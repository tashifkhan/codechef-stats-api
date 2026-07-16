import hashlib
import re
import json
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from core.cache import decode_body, encode_body, get_json, redis_enabled, set_json
from core.config import settings
from core.rate_limit import RateLimitResult, check_rate_limit


SKIP_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
INVALID_USER_MARKERS = ("user does not exist", "user not found", "not found on", "invalid username")


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "anonymous"


def _handle_from_path(path: str) -> str | None:
    if path in SKIP_PATHS or path.startswith("/docs/") or path.startswith("/redoc/"):
        return None
    segment = path.strip("/").split("/", 1)[0].strip()
    if not segment or "." in segment:
        return None
    return segment.lower()


def _query_string(request: Request) -> str:
    pairs = sorted(request.query_params.multi_items())
    return "&".join(f"{key}={value}" for key, value in pairs)


def _cache_key(platform: str, request: Request) -> str:
    raw = f"{request.method}:{request.url.path}:{_query_string(request)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"cache:{platform}:{digest}"


def _is_invalid_user(status_code: int, body: bytes) -> bool:
    if status_code == 404:
        return True
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False

    message = str(payload.get("message") or payload.get("detail") or "").lower()
    status = str(payload.get("status") or "").lower()
    return status == "error" and any(marker in message for marker in INVALID_USER_MARKERS)


def _rate_limited_response(result: RateLimitResult) -> JSONResponse:
    headers = {
        "Retry-After": str(result.retry_after),
        "X-RateLimit-Limit": str(result.limit or 0),
        "X-RateLimit-Remaining": str(result.remaining or 0),
        "X-RateLimit-Reset": str(result.reset_at or 0),
    }
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "message": "Rate limit exceeded",
            "retryAfter": result.retry_after,
            "limitedBy": result.limited_by,
        },
        headers=headers,
    )



def _ttl_from_cache_control(headers: dict, default: int) -> int:
    """Prefer response Cache-Control max-age when present (e.g. SVG 24h)."""
    cache_control = headers.get("cache-control") or headers.get("Cache-Control") or ""
    match = re.search(r"max-age=(\d+)", cache_control, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return default


class CacheRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, platform: str) -> None:
        super().__init__(app)
        self.platform = platform.lower()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "GET" or not redis_enabled() or request.url.path in SKIP_PATHS:
            return await call_next(request)

        handle = _handle_from_path(request.url.path)
        if handle is None:
            return await call_next(request)

        key = _cache_key(self.platform, request)
        cached = await get_json(key)
        if cached is not None:
            headers = dict(cached.get("headers") or {})
            headers["X-Cache"] = "HIT"
            headers.setdefault("Cache-Control", f"public, max-age={settings.api_cache_ttl_seconds}")
            return Response(
                content=decode_body(cached["body"]),
                status_code=int(cached["status_code"]),
                headers=headers,
                media_type=cached.get("media_type") or "application/json",
            )

        invalid_key = f"invalid:{self.platform}:{handle}"
        invalid_cached = await get_json(invalid_key)
        if invalid_cached is not None:
            limited = await self._check_invalid_limits(request, handle)
            if not limited.allowed:
                return _rate_limited_response(limited)
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "User does not exist"},
                headers={"X-Cache": "NEGATIVE-HIT"},
            )

        limited = await self._check_limits(request, handle)
        if not limited.allowed:
            return _rate_limited_response(limited)

        response = await call_next(request)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["X-Cache"] = "MISS"

        invalid_user = _is_invalid_user(response.status_code, body)
        if invalid_user:
            await set_json(invalid_key, {"invalid": True}, settings.invalid_user_cache_ttl_seconds)
        elif response.status_code == 200:
            headers.setdefault("Cache-Control", f"public, max-age={settings.api_cache_ttl_seconds}")
            ttl = _ttl_from_cache_control(headers, settings.api_cache_ttl_seconds)
            await set_json(key, self._cached_response(response, body), ttl)

        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    async def _check_limits(self, request: Request, handle: str) -> RateLimitResult:
        ip = _client_ip(request)
        ip_result = await check_rate_limit(
            f"ip:{self.platform}:{ip}",
            settings.rate_limit_ip_requests,
            settings.rate_limit_window_seconds,
            "ip",
        )
        if not ip_result.allowed:
            return ip_result
        return await check_rate_limit(
            f"handle:{self.platform}:{handle}",
            settings.rate_limit_handle_requests,
            settings.rate_limit_window_seconds,
            "handle",
        )

    async def _check_invalid_limits(self, request: Request, handle: str) -> RateLimitResult:
        ip = _client_ip(request)
        ip_result = await check_rate_limit(
            f"invalid-ip:{self.platform}:{ip}",
            settings.invalid_rate_limit_ip_requests,
            settings.invalid_rate_limit_window_seconds,
            "invalid-ip",
        )
        if not ip_result.allowed:
            return ip_result
        return await check_rate_limit(
            f"invalid-handle:{self.platform}:{handle}",
            settings.invalid_rate_limit_handle_requests,
            settings.invalid_rate_limit_window_seconds,
            "invalid-handle",
        )

    @staticmethod
    def _cached_response(response: Response, body: bytes) -> dict:
        headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "cache-control"}
        }
        return {
            "status_code": response.status_code,
            "headers": headers,
            "media_type": response.media_type or "application/json",
            "body": encode_body(body),
        }

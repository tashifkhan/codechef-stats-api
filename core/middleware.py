import hashlib
import json
import time
from collections.abc import Callable
from urllib.parse import urlencode

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from core.cache import decode_body, encode_body, get_json, redis_enabled, set_json
from core.cache_control import (
    BROWSER_MAX_AGE_SECONDS,
    CDN_MAX_AGE_SECONDS,
    STORE_TTL_HEADER,
    _no_store,
)
from core.config import settings
from core.rate_limit import RateLimitResult, check_rate_limit
from core.runtime import state


SKIP_PATHS = {
    "/",
    "/docs",
    "/docs/",
    "/docs/oauth2-redirect",
    "/redoc",
    "/redoc/",
    "/openapi.json",
    "/favicon.ico",
    "/playground",
    "/playground/",
    "/robots.txt",
    "/sitemap.xml",
}
STATIC_SUFFIXES = (
    ".png",
    ".ico",
    ".jpg",
    ".jpeg",
    ".svg",
    ".css",
    ".js",
    ".json",
    ".map",
    ".txt",
    ".xml",
    ".php",
    ".woff",
    ".woff2",
)
MAX_QUERY_VALUE_LENGTH = 64
INVALID_USER_MARKERS = ("user does not exist", "user not found", "not found on", "invalid username")

# Only parameters a route actually reads may split the cache. Unknown params
# are dropped so tracker links cannot create new store entries.
QUERY_PARAMS = {
    ("stats", "svg"): frozenset({"theme", "exclude"}),
    ("heatmap",): frozenset({"view", "year"}),
}


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "anonymous"


def _handle_from_path(path: str) -> str | None:
    # Scanner hits and static assets are not handles: charging them to a
    # user-shaped bucket spends commands on traffic no cache key can help.
    if path in SKIP_PATHS:
        return None
    # Look at the last segment only, so a real handle named "static" or
    # "playground" keeps its cache and its bucket. Scanner paths such as
    # /alice/wp-login.php or /alice/app.js stop charging alice.
    last = path.rstrip("/").rsplit("/", 1)[-1]
    if last.lower().endswith(STATIC_SUFFIXES):
        return None
    segment = path.strip("/").split("/", 1)[0].strip()
    if not segment or "." in segment:
        return None
    return segment.lower()


def _allowed_query_params(path: str) -> frozenset[str]:
    parts = [part for part in path.strip("/").split("/") if part]
    # Legacy /heatmap/{handle} keeps the canonical view/year filters.
    if len(parts) == 2 and parts[0].lower() == "heatmap":
        return QUERY_PARAMS[("heatmap",)]
    return QUERY_PARAMS.get(tuple(parts[1:]), frozenset())


def _query_params(request: Request) -> dict[str, str]:
    """The allowlisted params exactly as the route will read them.

    FastAPI lookups are case-sensitive, repeated scalar params resolve to the
    last occurrence, and values are not stripped. Mirroring that here keeps a
    request the route ignores from warming the key of one it honors.
    """
    allowed = _allowed_query_params(request.url.path)
    values: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        if key in allowed:
            values[key] = value
    return values


def _query_values_bounded(request: Request) -> bool:
    return all(
        len(value) <= MAX_QUERY_VALUE_LENGTH
        for value in _query_params(request).values()
    )


def _query_string(request: Request) -> str:
    return urlencode(sorted(_query_params(request).items()))


def _cache_key(platform: str, request: Request) -> str:
    raw = f"{request.method}:{request.url.path}:{_query_string(request)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    # v4 also invalidates entries written without expires_at.
    return f"cache:v4:{platform}:{digest}"


def _is_invalid_user(status_code: int, body: bytes) -> bool:
    if status_code == 404:
        return True
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False

    if not isinstance(payload, dict):
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
    _no_store(headers)
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
    """Return the store TTL, never the short edge window.

    Routes that need a longer store entry (SVG cards) send an explicit
    X-Store-TTL. Parsing max-age here would store every SVG for five minutes
    and every JSON response for one hour once the edge headers were shortened.
    """
    explicit = headers.get(STORE_TTL_HEADER)
    if explicit is not None:
        try:
            ttl = int(explicit)
        except (TypeError, ValueError):
            return default
        if ttl > 0:
            return ttl
    return default


def _uncacheable(headers: dict) -> bool:
    value = ",".join(
        part
        for part in (
            headers.get("cache-control") or headers.get("Cache-Control") or "",
            headers.get("cdn-cache-control") or headers.get("CDN-Cache-Control") or "",
        )
        if part
    )
    return any(
        directive.strip().lower() in {"no-store", "no-cache", "private"}
        for directive in value.split(",")
    )


def _remaining_store_ttl(cached: dict) -> int | None:
    """Seconds left on a store entry, when the entry records its expiry."""
    expires_at = cached.get("expires_at")
    if isinstance(expires_at, (int, float)):
        return max(0, int(expires_at - time.time()))
    return None


def _edge_cache_headers(
    headers: dict, default: int, remaining: int | None = None
) -> int:
    """Write one cacheable header pair and return the TTL used for the store."""
    ttl = _ttl_from_cache_control(headers, default)
    headers.pop(STORE_TTL_HEADER, None)
    max_age = BROWSER_MAX_AGE_SECONDS
    s_maxage = CDN_MAX_AGE_SECONDS
    if remaining is not None:
        # A hit near the end of the store entry must not pin the CDN for
        # another full hour past the data it can still be served from.
        max_age = max(1, min(max_age, remaining))
        s_maxage = max(1, min(s_maxage, remaining))
    value = f"public, max-age={max_age}, s-maxage={s_maxage}"
    headers["cache-control"] = value
    headers["cdn-cache-control"] = value
    return ttl


class CacheRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, platform: str) -> None:
        super().__init__(app)
        self.platform = platform.lower()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "GET" or not redis_enabled() or request.url.path in SKIP_PATHS:
            return await self._pass_through(request, call_next)

        handle = _handle_from_path(request.url.path)
        if handle is None:
            return await self._pass_through(request, call_next)

        # An oversized allowlisted value would mint a new store key per request.
        cacheable = _query_values_bounded(request)

        # A cache hit stays free, as before this change and in the GFG API.
        key = _cache_key(self.platform, request)
        cached = await get_json(key) if cacheable else None
        if cached is not None:
            headers = {
                str(key).lower(): value
                for key, value in (cached.get("headers") or {}).items()
            }
            headers["X-Cache"] = "HIT"
            _edge_cache_headers(
                headers,
                settings.api_cache_ttl_seconds,
                _remaining_store_ttl(cached),
            )
            return Response(
                content=decode_body(cached["body"]),
                status_code=int(cached["status_code"]),
                headers=headers,
                media_type=cached.get("media_type") or "application/json",
            )

        invalid_key = f"invalid:{self.platform}:{handle}"
        invalid_cached = await get_json(invalid_key) if cacheable else None
        if invalid_cached is not None:
            limited = await self._check_invalid_limits(request, handle)
            if not limited.allowed:
                return _rate_limited_response(limited)
            headers = {"X-Cache": "NEGATIVE-HIT"}
            _no_store(headers)
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "User does not exist"},
                headers=headers,
            )

        limited = await self._check_limits(request, handle)
        if not limited.allowed:
            return _rate_limited_response(limited)

        response = await call_next(request)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # Starlette lower-cases headers; normalise once so no write can add a
        # second Cache-Control header alongside the route's own.
        headers = {key.lower(): value for key, value in response.headers.items()}
        headers.pop("content-length", None)
        headers["X-Cache"] = "MISS"

        # Partial or stale data must not be cached. RequestBudgetMiddleware
        # reports the reason in X-Data-State, so the JSON body keeps its shape.
        current = state.get()
        if current and current.meta:
            _no_store(headers)
        # An upstream error envelope is not a cacheable success.
        app_status = response.status_code
        try:
            payload = json.loads(body)
            if app_status == 200 and isinstance(payload, dict) and payload.get("status") == "error":
                app_status = 404 if _is_invalid_user(200, body) else 502
                _no_store(headers)
        except (ValueError, TypeError):
            pass
        if not cacheable:
            _no_store(headers)
        invalid_user = _is_invalid_user(app_status, body)
        if invalid_user:
            # Every error answer is no-store, even when the route never set a
            # cache header of its own.
            _no_store(headers)
            if cacheable:
                await set_json(invalid_key, {"invalid": True}, settings.invalid_user_cache_ttl_seconds)
        elif app_status != 200:
            _no_store(headers)
        elif _uncacheable(headers):
            # The route declined shared caching; the CDN header must agree.
            _no_store(headers)
        elif cacheable:
            ttl = _edge_cache_headers(headers, settings.api_cache_ttl_seconds)
            payload = self._cached_response(response, body)
            payload["expires_at"] = time.time() + ttl
            await set_json(key, payload, ttl)

        return Response(
            content=body,
            status_code=app_status,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )

    @staticmethod
    async def _pass_through(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if response.status_code >= 400:
            _no_store(response.headers)
        return response

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
            if key.lower() in {"content-type", "cache-control", "cdn-cache-control"}
        }
        return {
            "status_code": response.status_code,
            "headers": headers,
            "media_type": response.media_type or "application/json",
            "body": encode_body(body),
        }

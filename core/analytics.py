"""Request analytics over OpenTelemetry (OTLP), with caller identification.

Each request becomes one OTLP server span. The caller is worked out in this order:

1. ``?client=<name>``: callers who identify themselves (asked for in the README).
2. The ``Origin`` header, then the ``Referer`` host: websites calling from a browser.
3. Otherwise the kind of caller, read from the User-Agent (python-requests, curl, ...).

Set the standard OpenTelemetry variables to enable it. For Honeycomb:

    OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
    OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=<ingest key>

Without an endpoint nothing is sent, so local runs and tests need no setup. Any OTLP
backend works (Grafana Cloud, a self-hosted collector), so switching is a config change.

Spans are posted directly as OTLP/HTTP JSON instead of through the OpenTelemetry SDK:
the SDK batches on a background thread, which Vercel can freeze before it sends.
"""

import asyncio
import hashlib
import os
import re
import secrets
import time
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
from starlette.types import ASGIApp, Message, Receive, Scope, Send


CLIENT_PARAM = "client"
OWN_HOSTS = re.compile(r"(^|\.)(tashif\.codes|codetrace\.xyz|taf\.sh)$")
LOCAL_HOSTS = re.compile(r"^(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|\[::1\])")
SAFE_NAME = re.compile(r"[^a-z0-9._-]+")
SKIP_PATHS = {"/favicon.ico", "/robots.txt"}
DOC_PATHS = {"docs", "redoc", "health", "playground"}
SEND_TIMEOUT = 2.0

# First match wins, so specific tools come before the generic browser check.
AGENTS = (
    ("python-requests", "python-requests"),
    ("python-httpx", "httpx"),
    ("aiohttp", "aiohttp"),
    ("python-urllib", "python-urllib"),
    ("node-fetch", "node-fetch"),
    ("undici", "node"),
    ("axios", "axios"),
    ("node", "node"),
    ("curl", "curl"),
    ("wget", "wget"),
    ("go-http-client", "go"),
    ("okhttp", "okhttp"),
    ("dart", "dart"),
    ("postman", "postman"),
    ("insomnia", "insomnia"),
    ("github-camo", "github-readme"),
    ("vercel", "vercel"),
    ("bot", "bot"),
    ("spider", "bot"),
    ("crawl", "bot"),
    ("mozilla", "browser"),
)


def _clean(value: str, limit: int = 64) -> str:
    return SAFE_NAME.sub("-", value.strip().lower()).strip("-")[:limit]


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _agent(user_agent: str) -> str:
    ua = user_agent.lower()
    for marker, name in AGENTS:
        if marker in ua:
            return name
    return "unknown"


def identify(query_string: str, headers: dict[str, str]) -> tuple[str, str, str]:
    """Return (identifier, display name, group) for a request."""
    client = parse_qs(query_string).get(CLIENT_PARAM, [""])[0]
    if client and (name := _clean(client)):
        return f"client:{name}", name, "Named clients"

    for header in ("origin", "referer"):
        host = _host(headers.get(header, ""))
        if not host:
            continue
        if LOCAL_HOSTS.match(host):
            return "local", "Local development", "Local"
        if OWN_HOSTS.search(host):
            return f"site:{host}", host, "Own sites"
        return f"site:{host}", host, "Websites"

    agent = _agent(headers.get("user-agent", ""))
    return f"anon:{agent}", f"Anonymous ({agent})", "Anonymous"


def _client_ip(headers: dict[str, str]) -> str:
    forwarded = headers.get("x-forwarded-for", "")
    return forwarded.split(",", 1)[0].strip() or headers.get("x-real-ip", "").strip()


def _endpoint(path: str) -> str:
    """/{username}/heatmap -> "heatmap". Grouping by raw path would split on every username."""
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "root"
    if len(parts) == 1 and ("." in parts[0] or parts[0] in DOC_PATHS):
        return parts[0]
    return parts[1] if len(parts) > 1 else "profile"


def _headers_from_env(raw: str) -> dict[str, str]:
    """Parse OTEL_EXPORTER_OTLP_HEADERS ("k1=v1,k2=v2", values may be URL-encoded)."""
    headers = {}
    for pair in raw.split(","):
        key, sep, value = pair.partition("=")
        if sep and key.strip():
            headers[key.strip()] = unquote(value.strip())
    return headers


def _attr(key: str, value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def build_attributes(api: str, scope: Scope, status: int, cache: str) -> dict:
    headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
    query = scope.get("query_string", b"").decode("latin-1")
    identifier, name, group = identify(query, headers)
    ip = _client_ip(headers)
    endpoint = _endpoint(scope["path"])
    return {
        # OpenTelemetry semantic conventions, so backends recognise them.
        "http.request.method": scope["method"],
        "http.response.status_code": status,
        "url.path": scope["path"],
        "http.route": endpoint,
        # Ours.
        "api": api,
        "endpoint": endpoint,
        "cache": cache,
        "consumer": identifier,
        "consumer.name": name,
        "consumer.group": group,
        "origin_host": _host(headers.get("origin", "")) or _host(headers.get("referer", "")) or None,
        "agent": _agent(headers.get("user-agent", "")),
        # Counts unique callers without storing raw IPs.
        "client.ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else None,
    }


def build_payload(api: str, scope: Scope, status: int, cache: str, start_ns: int, end_ns: int) -> dict:
    attributes = build_attributes(api, scope, status, cache)
    span = {
        "traceId": secrets.token_hex(16),
        "spanId": secrets.token_hex(8),
        "name": f"{scope['method']} {attributes['endpoint']}",
        "kind": 2,  # SERVER
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": [a for k, v in attributes.items() if (a := _attr(k, v))],
        "status": {"code": 2 if status >= 500 else 0},  # ERROR only for server faults
    }
    resource = [
        _attr("service.name", f"{api}-stats-api"),
        _attr("deployment.environment.name", "production" if os.environ.get("VERCEL_ENV") == "production" else os.environ.get("VERCEL_ENV", "local")),
        _attr("service.version", os.environ.get("VERCEL_GIT_COMMIT_SHA", "")[:7] or None),
    ]
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [a for a in resource if a]},
                "scopeSpans": [{"scope": {"name": "stats-api-analytics"}, "spans": [span]}],
            }
        ]
    }


class AnalyticsMiddleware:
    """Sends one OTLP span per request. Sits outside the cache middleware, so cache
    hits and 429s are counted too.

    By default the span is posted in the background, so the caller never waits.
    Pass wait=True on runtimes that end the invocation as soon as the response
    is done (Vercel's legacy @vercel/python builder): the post then finishes
    before the handler returns, on a fresh client, since such runtimes can run
    each request on a new event loop. A short timeout and fail-open path keep a
    Honeycomb outage from hanging or failing the request.
    """

    def __init__(self, app: ASGIApp, api: str, wait: bool = False) -> None:
        self.app = app
        self.api = api
        self.wait = wait
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
        base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
        self.url = endpoint or (f"{base}/v1/traces" if base else "")
        self.headers = {
            **_headers_from_env(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")),
            "Content-Type": "application/json",
        }
        self.client: httpx.AsyncClient | None = None
        self.pending: set[asyncio.Task] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.url or scope["type"] != "http" or scope["path"] in SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        start_ns = time.time_ns()
        seen = {"status": 500, "cache": "NONE"}

        async def watch(message: Message) -> None:
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]
                for key, value in message.get("headers", []):
                    if key.lower() == b"x-cache":
                        seen["cache"] = value.decode("latin-1")
            await send(message)

        try:
            await self.app(scope, receive, watch)
        finally:
            try:
                payload = build_payload(self.api, scope, seen["status"], seen["cache"], start_ns, time.time_ns())
                if self.wait:
                    await self._send_now(payload)
                else:
                    # Background send, so the caller never waits on the backend.
                    task = asyncio.create_task(self._send(payload))
                    self.pending.add(task)
                    task.add_done_callback(self.pending.discard)
            except Exception:  # analytics must never break a request
                pass

    async def _send(self, payload: dict) -> None:
        try:
            if self.client is None:
                self.client = httpx.AsyncClient(timeout=SEND_TIMEOUT)
            await self.client.post(self.url, json=payload, headers=self.headers)
        except Exception:
            pass

    async def _send_now(self, payload: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as client:
                await client.post(self.url, json=payload, headers=self.headers)
        except Exception:
            pass

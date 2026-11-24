"""Cache header policy shared by routes, middleware and the request runtime.

The browser gets a short window and the CDN an hour. The store keeps its own
long TTL, carried separately from ``Cache-Control`` so rewriting the edge
headers cannot shorten a 12h JSON or 24h SVG entry.
"""

BROWSER_MAX_AGE_SECONDS = 300
CDN_MAX_AGE_SECONDS = 3600
STORE_TTL_HEADER = "x-store-ttl"


def _no_store(headers):
    """Set both cache headers to no-store, removing any earlier values.

    Accepts a mutable mapping (a lower-case dict or Starlette MutableHeaders)
    or the raw ASGI header list used by ``RequestBudgetMiddleware``.
    """
    if isinstance(headers, list):
        headers[:] = [
            (name, value)
            for name, value in headers
            if name.lower() not in (b"cache-control", b"cdn-cache-control", b"x-store-ttl")
        ]
        headers.extend([
            (b"cache-control", b"no-store"),
            (b"cdn-cache-control", b"no-store"),
        ])
        return headers

    for name in (
        "Cache-Control",
        "CDN-Cache-Control",
        "X-Store-TTL",
        "cache-control",
        "cdn-cache-control",
        "x-store-ttl",
    ):
        if name in headers:
            del headers[name]
    headers["cache-control"] = "no-store"
    headers["cdn-cache-control"] = "no-store"
    return headers

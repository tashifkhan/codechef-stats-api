"""Cache policy: long store TTLs, narrow keys, no-store parity and HIT cost."""

import asyncio
import time
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from core import middleware
from core.cache import encode_body
from core.cache_control import BROWSER_MAX_AGE_SECONDS, CDN_MAX_AGE_SECONDS
from core.config import settings
from core.rate_limit import RateLimitResult
from core.runtime import RequestBudgetMiddleware, state
from services.stats_svg import (
    SVG_CACHE_SECONDS,
    error_svg_response,
    stats_svg_response,
)


def _app(*, budget: bool = False) -> FastAPI:
    app = FastAPI()

    @app.get("/{username}/profile")
    async def profile(username: str):
        return {"status": "success", "username": username}

    @app.get("/{username}/stats")
    async def stats(username: str):
        return {"status": "success", "username": username}

    @app.get("/{username}/stats/svg")
    async def svg(username: str, theme: str = "dark"):
        return stats_svg_response("codechef", username, {"totalSolved": 1}, theme=theme)

    @app.get("/{username}/error")
    async def error(username: str):
        return {"status": "error", "message": "boom"}

    @app.get("/{username}/missing")
    async def missing(username: str):
        raise HTTPException(status_code=404, detail="User not found")

    @app.get("/{username}/error-card")
    async def error_card(username: str):
        return error_svg_response("User not found", platform="codechef", username=username)

    @app.get("/{username}/stale")
    async def stale(username: str):
        current = state.get()
        if current is not None:
            current.meta["source"] = {"status": "stale", "updatedAt": 1}
        return {"status": "success"}

    app.add_middleware(middleware.CacheRateLimitMiddleware, platform="codechef")
    if budget:
        app.add_middleware(RequestBudgetMiddleware, seconds=5)
    return app


def _patch_store(monkeypatch, *, cached=None):
    stored, ttls = {}, {}
    if cached is not None:
        reads = AsyncMock(return_value=cached)
    else:
        async def read(key):
            return stored.get(key)
        reads = AsyncMock(side_effect=read)

    async def write(key, value, ttl):
        stored[key] = value
        ttls[key] = ttl

    writes = AsyncMock(side_effect=write)

    async def allowed(*args, **kwargs):
        return RateLimitResult(allowed=True)

    limiter = AsyncMock(side_effect=allowed)
    monkeypatch.setattr(middleware, "redis_enabled", lambda: True)
    monkeypatch.setattr(middleware, "get_json", reads)
    monkeypatch.setattr(middleware, "set_json", writes)
    monkeypatch.setattr(middleware, "check_rate_limit", limiter)
    return stored, ttls, reads, writes, limiter


def test_json_and_svg_keep_long_store_ttls(monkeypatch):
    _stored, _ttls, _reads, writes, _limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        json_response = client.get("/alice/stats")
        svg_response = client.get("/alice/stats/svg")

    control = f"public, max-age={BROWSER_MAX_AGE_SECONDS}, s-maxage={CDN_MAX_AGE_SECONDS}"
    for response in (json_response, svg_response):
        assert response.status_code == 200
        assert response.headers.get_list("cache-control") == [control]
        assert response.headers.get_list("cdn-cache-control") == [control]
        assert "x-store-ttl" not in response.headers
    assert settings.api_cache_ttl_seconds == 43200
    assert SVG_CACHE_SECONDS == 86400
    # JSON first, SVG second: the store TTLs prove the mapping, not just the set.
    assert [call.args[2] for call in writes.await_args_list] == [43200, 86400]


def test_ttl_helper_ignores_the_short_edge_window():
    headers = {"cache-control": "public, max-age=300, s-maxage=3600"}
    assert middleware._ttl_from_cache_control(headers, 43200) == 43200
    assert middleware._ttl_from_cache_control({"x-store-ttl": "86400"}, 43200) == 86400


def test_only_used_query_params_split_the_cache_key(monkeypatch):
    stored, _ttls, _reads, _writes, _limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        first = client.get("/alice/profile?exclude=anything")
        junk = client.get("/alice/profile?utm_source=newsletter")
        dark = client.get("/alice/stats/svg?theme=dark")
        light = client.get("/alice/stats/svg?theme=light")
        python = client.get("/alice/stats/svg?exclude=Python")
        rust = client.get("/alice/stats/svg?exclude=Rust")

    assert first.headers["x-cache"] == "MISS"
    assert junk.headers["x-cache"] == "HIT"
    assert dark.headers["x-cache"] == "MISS"
    assert light.headers["x-cache"] == "MISS"
    assert python.headers["x-cache"] == "MISS"
    assert rust.headers["x-cache"] == "MISS"
    assert len(stored) == 5


def test_cache_key_matches_the_route_query_params(monkeypatch):
    stored, _ttls, _reads, _writes, _limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        light = client.get("/alice/stats/svg?theme=light")
        upper = client.get("/alice/stats/svg?THEME=light")
        padded = client.get("/alice/stats/svg?theme=%20light")
        repeated = client.get("/alice/stats/svg?theme=light&theme=dark")
        repeated_again = client.get("/alice/stats/svg?theme=dark")
        reversed_pair = client.get("/alice/stats/svg?theme=dark&theme=light")
        python = client.get("/alice/stats/svg?exclude=Python")
        junk = client.get("/alice/stats/svg?utm_source=x&exclude=Python")

    # The route never reads THEME, so its response must not warm theme=light.
    assert light.headers["x-cache"] == "MISS"
    assert upper.headers["x-cache"] == "MISS"
    assert upper.content != light.content
    # Values are not stripped: " light" is a different theme.
    assert padded.headers["x-cache"] == "MISS"
    assert padded.content != light.content
    # FastAPI takes the last repeated value, so these share a key.
    assert repeated.headers["x-cache"] == "MISS"
    assert repeated_again.headers["x-cache"] == "HIT"
    assert reversed_pair.headers["x-cache"] == "HIT"
    assert reversed_pair.content == light.content
    # Unknown names still cannot create entries.
    assert python.headers["x-cache"] == "MISS"
    assert junk.headers["x-cache"] == "HIT"
    assert len(stored) == 5


def test_meta_and_error_paths_set_both_no_store_headers(monkeypatch):
    stored, _ttls, _reads, _writes, _limiter = _patch_store(monkeypatch)
    with TestClient(_app(budget=True)) as client:
        stale_response = client.get("/alice/stale")
        error_response = client.get("/alice/error")

    assert error_response.status_code == 502
    for response in (stale_response, error_response):
        assert response.headers.get_list("cache-control") == ["no-store"]
        assert response.headers.get_list("cdn-cache-control") == ["no-store"]
    assert len(stale_response.headers.get_list("x-data-state")) == 1
    assert stored == {}


def test_real_404_negative_hit_and_error_svg_are_no_store(monkeypatch):
    stored, _ttls, _reads, _writes, _limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        not_found = client.get("/alice/missing")
        negative = client.get("/alice/missing")
        svg = client.get("/bob/error-card")

    assert not_found.status_code == 404
    assert negative.status_code == 404
    assert negative.headers["x-cache"] == "NEGATIVE-HIT"
    assert svg.status_code == 404
    assert svg.headers["content-type"].startswith("image/svg+xml")
    for response in (not_found, negative, svg):
        assert response.headers.get_list("cache-control") == ["no-store"]
        assert response.headers.get_list("cdn-cache-control") == ["no-store"]
    assert not any(key.startswith("cache:v4:") for key in stored)


def test_rate_limited_response_sets_both_no_store_headers(monkeypatch):
    _stored, _ttls, _reads, _writes, _limiter = _patch_store(monkeypatch)

    async def denied(*args, **kwargs):
        return RateLimitResult(
            allowed=False,
            retry_after=7,
            limited_by="ip",
            limit=60,
            remaining=0,
            reset_at=1,
        )

    monkeypatch.setattr(middleware, "check_rate_limit", AsyncMock(side_effect=denied))
    with TestClient(_app()) as client:
        response = client.get("/alice/stats")

    assert response.status_code == 429
    assert response.headers.get_list("cache-control") == ["no-store"]
    assert response.headers.get_list("cdn-cache-control") == ["no-store"]


def test_hit_costs_one_read_and_no_rate_limit_eval(monkeypatch):
    cached = {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "media_type": "application/json",
        "body": encode_body(b'{"status":"success"}'),
        "expires_at": time.time() + CDN_MAX_AGE_SECONDS + 1,
    }
    _stored, _ttls, reads, writes, limiter = _patch_store(monkeypatch, cached=cached)
    with TestClient(_app()) as client:
        response = client.get("/alice/stats")

    assert response.headers["x-cache"] == "HIT"
    assert reads.await_count == 1
    limiter.assert_not_awaited()
    writes.assert_not_awaited()
    control = f"public, max-age={BROWSER_MAX_AGE_SECONDS}, s-maxage={CDN_MAX_AGE_SECONDS}"
    assert response.headers.get_list("cache-control") == [control]
    assert response.headers.get_list("cdn-cache-control") == [control]


def test_hit_near_expiry_clamps_the_edge_window(monkeypatch):
    cached = {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "media_type": "application/json",
        "body": encode_body(b'{"status":"success"}'),
        "expires_at": time.time() + 10,
    }
    _stored, _ttls, reads, writes, limiter = _patch_store(monkeypatch, cached=cached)
    with TestClient(_app()) as client:
        response = client.get("/alice/stats")

    assert response.headers["x-cache"] == "HIT"
    control = response.headers.get_list("cache-control")
    assert len(control) == 1
    assert response.headers.get_list("cdn-cache-control") == control
    assert "s-maxage=3600" not in control[0]
    s_maxage = int(control[0].split("s-maxage=")[1])
    max_age = int(control[0].split("max-age=")[1].split(",")[0])
    assert 1 <= s_maxage <= 10
    assert 1 <= max_age <= 10
    assert reads.await_count == 1
    limiter.assert_not_awaited()
    writes.assert_not_awaited()


def test_static_and_playground_are_real_handles(monkeypatch):
    _stored, ttls, _reads, _writes, limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        static = client.get("/static/stats")
        playground = client.get("/playground/stats")

    assert static.status_code == 200
    assert playground.status_code == 200
    assert len(ttls) == 2
    buckets = [call.args[0] for call in limiter.await_args_list]
    assert "handle:codechef:static" in buckets
    assert "handle:codechef:playground" in buckets


def test_scanner_paths_skip_rate_limits_and_store(monkeypatch):
    _stored, _ttls, reads, writes, limiter = _patch_store(monkeypatch)
    with TestClient(_app()) as client:
        for path in ("/alice/wp-login.php", "/alice/app.js", "/favicon.ico", "/robots.txt"):
            client.get(path)

    limiter.assert_not_awaited()
    reads.assert_not_awaited()
    writes.assert_not_awaited()


def test_oversized_query_value_is_not_stored(monkeypatch):
    _stored, _ttls, reads, writes, limiter = _patch_store(monkeypatch)
    long_value = "x" * 65
    with TestClient(_app()) as client:
        first = client.get(f"/alice/stats/svg?exclude={long_value}")
        second = client.get(f"/alice/stats/svg?exclude={long_value}")

    for response in (first, second):
        assert response.status_code == 200
        assert response.headers.get_list("cache-control") == ["no-store"]
        assert response.headers.get_list("cdn-cache-control") == ["no-store"]
    reads.assert_not_awaited()
    writes.assert_not_awaited()
    assert limiter.await_count == 4


def test_request_budget_replaces_both_cache_headers_on_meta():
    async def app(scope, receive, send):
        state.get().meta["source"] = {"status": "stale"}
        response = Response(
            "ok",
            headers={
                "Cache-Control": "public, max-age=300",
                "CDN-Cache-Control": "public, max-age=3600",
            },
        )
        await response(scope, receive, send)

    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=RequestBudgetMiddleware(app, seconds=5)),
            base_url="http://test",
        ) as http:
            return await http.get("/alice/stats")

    response = asyncio.run(call())
    assert response.headers.get_list("cache-control") == ["no-store"]
    assert response.headers.get_list("cdn-cache-control") == ["no-store"]


def test_violations_reset_only_at_window_start():
    from core.rate_limit import RATE_SCRIPT

    allowed_branch = RATE_SCRIPT.split("if count <= tonumber(ARGV[1]) then", 1)[1].split("local violations", 1)[0]
    assert "if count == 1 then redis.call('DEL', KEYS[3]) end" in allowed_branch
    assert "\n redis.call('DEL', KEYS[3])" not in allowed_branch

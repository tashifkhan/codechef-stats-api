"""Offline regressions for the Vercel 10s timeout incident."""

import asyncio
import time

import httpx
import pytest
from fastapi import HTTPException

from core import cache, rate_limit, runtime, source as source_module
from main import app
from services import client


async def get(path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        return await http.get(path, headers={"Origin": "https://example.org"})


@pytest.mark.anyio
async def test_request_budget_cancels_stalled_route_and_keeps_cors(monkeypatch) -> None:
    cancelled = asyncio.Event()

    async def stalled(handle):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()

    monkeypatch.setattr(runtime, "REQUEST_BUDGET", 0.05)
    monkeypatch.setattr("routes.profile.fetch_codechef_profile", stalled)
    monkeypatch.setattr("core.middleware.redis_enabled", lambda: False)
    started = time.monotonic()
    response = await get("/alice/profile")

    assert time.monotonic() - started < 2
    assert response.status_code == 504
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["access-control-allow-origin"] == "https://example.org"
    assert cancelled.is_set()


@pytest.mark.anyio
async def test_stalled_store_fails_open_for_cache_and_rate_limit(monkeypatch) -> None:
    async def stalled(*args, **kwargs):
        await asyncio.sleep(60)

    class StalledRedis:
        get = setex = eval = set = stalled

    monkeypatch.setattr(cache, "get_redis", lambda: StalledRedis())
    monkeypatch.setattr(cache, "OPERATION_TIMEOUT", 0.02)

    started = time.monotonic()
    assert await cache.get_json("k") is None
    assert await cache.set_json("k", {"ok": True}, 60) is False
    result = await rate_limit.check_rate_limit("ip:test", 60, 60, "ip")
    assert result.allowed
    assert time.monotonic() - started < 1


@pytest.mark.anyio
async def test_store_calls_respect_remaining_request_budget(monkeypatch) -> None:
    async def stalled(*args, **kwargs):
        await asyncio.sleep(60)

    class StalledRedis:
        get = stalled

    monkeypatch.setattr(cache, "get_redis", lambda: StalledRedis())
    current = runtime.RequestState(deadline=time.monotonic() + 0.02, client=None)
    token = runtime.state.set(current)
    try:
        started = time.monotonic()
        assert await cache.get_json("k") is None
    finally:
        runtime.state.reset(token)
    assert time.monotonic() - started < 0.2


class MemoryStore:
    def __init__(self):
        self.values = {}

    async def get_json(self, key):
        return self.values.get(key)

    async def set_json(self, key, value, ttl):
        self.values[key] = value
        return True

    async def command(self, name, *args, **kwargs):
        return True  # Lease always granted.


@pytest.fixture
def memory_store(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(source_module, "get_json", store.get_json)
    monkeypatch.setattr(source_module, "set_json", store.set_json)
    monkeypatch.setattr(source_module, "command", store.command)
    monkeypatch.setattr(source_module, "redis_enabled", lambda: True)
    return store


async def _seed_stale(store, key):
    async def ok():
        return {"value": "old"}

    await source_module.source(key, ok)
    for entry in store.values.values():
        entry["at"] -= 10_000


@pytest.mark.anyio
async def test_upstream_failure_falls_back_to_stale_and_marks_meta(memory_store) -> None:
    await _seed_stale(memory_store, "profile:alice")

    async def down():
        raise HTTPException(status_code=503, detail="CodeChef is unreachable")

    current = runtime.RequestState(deadline=time.monotonic() + 5, client=None)
    token = runtime.state.set(current)
    try:
        data = await source_module.source("profile:alice", down)
    finally:
        runtime.state.reset(token)

    assert data == {"value": "old"}
    assert current.meta["source"]["status"] == "stale"


@pytest.mark.anyio
async def test_not_found_is_not_masked_by_stale_data(memory_store) -> None:
    await _seed_stale(memory_store, "profile:bob")

    async def missing():
        raise HTTPException(status_code=404, detail="CodeChef user not found")

    with pytest.raises(HTTPException) as error:
        await source_module.source("profile:bob", missing)
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_profile_network_errors_become_http_errors(monkeypatch) -> None:
    client.profile_cache.clear()

    def transport(exc):
        def handler(request):
            raise exc
        return httpx.MockTransport(handler)

    for exc, status in ((httpx.ReadTimeout("slow"), 504), (httpx.ConnectError("down"), 503)):
        async with httpx.AsyncClient(transport=transport(exc)) as http:
            current = runtime.RequestState(deadline=time.monotonic() + 5, client=http)
            token = runtime.state.set(current)
            try:
                with pytest.raises(HTTPException) as error:
                    await client._fetch_codechef_profile("alice")
            finally:
                runtime.state.reset(token)
        assert error.value.status_code == status

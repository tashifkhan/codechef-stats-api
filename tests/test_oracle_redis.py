"""Tests for Oracle Redis primary cache with Upstash REST fallback and cooldown."""

import asyncio
import ssl

import httpx
import pytest
from redis import exceptions as redis_exc

from core import cache
from core.config import settings


class FakeOracleClient:
    def __init__(self, store=None, exc=None, delay=0.0):
        self.store = store if store is not None else {}
        self.exc = exc
        self.delay = delay
        self.calls = []

    async def _maybe_fail(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc is not None:
            raise self.exc

    async def get(self, key):
        self.calls.append(("get", key))
        await self._maybe_fail()
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.calls.append(("setex", key, ttl))
        await self._maybe_fail()
        self.store[key] = value
        return True

    async def delete(self, key):
        self.calls.append(("delete", key))
        await self._maybe_fail()
        return 1 if self.store.pop(key, None) is not None else 0


class FakeUpstashStore:
    def __init__(self):
        self.store = {}
        self.requests = []

    def client(self, monkeypatch):
        import json
        from contextlib import asynccontextmanager

        def handler(request: httpx.Request) -> httpx.Response:
            cmd = json.loads(request.content)
            self.requests.append(cmd)
            name = cmd[0].upper()
            if name == "GET":
                return httpx.Response(200, json={"result": self.store.get(cmd[1])})
            if name == "SET":
                self.store[cmd[1]] = cmd[2]
                return httpx.Response(200, json={"result": "OK"})
            if name == "DEL":
                existed = cmd[1] in self.store
                self.store.pop(cmd[1], None)
                return httpx.Response(200, json={"result": 1 if existed else 0})
            return httpx.Response(400, json={"error": "unsupported"})

        real_async_client = httpx.AsyncClient

        @asynccontextmanager
        async def fake_http_client():
            async with real_async_client(transport=httpx.MockTransport(handler)) as c:
                yield c

        monkeypatch.setattr(cache, "http_client", fake_http_client)
        return cache.UpstashRestRedis("https://backup.upstash.io", "tok")


@pytest.fixture(autouse=True)
def _clean_cache_state(monkeypatch):
    cache.reset_oracle_state()
    monkeypatch.setattr(cache, "_client", None)
    monkeypatch.setattr(settings, "oracle_redis_url", None)
    monkeypatch.setattr(settings, "oracle_redis_ca_cert", None)
    monkeypatch.setattr(settings, "redis_url", None)
    monkeypatch.delenv("ORACLE_REDIS_URL", raising=False)
    monkeypatch.delenv("ORACLE_REDIS_CA_CERT", raising=False)
    yield
    cache.reset_oracle_state()


def test_unset_oracle_url_uses_existing_upstash_path(monkeypatch):
    upstash = FakeUpstashStore()
    upstash.store["k1"] = '{"v":1}'
    monkeypatch.setattr(cache, "get_redis", lambda: upstash.client(monkeypatch))

    assert cache.get_oracle_redis() is None
    assert asyncio.run(cache.get_json("k1")) == {"v": 1}
    assert upstash.requests == [["GET", "k1"]]


def test_oracle_primary_used_when_healthy_and_skips_upstash(monkeypatch):
    upstash = FakeUpstashStore()
    oracle = FakeOracleClient(store={"k1": '{"source":"oracle"}'})

    monkeypatch.setenv("ORACLE_REDIS_URL", "rediss://cache:secret@example.com:6380/0")
    monkeypatch.setattr(cache, "get_oracle_redis", lambda: oracle)
    monkeypatch.setattr(cache, "get_redis", lambda: upstash.client(monkeypatch))

    assert cache.redis_enabled() is True
    assert asyncio.run(cache.get_json("k1")) == {"source": "oracle"}
    assert oracle.calls == [("get", "k1")]
    assert upstash.requests == []


@pytest.mark.parametrize(
    "exc",
    [
        redis_exc.ConnectionError("connection refused"),
        redis_exc.TimeoutError("socket timed out"),
        redis_exc.AuthenticationError("WRONGPASS"),
        ssl.SSLCertVerificationError("certificate verify failed"),
    ],
)
def test_oracle_failure_falls_back_to_upstash_and_trips_cooldown(monkeypatch, exc):
    upstash = FakeUpstashStore()
    upstash.store["k1"] = '{"source":"upstash"}'
    oracle = FakeOracleClient(exc=exc)

    now = [1000.0]
    monkeypatch.setattr(cache.time, "monotonic", lambda: now[0])
    monkeypatch.setenv("ORACLE_REDIS_URL", "rediss://cache:secret@example.com:6380/0")
    monkeypatch.setattr(cache, "get_oracle_redis", lambda: oracle)
    monkeypatch.setattr(cache, "get_redis", lambda: upstash.client(monkeypatch))

    # First call fails on Oracle, falls back to Upstash for that same call.
    assert asyncio.run(cache.get_json("k1")) == {"source": "upstash"}
    assert len(oracle.calls) == 1
    assert upstash.requests == [["GET", "k1"]]

    # Subsequent calls within the 60s cooldown skip Oracle entirely.
    now[0] += 30.0
    assert asyncio.run(cache.get_json("k1")) == {"source": "upstash"}
    assert len(oracle.calls) == 1
    assert len(upstash.requests) == 2

    # After 60s, Oracle is retried and resumes primary duty when healthy.
    now[0] += 31.0
    oracle.exc = None
    oracle.store["k1"] = '{"source":"oracle-recovered"}'
    assert asyncio.run(cache.get_json("k1")) == {"source": "oracle-recovered"}
    assert len(oracle.calls) == 2
    assert len(upstash.requests) == 2


def test_oracle_timeout_falls_back_to_upstash(monkeypatch):
    upstash = FakeUpstashStore()
    upstash.store["k1"] = '{"source":"upstash"}'
    oracle = FakeOracleClient(delay=1.0)

    monkeypatch.setattr(cache, "ORACLE_OPERATION_TIMEOUT", 0.01)
    monkeypatch.setenv("ORACLE_REDIS_URL", "rediss://cache:secret@example.com:6380/0")
    monkeypatch.setattr(cache, "get_oracle_redis", lambda: oracle)
    monkeypatch.setattr(cache, "get_redis", lambda: upstash.client(monkeypatch))

    assert asyncio.run(cache.get_json("k1")) == {"source": "upstash"}
    assert cache._oracle_in_cooldown() is True


def test_oracle_client_pins_ca_and_timeouts(monkeypatch, tmp_path):
    captured = {}

    def fake_from_url(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(cache.redis, "from_url", fake_from_url)
    monkeypatch.setattr(settings, "oracle_redis_url", "rediss://cache:pw@129.154.227.112:6380/0")
    monkeypatch.setattr(
        settings,
        "oracle_redis_ca_cert",
        "-----BEGIN CERTIFICATE-----\\nMIIB\\n-----END CERTIFICATE-----",
    )

    async def build():
        return cache.get_oracle_redis()

    asyncio.run(build())
    assert captured["url"] == "rediss://cache:pw@129.154.227.112:6380/0"
    assert captured["kwargs"]["socket_timeout"] == 1.5
    assert captured["kwargs"]["socket_connect_timeout"] == 1.5
    assert captured["kwargs"]["ssl_cert_reqs"] == "required"
    assert "\n" in captured["kwargs"]["ssl_ca_data"]

    # Also verify /tmp fallback when ssl_ca_data is unsupported.
    ca_file = tmp_path / "ca.pem"
    monkeypatch.setattr(cache, "_SUPPORTS_SSL_CA_DATA", False)
    monkeypatch.setattr(cache, "_ORACLE_CA_TMP_PATH", str(ca_file))
    cache.reset_oracle_state()
    asyncio.run(build())
    assert captured["kwargs"]["ssl_ca_certs"] == str(ca_file)
    assert "-----BEGIN CERTIFICATE-----" in ca_file.read_text()

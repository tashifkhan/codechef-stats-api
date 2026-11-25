"""In-process TTL cache plus bounded native Redis and Upstash REST storage.

Every store call is bounded by OPERATION_TIMEOUT and the request deadline, and
fails open to None so a stalled store cannot use up the function budget.
"""

import asyncio
import inspect
import json
import os
import time
import weakref
from base64 import b64decode, b64encode
from collections import OrderedDict
from threading import Lock
from time import monotonic
from typing import Any, Generic, TypeVar

import httpx
from redis import asyncio as redis

from core.config import settings
from core.runtime import http_client, remaining

OPERATION_TIMEOUT = 0.25
ORACLE_OPERATION_TIMEOUT = 1.5
ORACLE_COOLDOWN_SECONDS = 60.0
_ORACLE_CA_TMP_PATH = "/tmp/oracle-redis-ca.pem"
_SUPPORTS_SSL_CA_DATA = "ssl_ca_data" in inspect.signature(redis.SSLConnection.__init__).parameters


K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, ttl_seconds: int, max_size: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._values: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._values.get(key)
            if entry is None:
                return None

            expires_at, value = entry
            if expires_at <= monotonic():
                self._values.pop(key, None)
                return None

            self._values.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._values[key] = (monotonic() + self.ttl_seconds, value)
            self._values.move_to_end(key)

            while len(self._values) > self.max_size:
                self._values.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class UpstashRestRedis:
    """Minimal Redis-over-HTTP client for Upstash's REST API."""

    def __init__(self, url: str, token: str):
        self._url = url.strip().rstrip("/")
        if not self._url.startswith(("https://", "http://")):
            self._url = "https://" + self._url
        self._headers = {"Authorization": "Bearer " + token}

    async def _command(self, *parts):
        try:
            async with http_client() as client:
                response = await asyncio.wait_for(
                    client.post(self._url, headers=self._headers, json=[str(p) for p in parts]),
                    min(OPERATION_TIMEOUT, remaining()),
                )
            if response.status_code != 200:
                return None
            body = response.json()
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
            return None
        return None if not isinstance(body, dict) or body.get("error") else body.get("result")

    async def get(self, key):
        return await self._command("GET", key)

    async def mget(self, keys):
        return await self._command("MGET", *keys) if keys else []

    async def setex(self, key, ttl, value):
        return await self._command("SET", key, value, "EX", ttl)

    async def set(self, key, value, ex=None, nx=False):
        parts = ["SET", key, value]
        if ex is not None:
            parts += ["EX", ex]
        if nx:
            parts += ["NX"]
        return await self._command(*parts)

    async def delete(self, key):
        return await self._command("DEL", key)

    async def eval(self, script, numkeys, *args):
        return await self._command("EVAL", script, numkeys, *args)


_client = None
_native_clients = weakref.WeakKeyDictionary()


def _rest_settings():
    return (
        getattr(settings, "upstash_rest_url", None),
        getattr(settings, "upstash_rest_token", None),
    )


_oracle_clients = weakref.WeakKeyDictionary()
_oracle_cooldown_until = 0.0


def _oracle_settings():
    url = getattr(settings, "oracle_redis_url", None)
    if url is None:
        url = os.getenv("ORACLE_REDIS_URL")
    url = url.strip() or None if isinstance(url, str) else None
    ca_cert = getattr(settings, "oracle_redis_ca_cert", None)
    if ca_cert is None:
        ca_cert = os.getenv("ORACLE_REDIS_CA_CERT")
    return url, ca_cert


def _oracle_url():
    url, _ = _oracle_settings()
    return url


def _normalize_ca_pem(raw):
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if "-----BEGIN" not in text and os.path.isfile(text):
        with open(text, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
    elif "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    return text or None


def _oracle_ssl_kwargs(url, ca_raw):
    kwargs = {}
    ca_pem = _normalize_ca_pem(ca_raw)
    if ca_pem:
        kwargs["ssl_cert_reqs"] = "required"
        if _SUPPORTS_SSL_CA_DATA:
            kwargs["ssl_ca_data"] = ca_pem
        else:
            fd = os.open(_ORACLE_CA_TMP_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(ca_pem)
                if not ca_pem.endswith("\n"):
                    fh.write("\n")
            kwargs["ssl_ca_certs"] = _ORACLE_CA_TMP_PATH
    elif url.lower().startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = "required"
    return kwargs


def _oracle_in_cooldown():
    return time.monotonic() < _oracle_cooldown_until


def _trip_oracle_cooldown():
    global _oracle_cooldown_until
    _oracle_cooldown_until = time.monotonic() + ORACLE_COOLDOWN_SECONDS


def reset_oracle_state():
    global _oracle_cooldown_until
    _oracle_cooldown_until = 0.0
    _oracle_clients.clear()


def get_oracle_redis():
    url, ca_raw = _oracle_settings()
    if not url:
        return None
    loop = asyncio.get_running_loop()
    cache_key = (url, ca_raw)
    entry = _oracle_clients.get(loop)
    if entry is None or entry[0] != cache_key:
        client = redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=ORACLE_OPERATION_TIMEOUT,
            socket_connect_timeout=ORACLE_OPERATION_TIMEOUT,
            **_oracle_ssl_kwargs(url, ca_raw),
        )
        _oracle_clients[loop] = (cache_key, client)
        return client
    return entry[1]


def redis_enabled() -> bool:
    url, token = _rest_settings()
    return bool(_oracle_url() or getattr(settings, "redis_url", None) or (url and token))


def get_redis():
    """One native client per event loop, since a connection pool cannot cross loops."""
    global _client
    if getattr(settings, "redis_url", None):
        loop = asyncio.get_running_loop()
        if loop not in _native_clients:
            _native_clients[loop] = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=OPERATION_TIMEOUT,
                socket_connect_timeout=OPERATION_TIMEOUT,
            )
        return _native_clients[loop]
    if _client is None:
        url, token = _rest_settings()
        if url and token:
            _client = UpstashRestRedis(url, token)
    return _client


async def command(name, *args, **kwargs):
    """Run one store command (Oracle primary, backup fallback). Any failure returns None."""
    if _oracle_url() and not _oracle_in_cooldown():
        try:
            oracle_client = get_oracle_redis()
            method = getattr(oracle_client, name, None) if oracle_client is not None else None
            if method is not None:
                return await asyncio.wait_for(method(*args, **kwargs), min(ORACLE_OPERATION_TIMEOUT, remaining()))
        except Exception:
            _trip_oracle_cooldown()

    client = get_redis()
    method = getattr(client, name, None) if client is not None else None
    if method is None:
        return None
    try:
        return await asyncio.wait_for(method(*args, **kwargs), min(OPERATION_TIMEOUT, remaining()))
    except Exception:
        return None


async def get_json(key: str) -> Any:
    value = await command("get", key)
    if value is None:
        return None
    try:
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    except (ValueError, TypeError):
        return None


async def get_many(keys: list[str]) -> list[Any]:
    result: list[Any] = []
    for start in range(0, len(keys), 100):
        chunk = keys[start:start + 100]
        values = await command("mget", chunk)
        if not isinstance(values, list) or len(values) != len(chunk):
            values = [None] * len(chunk)
        for value in values:
            try:
                result.append(json.loads(value) if value is not None else None)
            except (ValueError, TypeError):
                result.append(None)
    return result


async def set_json(key: str, value: Any, ttl_seconds: int) -> bool:
    """Return True only when the store confirmed the write."""
    return bool(await command("setex", key, ttl_seconds, json.dumps(value, separators=(",", ":"))))


def encode_body(body: bytes) -> str:
    return b64encode(body).decode("ascii")


def decode_body(body: str) -> bytes:
    return b64decode(body.encode("ascii"))

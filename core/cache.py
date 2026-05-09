from collections import OrderedDict
import json
from base64 import b64decode, b64encode
from threading import Lock
from time import monotonic
from typing import Any, Generic, TypeVar

from redis import asyncio as redis

from core.config import settings


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


_client: redis.Redis | None = None


def redis_enabled() -> bool:
    return bool(settings.redis_url)


def get_redis() -> redis.Redis | None:
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def get_json(key: str) -> dict[str, Any] | None:
    client = get_redis()
    if client is None:
        return None
    try:
        value = await client.get(key)
    except Exception:
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


async def set_json(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.setex(key, ttl_seconds, json.dumps(value, separators=(",", ":")))
    except Exception:
        return


def encode_body(body: bytes) -> str:
    return b64encode(body).decode("ascii")


def decode_body(body: str) -> bytes:
    return b64decode(body.encode("ascii"))

"""Source cache with request deduplication, owner-safe leases and stale fallback."""

import asyncio
import hashlib
import time
import uuid

from fastapi import HTTPException

from core.cache import command, get_json, redis_enabled, set_json
from core.runtime import once, state

RELEASE = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0"


def _serve_stale(cached):
    current = state.get()
    if current:
        current.meta["source"] = {"status": "stale", "updatedAt": cached.get("at")}
    return cached.get("data")


def _upstream_failure(exc: Exception) -> bool:
    """5xx and timeouts justify stale data. A 404 or 400 is a real answer."""
    if isinstance(exc, HTTPException):
        return exc.status_code >= 500
    return isinstance(exc, TimeoutError)


async def source(key, producer, ttl=300, stale_ttl=3600):
    key = "source:v1:" + hashlib.sha256(key.encode()).hexdigest()

    async def load():
        cached = await get_json(key)
        if not isinstance(cached, dict) or "data" not in cached:
            cached = None
        if cached and time.time() - cached.get("at", 0) < ttl:
            return cached["data"]

        store = redis_enabled()
        owner = uuid.uuid4().hex
        # Keyword arguments: redis-py's positional order is (ex, px, nx).
        locked = await command("set", key + ":lease", owner, ex=10, nx=True) if store else None
        if store and not locked:
            # Another invocation is refreshing this key, or the store is down.
            if cached:
                return _serve_stale(cached)
            # Bounded coalescing. A failed cache must not cause an unbounded wait.
            for _ in range(3):
                await asyncio.sleep(0.05)
                shared = await get_json(key)
                if isinstance(shared, dict) and "data" in shared:
                    return shared["data"]
        try:
            data = await producer()
        except (HTTPException, TimeoutError) as exc:
            if cached and _upstream_failure(exc):
                return _serve_stale(cached)
            raise
        else:
            await set_json(key, {"at": time.time(), "data": data}, stale_ttl)
            return data
        finally:
            if locked:
                await command("eval", RELEASE, 1, key + ":lease", owner)

    return await once(key, load)

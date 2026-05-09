import time
from dataclasses import dataclass

from core.cache import get_redis
from core.config import settings


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int = 0
    limited_by: str | None = None
    limit: int | None = None
    remaining: int | None = None
    reset_at: int | None = None


async def check_rate_limit(key: str, limit: int, window_seconds: int, label: str) -> RateLimitResult:
    client = get_redis()
    if client is None:
        return RateLimitResult(allowed=True)

    backoff_key = f"backoff:{key}"
    violations_key = f"violations:{key}"
    counter_key = f"rl:{key}"
    now = int(time.time())

    try:
        retry_after = await client.ttl(backoff_key)
        if retry_after and retry_after > 0:
            return RateLimitResult(False, retry_after, label, limit, 0, now + retry_after)

        count = await client.incr(counter_key)
        if count == 1:
            await client.expire(counter_key, window_seconds)

        ttl = await client.ttl(counter_key)
        reset_at = now + max(ttl, 0)
        remaining = max(limit - count, 0)
        if count <= limit:
            await client.delete(violations_key)
            return RateLimitResult(True, 0, label, limit, remaining, reset_at)

        violations = await client.incr(violations_key)
        await client.expire(violations_key, settings.rate_limit_backoff_max_seconds)
        backoff = min(
            settings.rate_limit_backoff_base_seconds * (2 ** max(violations - 1, 0)),
            settings.rate_limit_backoff_max_seconds,
        )
        await client.setex(backoff_key, backoff, "1")
        return RateLimitResult(False, backoff, label, limit, 0, now + backoff)
    except Exception:
        return RateLimitResult(allowed=True)


async def enforce_rate_limit() -> None:
    return None

import time
from dataclasses import dataclass

from core.cache import get_redis, upstash_command, upstash_enabled
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
    use_upstash = upstash_enabled()
    if client is None and not use_upstash:
        return RateLimitResult(allowed=True)

    backoff_key = f"backoff:{key}"
    violations_key = f"violations:{key}"
    counter_key = f"rl:{key}"
    now = int(time.time())

    try:
        retry_after = await upstash_command("TTL", backoff_key) if use_upstash else await client.ttl(backoff_key)
        if retry_after and retry_after > 0:
            return RateLimitResult(False, retry_after, label, limit, 0, now + retry_after)

        count = await upstash_command("INCR", counter_key) if use_upstash else await client.incr(counter_key)
        if count == 1:
            if use_upstash:
                await upstash_command("EXPIRE", counter_key, window_seconds)
            else:
                await client.expire(counter_key, window_seconds)

        ttl = await upstash_command("TTL", counter_key) if use_upstash else await client.ttl(counter_key)
        reset_at = now + max(ttl, 0)
        remaining = max(limit - count, 0)
        if count <= limit:
            if use_upstash:
                await upstash_command("DEL", violations_key)
            else:
                await client.delete(violations_key)
            return RateLimitResult(True, 0, label, limit, remaining, reset_at)

        violations = await upstash_command("INCR", violations_key) if use_upstash else await client.incr(violations_key)
        if use_upstash:
            await upstash_command("EXPIRE", violations_key, settings.rate_limit_backoff_max_seconds)
        else:
            await client.expire(violations_key, settings.rate_limit_backoff_max_seconds)
        backoff = min(
            settings.rate_limit_backoff_base_seconds * (2 ** max(violations - 1, 0)),
            settings.rate_limit_backoff_max_seconds,
        )
        if use_upstash:
            await upstash_command("SETEX", backoff_key, backoff, "1")
        else:
            await client.setex(backoff_key, backoff, "1")
        return RateLimitResult(False, backoff, label, limit, 0, now + backoff)
    except Exception:
        return RateLimitResult(allowed=True)


async def enforce_rate_limit() -> None:
    return None

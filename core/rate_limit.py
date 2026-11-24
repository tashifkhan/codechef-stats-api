"""Atomic counters and backoff, in one bounded store call per dimension."""

import time
from dataclasses import dataclass

from core.cache import command
from core.config import settings


RATE_SCRIPT = """
local backoff = redis.call('TTL', KEYS[1])
if backoff > 0 then return {0, backoff, 0} end
local count = redis.call('INCR', KEYS[2])
local ttl = redis.call('TTL', KEYS[2])
if count == 1 or ttl < 0 then
 redis.call('EXPIRE', KEYS[2], ARGV[2])
 ttl = tonumber(ARGV[2])
end
if count <= tonumber(ARGV[1]) then
 if count == 1 then redis.call('DEL', KEYS[3]) end
 return {1, ttl, tonumber(ARGV[1])-count}
end
local violations = redis.call('INCR', KEYS[3])
redis.call('EXPIRE', KEYS[3], ARGV[4])
local delay = math.min(tonumber(ARGV[3])*2^math.min(violations-1, 20), tonumber(ARGV[4]))
redis.call('SET', KEYS[1], '1', 'EX', delay)
return {0, delay, 0}
"""


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after: int = 0
    limited_by: str | None = None
    limit: int | None = None
    remaining: int | None = None
    reset_at: int | None = None


async def check_rate_limit(key, limit, window_seconds, label):
    result = await command(
        "eval", RATE_SCRIPT, 3, "backoff:" + key, "rl:" + key, "violations:" + key,
        limit, window_seconds, settings.rate_limit_backoff_base_seconds, settings.rate_limit_backoff_max_seconds,
    )
    if not isinstance(result, list) or len(result) != 3:
        return RateLimitResult(allowed=True)
    allowed, ttl, remaining = map(int, result)
    return RateLimitResult(bool(allowed), 0 if allowed else max(1, ttl), None if allowed else label, limit, remaining, int(time.time()) + max(0, ttl))


async def enforce_rate_limit():
    # Kept for existing dependency imports. Middleware owns the actual checks.
    return None

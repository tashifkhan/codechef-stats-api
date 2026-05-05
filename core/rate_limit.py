from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

from core.config import settings


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> int | None:
        now = monotonic()

        with self._lock:
            timestamps = self._requests[key]
            window_start = now - self.window_seconds

            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            if len(timestamps) >= self.limit:
                return max(1, ceil(self.window_seconds - (now - timestamps[0])))

            timestamps.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


rate_limiter = InMemoryRateLimiter(
    limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


async def enforce_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "anonymous"
    retry_after = rate_limiter.check(client_host)
    if retry_after is None:
        return

    raise HTTPException(
        status_code=429,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(retry_after)},
    )

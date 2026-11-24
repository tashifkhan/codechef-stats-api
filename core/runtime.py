"""Request-scoped clients, source deduplication, and a total request budget."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx
from starlette.responses import JSONResponse

from core.cache_control import _no_store

logger = logging.getLogger("stats_api")

# Total time for one request, under Vercel's 10s function limit.
REQUEST_BUDGET = 8.0


@dataclass
class RequestState:
    deadline: float
    client: httpx.AsyncClient
    tasks: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


state: ContextVar[RequestState | None] = ContextVar("stats_request", default=None)


def remaining(default=6.0):
    current = state.get()
    return max(0.001, current.deadline - time.monotonic()) if current else default


@asynccontextmanager
async def http_client():
    current = state.get()
    if current:
        yield current.client
    else:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            yield client


async def once(key, producer):
    current = state.get()
    if current is None:
        return await producer()
    if key not in current.tasks:
        current.tasks[key] = asyncio.create_task(producer())
    return await current.tasks[key]


class RequestBudgetMiddleware:
    def __init__(self, app, seconds=None):
        self.app, self.seconds = app, seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        budget = self.seconds or REQUEST_BUDGET
        started, sent, status = time.monotonic(), False, 500
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            current = RequestState(started + budget, client)
            token = state.set(current)

            async def tracked(message):
                nonlocal sent, status
                if message["type"] == "http.response.start":
                    sent, status = True, message["status"]
                    # Report partial or stale data in a header so the JSON shape stays the same.
                    if current.meta:
                        headers = _no_store(list(message.get("headers", [])))
                        headers.append((b"x-data-state", json.dumps(current.meta, separators=(",", ":")).encode()))
                        message["headers"] = headers
                await send(message)

            try:
                await asyncio.wait_for(self.app(scope, receive, tracked), budget)
            except asyncio.TimeoutError:
                if sent:
                    raise
                response = JSONResponse(
                    {"status": "error", "message": "Upstream request deadline exceeded"},
                    status_code=504, headers=_no_store({}),
                )
                await response(scope, receive, tracked)
            finally:
                pending = [task for task in current.tasks.values() if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                state.reset(token)
                logger.info("request route=%s status=%s elapsed_ms=%s", getattr(scope.get("route"), "path", "unmatched"), status, int((time.monotonic() - started) * 1000))

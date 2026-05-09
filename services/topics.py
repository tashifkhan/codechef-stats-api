"""Per-problem topic tag lookup for CodeChef solved problems.

CodeChef's scraped profile page (``services/profile_parser.py``) exposes only
a total solved count, not individual problem codes. Solved problem codes are
instead enumerated from the paginated "recent activity" endpoint that backs
the profile UI's submissions table, and each code's topic tags are then
fetched from CodeChef's public problem API. See ../CANONICAL_SCHEMA.md.
"""

import asyncio
from typing import List, Set

import httpx
from bs4 import BeautifulSoup

from core.cache import TTLCache
from core.config import settings
from models.canonical.stats import TopicCount

RECENT_URL = f"{settings.codechef_base_url}/recent/user"
PROBLEM_URL = f"{settings.codechef_base_url}/api/contests/PRACTICE/problems/{{code}}"

_CONCURRENCY = 10
_DEFAULT_MAX_PAGES = 40

# Problem tags are effectively static, so a long TTL avoids re-scraping the
# same problem across users/requests.
_tag_cache: TTLCache[str, List[str]] = TTLCache(ttl_seconds=6 * 60 * 60, max_size=4096)


async def _fetch_recent_page(handle: str, page: int) -> dict:
    headers = {
        "User-Agent": settings.user_agent,
        "X-Requested-With": "XMLHttpRequest",
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout, headers=headers) as client:
        response = await client.get(RECENT_URL, params={"user_handle": handle, "page": page})
    if response.status_code != 200:
        return {"max_page": 0, "content": ""}
    try:
        return response.json()
    except ValueError:
        return {"max_page": 0, "content": ""}


def _accepted_codes_from_page(content: str) -> Set[str]:
    soup = BeautifulSoup(content, "html.parser")
    codes: Set[str] = set()
    for row in soup.select("table.dataTable tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        link = cells[1].find("a")
        code = link.get_text(strip=True) if link else (cells[1].get("title") or "").strip()
        status_span = cells[2].find("span", title=True)
        verdict = (status_span.get("title") or "").strip().lower() if status_span else ""
        if code and verdict == "accepted":
            codes.add(code)
    return codes


async def _fetch_solved_codes(handle: str, max_pages: int = _DEFAULT_MAX_PAGES) -> Set[str]:
    first = await _fetch_recent_page(handle, 0)
    total_pages = min(int(first.get("max_page") or 0) or 1, max_pages)

    codes = _accepted_codes_from_page(first.get("content", ""))
    if total_pages <= 1:
        return codes

    remaining_pages = range(1, total_pages)
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def _bounded_fetch(page: int) -> dict:
        async with semaphore:
            return await _fetch_recent_page(handle, page)

    pages = await asyncio.gather(*(_bounded_fetch(p) for p in remaining_pages))
    for page in pages:
        codes |= _accepted_codes_from_page(page.get("content", ""))
    return codes


def _extract_tags(payload: dict) -> List[str]:
    tags = payload.get("computed_tags")
    if not tags:
        tags = payload.get("user_tags")
    return list(tags or [])


async def _fetch_problem_tags(code: str) -> List[str]:
    if not code:
        return []
    cached = _tag_cache.get(code)
    if cached is not None:
        return cached

    tags: List[str] = []
    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout, headers=headers) as client:
            response = await client.get(PROBLEM_URL.format(code=code))
        if response.status_code == 200:
            tags = _extract_tags(response.json())
    except (httpx.HTTPError, ValueError):
        tags = []

    _tag_cache.set(code, tags)
    return tags


async def build_topic_analysis(handle: str) -> List[TopicCount]:
    codes = await _fetch_solved_codes(handle)
    if not codes:
        return []

    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def _bounded_fetch(code: str) -> List[str]:
        async with semaphore:
            return await _fetch_problem_tags(code)

    results = await asyncio.gather(*(_bounded_fetch(code) for code in sorted(codes)))

    counts: dict[str, int] = {}
    for tags in results:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1

    return [
        TopicCount(topic=topic, count=count)
        for topic, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]


__all__ = ["build_topic_analysis"]

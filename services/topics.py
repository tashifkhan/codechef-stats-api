"""Per-problem topic tag lookup for CodeChef solved problems.

CodeChef's scraped profile page (``services/profile_parser.py``) exposes only
a total solved count, not individual problem codes. Solved problem codes are
instead enumerated from the paginated "recent activity" endpoint that backs
the profile UI's submissions table, and each code's topic tags are then
fetched from CodeChef's public problem API. See ../CANONICAL_SCHEMA.md.
"""

from typing import List, Set

import httpx
from bs4 import BeautifulSoup

from core.cache import TTLCache
from core.config import settings
from core.enrichment import read_topics
from core.runtime import http_client, remaining
from models.canonical.stats import TopicCount

RECENT_URL = f"{settings.codechef_base_url}/recent/user"
PROBLEM_URL = f"{settings.codechef_base_url}/api/contests/PRACTICE/problems/{{code}}"

# Per-call ceiling for history pages and problem metadata.
_UPSTREAM_TIMEOUT = 3.0

# Problem tags are effectively static, so a long TTL avoids re-scraping the
# same problem across users/requests.
_tag_cache: TTLCache[str, List[str]] = TTLCache(ttl_seconds=6 * 60 * 60, max_size=4096)


async def _fetch_recent_page(handle: str, page: int) -> dict:
    """One page of recent submissions. Raises on failure so a refresh retries."""
    headers = {
        "User-Agent": settings.user_agent,
        "X-Requested-With": "XMLHttpRequest",
    }
    async with http_client() as client:
        response = await client.get(RECENT_URL, params={"user_handle": handle, "page": page}, headers=headers, timeout=min(_UPSTREAM_TIMEOUT, remaining()))
    if response.status_code != 200:
        raise RuntimeError("CodeChef history unavailable")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("CodeChef history unavailable") from exc


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

    headers = {"User-Agent": settings.user_agent}
    # Failures raise so the refresh job retries. Never cache an empty list on failure.
    try:
        async with http_client() as client:
            response = await client.get(
                PROBLEM_URL.format(code=code), headers=headers, timeout=min(_UPSTREAM_TIMEOUT, remaining())
            )
        if response.status_code != 200:
            raise RuntimeError("CodeChef problem unavailable")
        tags = _extract_tags(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("CodeChef problem unavailable") from exc

    _tag_cache.set(code, tags)
    return tags


async def build_topic_analysis(handle: str) -> List[TopicCount]:
    """Cached topics, advanced by a bounded inline refresh slice when incomplete."""
    from services.refresh import handle as refresh_handler

    return [TopicCount(**row) for row in await read_topics(handle, refresh_handler)]


__all__ = ["build_topic_analysis"]

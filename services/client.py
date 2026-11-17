import httpx
from fastapi import HTTPException

from core.cache import TTLCache
from core.config import settings
from core.runtime import http_client, remaining
from core.source import source
from models.profile import CodeChefProfileResponse
from services.profile_parser import parse_codechef_profile

# Per-call ceiling for the profile page. The request budget is the total.
PROFILE_TIMEOUT = 4.0

profile_cache = TTLCache[str, CodeChefProfileResponse](
    ttl_seconds=settings.cache_ttl_seconds,
    max_size=settings.cache_max_entries,
)


async def _fetch_codechef_profile(handle: str) -> CodeChefProfileResponse:
    if not handle or handle == "favicon.ico":
        raise HTTPException(status_code=400, detail="Invalid handle")

    cached_profile = profile_cache.get(handle)
    if cached_profile is not None:
        return cached_profile

    url = f"{settings.codechef_base_url}/users/{handle}"
    headers = {"User-Agent": settings.user_agent}

    # httpx errors become HTTPExceptions so source() can fall back to stale
    # data, and so a dead upstream returns 504/503 instead of a 500.
    try:
        async with http_client() as client:
            response = await client.get(url, headers=headers, timeout=min(PROFILE_TIMEOUT, remaining()))
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="CodeChef timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="CodeChef is unreachable") from exc

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="CodeChef user not found")

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"CodeChef returned status {response.status_code}",
        )

    profile = parse_codechef_profile(response.text, response.status_code)
    profile_cache.set(handle, profile)
    return profile


async def fetch_codechef_profile(handle: str) -> CodeChefProfileResponse:
    """Profile through the shared source cache, with stale fallback on failure."""

    async def fetch():
        return (await _fetch_codechef_profile(handle)).model_dump(mode="json")

    data = await source("codechef:profile:" + handle, fetch)
    return CodeChefProfileResponse.model_validate(data)


__all__ = ["fetch_codechef_profile"]

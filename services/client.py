import httpx
from fastapi import HTTPException

from core.cache import TTLCache
from core.config import settings
from models.profile import CodeChefProfileResponse
from services.profile_parser import parse_codechef_profile


profile_cache = TTLCache[str, CodeChefProfileResponse](
    ttl_seconds=settings.cache_ttl_seconds,
    max_size=settings.cache_max_entries,
)


async def fetch_codechef_profile(handle: str) -> CodeChefProfileResponse:
    if not handle or handle == "favicon.ico":
        raise HTTPException(status_code=400, detail="Invalid handle")

    cached_profile = profile_cache.get(handle)
    if cached_profile is not None:
        return cached_profile

    url = f"{settings.codechef_base_url}/users/{handle}"
    headers = {"User-Agent": settings.user_agent}

    async with httpx.AsyncClient(timeout=settings.request_timeout, headers=headers) as client:
        response = await client.get(url)

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


__all__ = ["fetch_codechef_profile"]

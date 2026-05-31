import json
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core.cache import TTLCache
from core.config import settings
from models.codechef import CodeChefProfileInfo, CodeChefProfileInfoResponse, CodeChefProfileResponse


profile_cache = TTLCache[str, CodeChefProfileResponse](
    ttl_seconds=settings.cache_ttl_seconds,
    max_size=settings.cache_max_entries,
)


def _normalize_heatmap(data: dict | list) -> list[dict[str, str | int]]:
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]

    if isinstance(data, dict):
        return [{"date": key, "value": value} for key, value in data.items()]

    return []


def _extract_json_blob(page: str, variable_name: str) -> dict | list:
    pattern = rf"var\s+{re.escape(variable_name)}\s*=\s*(.*?);"
    match = re.search(pattern, page, re.DOTALL)
    if not match:
        return {} if variable_name == "userDailySubmissionsStats" else []

    try:
        return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return {} if variable_name == "userDailySubmissionsStats" else []


def _to_int(value: str | None) -> int | None:
    if not value:
        return None

    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _make_absolute(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http"):
        return url
    return f"{settings.codechef_base_url}{url}"


def _parse_total_solved(soup: "BeautifulSoup", page: str) -> int | None:
    """Extract the total number of problems solved from the profile page.

    CodeChef renders this as a "Total Problems Solved: N" heading. Falls back to
    a regex over the raw page if the DOM structure changes.
    """
    section = soup.select_one(".rating-data-section.problems-solved")
    if section:
        heading = section.find(["h3", "h5"], string=re.compile(r"Total Problems Solved", re.I))
        if heading:
            count = _to_int(heading.get_text(strip=True))
            if count is not None:
                return count

    match = re.search(r"Total Problems Solved\s*:?\s*(\d+)", page, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_codechef_profile(page: str, status_code: int) -> CodeChefProfileResponse:
    soup = BeautifulSoup(page, "html.parser")

    user_container = soup.select_one(".user-details-container")
    avatar = user_container.select_one("img") if user_container else None
    name_node = user_container.select_one("h1, h2, h3") if user_container else None

    rating_number = soup.select_one(".rating-number")
    rating_label = soup.select_one(".rating")
    country_flag = soup.select_one(".user-country-flag")
    country_name = soup.select_one(".user-country-name")
    ranks = soup.select(".rating-ranks strong")

    rating_data = _extract_json_blob(page, "all_rating")
    heatmap_data = _extract_json_blob(page, "userDailySubmissionsStats")

    highest_rating = None
    if rating_number and rating_number.parent:
        parent_text = rating_number.parent.get_text(" ", strip=True)
        highest_match = re.search(r"Highest\s+Rating\s+(\d+)", parent_text, re.IGNORECASE)
        if highest_match:
            highest_rating = int(highest_match.group(1))

    total_solved = _parse_total_solved(soup, page)

    return CodeChefProfileResponse(
        success=True,
        status=status_code,
        profile=_make_absolute(avatar.get("src") if avatar else None),
        name=name_node.get_text(strip=True) if name_node else None,
        currentRating=_to_int(rating_number.get_text(strip=True) if rating_number else None),
        highestRating=highest_rating,
        countryFlag=_make_absolute(country_flag.get("src") if country_flag else None),
        countryName=country_name.get_text(strip=True) if country_name else None,
        globalRank=_to_int(ranks[0].get_text(strip=True)) if len(ranks) > 0 else None,
        countryRank=_to_int(ranks[1].get_text(strip=True)) if len(ranks) > 1 else None,
        stars=rating_label.get_text(strip=True) if rating_label else "unrated",
        totalSolved=total_solved,
        heatMap=_normalize_heatmap(heatmap_data),
        ratingData=rating_data if isinstance(rating_data, list) else [],
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


async def fetch_profile_info(handle: str) -> CodeChefProfileInfoResponse:
    profile = await fetch_codechef_profile(handle)
    return CodeChefProfileInfoResponse(
        success=profile.success,
        status=profile.status,
        handle=handle,
        profile=CodeChefProfileInfo(
            profile=profile.profile,
            name=profile.name,
            currentRating=profile.currentRating,
            highestRating=profile.highestRating,
            countryFlag=profile.countryFlag,
            countryName=profile.countryName,
            globalRank=profile.globalRank,
            countryRank=profile.countryRank,
            stars=profile.stars,
        ),
    )

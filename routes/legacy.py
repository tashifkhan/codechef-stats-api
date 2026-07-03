from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.canonical import make_envelope
from services import canonical_mapper
from services.heatmap import fetch_heatmap
from services.heatmap_window import window_heatmap
from services.profile import fetch_codechef_profile, fetch_profile_info
from services.rating import fetch_rating_history


router = APIRouter(tags=["Legacy"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/profile/{handle}", deprecated=True)
async def legacy_profile(handle: str):
    legacy = await fetch_profile_info(handle)
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, canonical_mapper.profile_from(profile, handle), legacy=legacy)


@router.get("/heatmap/{handle}", deprecated=True)
async def legacy_heatmap(handle: str, view: str = "all", year: int | None = None):
    legacy = await fetch_heatmap(handle, view=view, year=year)
    profile = await fetch_codechef_profile(handle)
    heatmap = window_heatmap(canonical_mapper.heatmap_from(profile), view, year)
    return make_envelope(handle, heatmap, legacy=legacy)


@router.get("/rating/{handle}", deprecated=True)
async def legacy_rating(handle: str):
    legacy = await fetch_rating_history(handle)
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, canonical_mapper.rating_from(profile), legacy=legacy)

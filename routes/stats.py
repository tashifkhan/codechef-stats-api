from fastapi import APIRouter, Depends, Query

from core.rate_limit import enforce_rate_limit
from models.canonical import make_envelope
from services import canonical_mapper
from services.profile import fetch_codechef_profile
from services.stats_svg import stats_svg_response


router = APIRouter(tags=["Canonical"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}/stats/svg", summary="Stats SVG card")
async def get_stats_svg(
    handle: str,
    theme: str = Query("dark", description="Card theme: dark or light"),
):
    profile = await fetch_codechef_profile(handle)
    data = await canonical_mapper.stats_from(profile, handle)
    return stats_svg_response("codechef", handle, data, theme=theme)


@router.get("/{handle}/stats")
async def get_stats(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, await canonical_mapper.stats_from(profile, handle))

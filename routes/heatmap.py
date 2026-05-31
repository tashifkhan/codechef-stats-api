from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.unified import make_envelope
from services import unified_mapper
from services.heatmap import fetch_heatmap
from services.profile import fetch_codechef_profile


router = APIRouter(tags=["heatmap"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/heatmap/{handle}", deprecated=True)
async def get_heatmap(
    handle: str,
    view: str = "all",
    year: int | None = None,
):
    """Legacy alias. Prefer ``GET /{handle}/heatmap``."""
    legacy = await fetch_heatmap(handle, view=view, year=year)
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.heatmap_from(profile), legacy=legacy)

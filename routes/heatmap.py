from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.canonical import make_envelope
from services import canonical_mapper
from services.heatmap_window import window_heatmap
from services.profile import fetch_codechef_profile


router = APIRouter(tags=["Canonical"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}/heatmap")
async def get_heatmap(
    handle: str,
    view: str = "all",
    year: int | None = None,
):
    profile = await fetch_codechef_profile(handle)
    heatmap = window_heatmap(canonical_mapper.heatmap_from(profile), view, year)
    return make_envelope(handle, heatmap)

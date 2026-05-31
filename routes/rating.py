from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.unified import make_envelope
from services import unified_mapper
from services.profile import fetch_codechef_profile
from services.rating import fetch_rating_history


router = APIRouter(tags=["rating"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/rating/{handle}", deprecated=True)
async def get_rating_history(handle: str):
    """Legacy alias. Prefer ``GET /{handle}/rating``."""
    legacy = await fetch_rating_history(handle)
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.rating_from(profile), legacy=legacy)

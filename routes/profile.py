from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.unified import make_envelope
from services import unified_mapper
from services.profile import fetch_codechef_profile, fetch_profile_info


router = APIRouter(tags=["profile"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/profile/{handle}", deprecated=True)
async def get_profile(handle: str):
    """Legacy alias. Prefer ``GET /{handle}/profile``."""
    legacy = await fetch_profile_info(handle)
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.profile_from(profile, handle), legacy=legacy)

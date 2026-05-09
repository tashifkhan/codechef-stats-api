from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.canonical import make_envelope
from services import canonical_mapper
from services.profile import fetch_codechef_profile


router = APIRouter(tags=["Canonical"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}")
async def get_summary(handle: str):
    profile = await fetch_codechef_profile(handle)
    card = await canonical_mapper.card_from(profile, handle)
    return make_envelope(handle, canonical_mapper.summary_from(card))

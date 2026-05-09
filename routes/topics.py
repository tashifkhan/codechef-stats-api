from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.canonical import make_envelope
from services import canonical_mapper
from services.profile import fetch_codechef_profile


router = APIRouter(tags=["Canonical"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}/topics")
async def get_topics(handle: str):
    profile = await fetch_codechef_profile(handle)
    stats = await canonical_mapper.stats_from(profile, handle)
    return make_envelope(handle, stats.topicAnalysis)

"""Canonical unified endpoints shared across all stats services.

Adds the cross-platform endpoint surface for CodeChef
(``/{handle}``, ``/{handle}/profile``, ``/{handle}/stats``, ``/{handle}/contests``,
``/{handle}/rating``, ``/{handle}/heatmap``, ``/{handle}/badges``, ``/{handle}/card``)
on top of the legacy ``/profile/{handle}`` style aliases. See ../UNIFIED_SCHEMA.md.
"""

from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.unified import UnifiedBadges, make_envelope
from services import unified_mapper
from services.profile import fetch_codechef_profile

router = APIRouter(tags=["unified"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}/profile")
async def unified_profile(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.profile_from(profile, handle))


@router.get("/{handle}/stats")
async def unified_stats(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.stats_from(profile))


@router.get("/{handle}/contests")
async def unified_contests(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.contests_from(profile))


@router.get("/{handle}/rating")
async def unified_rating(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.rating_from(profile))


@router.get("/{handle}/heatmap")
async def unified_heatmap(handle: str):
    profile = await fetch_codechef_profile(handle)
    return make_envelope(handle, unified_mapper.heatmap_from(profile))


@router.get("/{handle}/badges")
async def unified_badges(handle: str):
    return make_envelope(handle, UnifiedBadges())


@router.get("/{handle}/card")
async def unified_card(handle: str):
    return make_envelope(handle, await unified_mapper.build_card(handle))


@router.get("/{handle}")
async def unified_summary(handle: str):
    profile = await fetch_codechef_profile(handle)
    card = unified_mapper.card_from(profile, handle)
    return make_envelope(handle, unified_mapper.summary_from(card))

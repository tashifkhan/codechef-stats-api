from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.canonical import Badges, make_envelope


router = APIRouter(tags=["Canonical"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/{handle}/badges")
async def get_badges(handle: str):
    return make_envelope(handle, Badges())

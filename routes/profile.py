from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.codechef import CodeChefProfileInfoResponse
from services.profile import fetch_profile_info


router = APIRouter(tags=["profile"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/profile/{handle}", response_model=CodeChefProfileInfoResponse)
async def get_profile(handle: str) -> CodeChefProfileInfoResponse:
    return await fetch_profile_info(handle)

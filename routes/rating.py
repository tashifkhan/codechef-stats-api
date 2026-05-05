from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.codechef import CodeChefRatingHistoryResponse
from services.rating import fetch_rating_history


router = APIRouter(tags=["rating"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/rating/{handle}", response_model=CodeChefRatingHistoryResponse)
async def get_rating_history(handle: str) -> CodeChefRatingHistoryResponse:
    return await fetch_rating_history(handle)

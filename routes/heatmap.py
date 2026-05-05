from fastapi import APIRouter, Depends

from core.rate_limit import enforce_rate_limit
from models.codechef import CodeChefHeatmapResponse
from services.heatmap import fetch_heatmap


router = APIRouter(tags=["heatmap"], dependencies=[Depends(enforce_rate_limit)])


@router.get("/heatmap/{handle}", response_model=CodeChefHeatmapResponse)
async def get_heatmap(handle: str) -> CodeChefHeatmapResponse:
    return await fetch_heatmap(handle)

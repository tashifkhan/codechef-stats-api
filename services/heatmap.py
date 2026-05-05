from models.codechef import CodeChefHeatmapResponse
from services.profile import fetch_codechef_profile


async def fetch_heatmap(handle: str) -> CodeChefHeatmapResponse:
    profile = await fetch_codechef_profile(handle)
    return CodeChefHeatmapResponse(
        success=profile.success,
        status=profile.status,
        handle=handle,
        heatMap=profile.heatMap,
    )

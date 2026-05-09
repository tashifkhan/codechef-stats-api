from models.rating import CodeChefRatingHistoryResponse
from services.profile import fetch_codechef_profile


async def fetch_rating_history(handle: str) -> CodeChefRatingHistoryResponse:
    profile = await fetch_codechef_profile(handle)
    return CodeChefRatingHistoryResponse(
        success=profile.success,
        status=profile.status,
        handle=handle,
        ratingData=profile.ratingData,
    )

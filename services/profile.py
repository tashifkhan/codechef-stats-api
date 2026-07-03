from models.profile import CodeChefProfileInfo, CodeChefProfileInfoResponse
from services.client import fetch_codechef_profile


async def fetch_profile_info(handle: str) -> CodeChefProfileInfoResponse:
    profile = await fetch_codechef_profile(handle)
    return CodeChefProfileInfoResponse(
        success=profile.success,
        status=profile.status,
        handle=handle,
        profile=CodeChefProfileInfo(
            profile=profile.profile,
            name=profile.name,
            currentRating=profile.currentRating,
            highestRating=profile.highestRating,
            countryFlag=profile.countryFlag,
            countryName=profile.countryName,
            globalRank=profile.globalRank,
            countryRank=profile.countryRank,
            stars=profile.stars,
            totalSolved=profile.totalSolved,
        ),
    )


__all__ = ["fetch_codechef_profile", "fetch_profile_info"]

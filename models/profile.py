from typing import Any
from pydantic import BaseModel, Field

class CodeChefProfileResponse(BaseModel):
    success: bool = True
    status: int
    profile: str | None = None
    name: str | None = None
    currentRating: int | None = None
    highestRating: int | None = None
    countryFlag: str | None = None
    countryName: str | None = None
    globalRank: int | None = None
    countryRank: int | None = None
    stars: str = "unrated"
    totalSolved: int | None = None
    heatMap: list[dict[str, Any]] = Field(default_factory=list)
    ratingData: list[Any] = Field(default_factory=list)

class CodeChefProfileInfo(BaseModel):
    profile: str | None = None
    name: str | None = None
    currentRating: int | None = None
    highestRating: int | None = None
    countryFlag: str | None = None
    countryName: str | None = None
    globalRank: int | None = None
    countryRank: int | None = None
    stars: str = "unrated"
    totalSolved: int | None = None

class CodeChefProfileInfoResponse(BaseModel):
    success: bool = True
    status: int
    handle: str
    profile: CodeChefProfileInfo

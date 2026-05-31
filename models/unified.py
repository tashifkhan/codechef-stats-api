"""Unified cross-platform stats schema (see ../UNIFIED_SCHEMA.md).

Pydantic implementation for the CodeChef (FastAPI) service. The wire format is
identical across all six services.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

PLATFORM = "codechef"
CATEGORY = "competitive"


class UnifiedSocial(BaseModel):
    github: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None


class UnifiedProfile(BaseModel):
    displayName: Optional[str] = None
    username: Optional[str] = None
    avatar: Optional[str] = None
    country: Optional[str] = None
    countryFlag: Optional[str] = None
    institution: Optional[str] = None
    company: Optional[str] = None
    bio: Optional[str] = None
    websites: List[str] = Field(default_factory=list)
    social: UnifiedSocial = Field(default_factory=UnifiedSocial)
    verified: bool = False


class TopicCount(BaseModel):
    topic: str
    count: int


class UnifiedStats(BaseModel):
    totalSolved: int = 0
    totalQuestions: Optional[int] = None
    acceptanceRate: Optional[float] = None
    byDifficulty: Dict[str, int] = Field(default_factory=dict)
    topicAnalysis: List[TopicCount] = Field(default_factory=list)


class ContestHistoryItem(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    timestamp: Optional[int] = None
    rating: Optional[float] = None
    ranking: Optional[int] = None
    problemsSolved: Optional[int] = None
    totalProblems: Optional[int] = None


class UnifiedContests(BaseModel):
    count: int = 0
    rating: Optional[float] = None
    maxRating: Optional[float] = None
    rank: Optional[str] = None
    globalRanking: Optional[int] = None
    topPercentage: Optional[float] = None
    history: List[ContestHistoryItem] = Field(default_factory=list)


class RatingPoint(BaseModel):
    timestamp: Optional[int] = None
    rating: Optional[float] = None
    contestName: Optional[str] = None


class UnifiedRating(BaseModel):
    current: Optional[float] = None
    max: Optional[float] = None
    history: List[RatingPoint] = Field(default_factory=list)


class HeatDay(BaseModel):
    date: str
    count: int
    level: int


class YearContribution(BaseModel):
    year: int
    totalSubmissions: int
    activeDays: int


class UnifiedHeatmap(BaseModel):
    totalSubmissions: int = 0
    totalActiveDays: int = 0
    currentStreak: int = 0
    longestStreak: int = 0
    maxDailySubmissions: int = 0
    firstActiveDate: Optional[str] = None
    lastActiveDate: Optional[str] = None
    dailyContributions: List[HeatDay] = Field(default_factory=list)
    yearlyContributions: List[YearContribution] = Field(default_factory=list)


class BadgeItem(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    level: Optional[str] = None


class UnifiedBadges(BaseModel):
    count: int = 0
    active: Optional[BadgeItem] = None
    list: List[BadgeItem] = Field(default_factory=list)


class UnifiedSummary(BaseModel):
    totalSolved: int = 0
    totalActiveDays: int = 0
    totalContests: int = 0
    currentRating: Optional[float] = None
    maxRating: Optional[float] = None
    rank: Optional[str] = None
    badgesCount: int = 0


class UnifiedCard(BaseModel):
    platform: str = PLATFORM
    username: str = ""
    category: str = CATEGORY
    profile: UnifiedProfile = Field(default_factory=UnifiedProfile)
    stats: UnifiedStats = Field(default_factory=UnifiedStats)
    contests: UnifiedContests = Field(default_factory=UnifiedContests)
    rating: UnifiedRating = Field(default_factory=UnifiedRating)
    heatmap: UnifiedHeatmap = Field(default_factory=UnifiedHeatmap)
    badges: UnifiedBadges = Field(default_factory=UnifiedBadges)


def make_envelope(
    username: str,
    data: Any,
    legacy: Optional[Any] = None,
    cached: bool = False,
    status: str = "success",
    message: str = "retrieved",
    platform: str = PLATFORM,
) -> Dict[str, Any]:
    """Wrap a payload in the unified envelope, preserving any legacy fields."""
    envelope: Dict[str, Any] = {}
    if legacy is not None:
        envelope.update(legacy.model_dump() if isinstance(legacy, BaseModel) else dict(legacy))
    envelope.setdefault("status", status)
    envelope.setdefault("message", message)
    envelope["platform"] = platform
    envelope["username"] = username
    envelope["cached"] = cached
    envelope["data"] = data.model_dump() if isinstance(data, BaseModel) else data
    return envelope

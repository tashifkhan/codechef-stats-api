from typing import List, Optional

from pydantic import BaseModel, Field


class ContestHistoryItem(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    timestamp: Optional[int] = None
    rating: Optional[float] = None
    ranking: Optional[int] = None
    problemsSolved: Optional[int] = None
    totalProblems: Optional[int] = None


class Contests(BaseModel):
    count: int = 0
    rating: Optional[float] = None
    maxRating: Optional[float] = None
    rank: Optional[str] = None
    globalRanking: Optional[int] = None
    topPercentage: Optional[float] = None
    history: List[ContestHistoryItem] = Field(default_factory=list)

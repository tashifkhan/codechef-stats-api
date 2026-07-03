from typing import List, Optional

from pydantic import BaseModel, Field


class RatingPoint(BaseModel):
    timestamp: Optional[int] = None
    rating: Optional[float] = None
    contestName: Optional[str] = None


class Rating(BaseModel):
    current: Optional[float] = None
    max: Optional[float] = None
    history: List[RatingPoint] = Field(default_factory=list)

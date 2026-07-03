from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TopicCount(BaseModel):
    topic: str
    count: int


class Stats(BaseModel):
    totalSolved: int = 0
    totalQuestions: Optional[int] = None
    acceptanceRate: Optional[float] = None
    byDifficulty: Dict[str, int] = Field(default_factory=dict)
    topicAnalysis: List[TopicCount] = Field(default_factory=list)

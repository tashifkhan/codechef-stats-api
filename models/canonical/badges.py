from typing import List, Optional

from pydantic import BaseModel, Field


class BadgeItem(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    level: Optional[str] = None


class Badges(BaseModel):
    count: int = 0
    active: Optional[BadgeItem] = None
    list: List[BadgeItem] = Field(default_factory=list)

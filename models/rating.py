from typing import Any
from pydantic import BaseModel, Field

class CodeChefRatingHistoryResponse(BaseModel):
    success: bool = True
    status: int
    handle: str
    ratingData: list[Any] = Field(default_factory=list)

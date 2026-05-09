from typing import Any
from pydantic import BaseModel, Field

class CodeChefHeatmapResponse(BaseModel):
    success: bool = True
    status: int
    handle: str
    view: str = "all"
    year: int | None = None
    availableYears: list[int] = Field(default_factory=list)
    firstActiveDate: str | None = None
    lastActiveDate: str | None = None
    heatMap: list[dict[str, Any]] = Field(default_factory=list)

from pydantic import BaseModel

class ErrorResponse(BaseModel):
    success: bool = False
    status: int
    error: str

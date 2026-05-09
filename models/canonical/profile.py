from typing import List, Optional

from pydantic import BaseModel, Field


class Social(BaseModel):
    github: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None


class Profile(BaseModel):
    displayName: Optional[str] = None
    username: Optional[str] = None
    avatar: Optional[str] = None
    country: Optional[str] = None
    countryFlag: Optional[str] = None
    institution: Optional[str] = None
    company: Optional[str] = None
    bio: Optional[str] = None
    websites: List[str] = Field(default_factory=list)
    social: Social = Field(default_factory=Social)
    verified: bool = False

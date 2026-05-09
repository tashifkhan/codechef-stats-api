from pydantic import BaseModel, Field

from models.canonical.badges import Badges
from models.canonical.constants import CATEGORY, PLATFORM
from models.canonical.contests import Contests
from models.canonical.heatmap import Heatmap
from models.canonical.profile import Profile
from models.canonical.rating import Rating
from models.canonical.stats import Stats


class Card(BaseModel):
    platform: str = PLATFORM
    username: str = ""
    category: str = CATEGORY
    profile: Profile = Field(default_factory=Profile)
    stats: Stats = Field(default_factory=Stats)
    contests: Contests = Field(default_factory=Contests)
    rating: Rating = Field(default_factory=Rating)
    heatmap: Heatmap = Field(default_factory=Heatmap)
    badges: Badges = Field(default_factory=Badges)

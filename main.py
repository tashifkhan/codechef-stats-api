from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.middleware import CacheRateLimitMiddleware
from routes.badges import router as badges_router
from routes.contests import router as contests_router
from routes.docs import router as docs_router
from routes.heatmap import router as heatmap_router
from routes.legacy import router as legacy_router
from routes.profile import router as profile_router
from routes.rating import router as rating_router
from routes.stats import router as stats_router
from routes.summary import router as summary_router
from routes.topics import router as topics_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI REST API for CodeChef profile data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you might want to restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CacheRateLimitMiddleware, platform="codechef")

app.include_router(docs_router)
app.include_router(profile_router)
app.include_router(stats_router)
app.include_router(contests_router)
app.include_router(rating_router)
app.include_router(heatmap_router)
app.include_router(topics_router)
app.include_router(badges_router)


app.include_router(summary_router)
app.include_router(legacy_router)

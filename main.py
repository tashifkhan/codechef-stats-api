from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from core.config import settings
from models.templates import dashboard_template, html_template
from routes.heatmap import router as heatmap_router
from routes.profile import router as profile_router
from routes.rating import router as rating_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI REST API for CodeChef profile data.",
)
app.include_router(profile_router)
app.include_router(heatmap_router)
app.include_router(rating_router)


@app.get("/", tags=["meta"], response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return HTMLResponse(content=html_template)


@app.get("/dashboard", tags=["meta"], response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(content=dashboard_template)

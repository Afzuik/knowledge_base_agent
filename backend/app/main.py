"""Minimal API entry point; business features are intentionally not implemented."""

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Knowledge Workbench", version="0.1.0")
    app.include_router(api_router, prefix="/api")

    assets = settings.frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend():
        index = settings.frontend_dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Frontend not built. Run npm ci && npm run build in frontend/.",
                "health_url": "/api/health",
            },
        )

    return app


app = create_app()

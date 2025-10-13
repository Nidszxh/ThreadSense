from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.threads import router as threads_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )
    app.include_router(health_router, prefix="/api")
    app.include_router(threads_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    return app


app = create_app()

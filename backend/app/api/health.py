from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

router = APIRouter(tags=["health"])


def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url)


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    checks: dict = {}
    ok = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
        ok = False

    try:
        _redis_client().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        ok = False

    checks["status"] = "ok" if ok else "degraded"
    return JSONResponse(status_code=200 if ok else 503, content=checks)

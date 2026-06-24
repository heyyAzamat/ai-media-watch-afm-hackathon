"""GET /health — liveness + dependency checks."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from .... import __version__
from ....config import get_settings
from ....db.base import get_session
from ....domain.schemas import HealthResponse

router = APIRouter()


def _check_db() -> str:
    try:
        session = get_session()
        try:
            session.execute(text("SELECT 1"))
            return "ok"
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _check_redis() -> str:
    try:
        import redis

        client = redis.Redis.from_url(get_settings().redis_url)
        client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


@router.get("/health", response_model=HealthResponse, summary="Health check", tags=["meta"])
def health() -> HealthResponse:
    settings = get_settings()
    checks = {
        "database": _check_db(),
        "redis": _check_redis(),
        "ocr_provider": settings.ocr_provider,
        "speech_provider": settings.speech_provider,
        "visual_provider": settings.visual_provider,
        "reasoning_model": settings.reasoning_model,
    }
    overall = "ok" if checks["database"] == "ok" else "degraded"
    return HealthResponse(status=overall, version=__version__, env=settings.env, checks=checks)

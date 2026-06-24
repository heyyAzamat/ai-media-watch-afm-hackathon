"""FastAPI application factory + entrypoint.

The API layer is intentionally thin: it validates input, persists job rows,
enqueues work and reads results. All business logic lives in the engine.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.errors import register_error_handlers
from .api.v1.endpoints.health import router as health_router
from .api.v1.router import api_router
from .config import get_settings
from .db.base import init_engine
from .logging_config import configure_logging, get_logger
from .utils.ids import new_request_id

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    settings.ensure_dirs()
    init_engine()
    log.info("api.startup", env=settings.env, version=__version__)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Media Watch",
        version=__version__,
        description="Explainable multimodal video risk analysis platform.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_id(request: Request, call_next):  # noqa: ANN001, ANN202
        request.state.request_id = request.headers.get("X-Request-ID", new_request_id())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    register_error_handlers(app)

    # /health at root, everything else under the versioned prefix.
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", tags=["meta"], summary="Service banner")
    async def root() -> dict:
        return {
            "service": "ai-media-watch",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "api": settings.api_prefix,
            "app": "/app/",
        }

    # Serve the ScamShield web app (PWA) at /app — same origin as the API, so the
    # phone hits one URL and there are no CORS concerns. html=True serves
    # index.html at /app/.
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    if frontend_dir.is_dir():
        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="app")

    # Pre-downloaded demo clips served as direct-media URLs (e.g. /clips/x.mp4),
    # so a stage demo never depends on live TikTok/YouTube downloads. Paste
    # <host>/clips/<file>.mp4 into the app and /check fetches it via the
    # direct-media path (no yt-dlp).
    clips_dir = Path(__file__).resolve().parents[2] / "storage" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/clips", StaticFiles(directory=str(clips_dir)), name="clips")

    return app


app = create_app()


def run() -> None:
    """Console entrypoint: ``aimw-api``."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "aimw.main:app",
        host="0.0.0.0",  # noqa: S104 - container service
        port=8000,
        reload=settings.env == "development",
    )


if __name__ == "__main__":
    run()

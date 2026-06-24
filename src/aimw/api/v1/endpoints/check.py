"""POST /check — synchronous one-shot analysis for the consumer app.

Downloads a video from a platform URL, runs the analysis engine in-process
(no Celery/DB), and returns the explainable report directly. Built for the
'paste a link, get a verdict' flow. The async /analyze path is unaffected.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Form, status

from ....config import get_settings
from ....logging_config import get_logger
from ....services.downloader import DownloadError, download_media
from ....services.scam_model import ScamVerdict, build_scam_model
from ....utils.ids import new_video_id
from ...errors import APIError

router = APIRouter()
log = get_logger(__name__)

# Build the configured model once at import. The default ("orchestrator") wraps
# the existing pipeline; swap to the ML model via AIMW_SCAM_MODEL_PROVIDER=ml.
_model = build_scam_model()


@router.post("/check", response_model=ScamVerdict,
             summary="Synchronously analyze a video URL and return a scam verdict")
async def check(source_url: str = Form(...)) -> ScamVerdict:
    if not source_url.strip():
        raise APIError("source_url is required")

    settings = get_settings()
    settings.ensure_dirs()
    video_id = new_video_id()

    try:
        path = await asyncio.to_thread(
            download_media, source_url, video_id, settings.uploads_dir
        )
    except DownloadError as exc:
        raise APIError(
            "failed to download video from URL",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    verdict = await asyncio.to_thread(_model.analyze, str(path))
    log.info("check.done", video_id=video_id, risk_score=verdict.risk_score,
             category=verdict.category, model=_model.name)
    return verdict

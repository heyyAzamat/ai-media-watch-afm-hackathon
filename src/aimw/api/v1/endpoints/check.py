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
from ....orchestration.orchestrator import AnalysisOrchestrator
from ....services.downloader import DownloadError, download_media
from ....utils.ids import new_video_id
from ...errors import APIError

router = APIRouter()
log = get_logger(__name__)

# Build once at import (wires the DI container / loads provider config).
_orchestrator = AnalysisOrchestrator()


@router.post("/check", summary="Synchronously analyze a video URL and return a verdict")
async def check(source_url: str = Form(...)):
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

    prepared = await asyncio.to_thread(
        _orchestrator.prepare,
        video_id=video_id,
        path=str(path),
        filename=path.name,
        source_url=source_url,
    )
    artifacts = await _orchestrator.run(prepared)
    log.info("check.done", video_id=video_id, risk_score=artifacts.report.risk_score)
    return artifacts.report

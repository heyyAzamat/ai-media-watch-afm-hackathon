"""POST /analyze — accept an upload (or media URL) and enqueue analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from ....config import get_settings
from ....db.repositories import JobRepository, VideoRepository
from ....domain.enums import JobStatus
from ....domain.models import VideoMetadata
from ....domain.schemas import JobAccepted
from ....logging_config import get_logger
from ....utils.ids import new_job_id, new_video_id
from ....workers.tasks import analyze_video_task
from ...deps import get_db
from ...errors import APIError

router = APIRouter()
log = get_logger(__name__)


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lstrip(".").lower()
    allowed = get_settings().allowed_extension_set
    if ext not in allowed:
        raise APIError(
            f"unsupported file type '.{ext}'",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"allowed: {sorted(allowed)}",
        )
    return ext


async def _save_upload(upload: UploadFile, video_id: str) -> str:
    settings = get_settings()
    settings.ensure_dirs()
    ext = _validate_extension(upload.filename or "video.mp4")
    dest = settings.uploads_dir / f"{video_id}.{ext}"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    with dest.open("wb") as fh:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                fh.close()
                dest.unlink(missing_ok=True)
                raise APIError(
                    "file too large",
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"max {settings.max_upload_mb} MB",
                )
            fh.write(chunk)
    return str(dest)


async def _download_url(url: str, video_id: str) -> str:
    """Download a *direct* media URL. Platform scraping (TikTok/IG/etc.) is a
    documented integration point (plug a yt-dlp-based downloader here)."""
    settings = get_settings()
    settings.ensure_dirs()
    dest = settings.uploads_dir / f"{video_id}.mp4"
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with dest.open("wb") as fh:
                    async for chunk in resp.aiter_bytes(1024 * 1024):
                        fh.write(chunk)
    except Exception as exc:  # noqa: BLE001
        raise APIError(
            "failed to fetch source_url",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return str(dest)


@router.post(
    "/analyze",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a video for analysis",
)
async def analyze(
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
    source_platform: str = Form(default="upload"),
    webhook_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> JobAccepted:
    if file is None and not source_url:
        raise APIError("provide either a file upload or source_url")

    video_id = new_video_id()
    job_id = new_job_id()

    if file is not None:
        path = await _save_upload(file, video_id)
        filename = file.filename or f"{video_id}.mp4"
    else:
        path = await _download_url(source_url, video_id)  # type: ignore[arg-type]
        filename = f"{video_id}.mp4"

    # Stub video row so the job FK is satisfied; the worker upserts real metadata.
    VideoRepository(db).upsert(
        VideoMetadata(
            video_id=video_id,
            filename=filename,
            source_platform=source_platform,
            source_url=source_url,
            duration_seconds=0.0,
            fps=0.0,
            width=0,
            height=0,
            size_bytes=0,
        ),
        storage_path=path,
    )
    JobRepository(db).create(job_id=job_id, video_id=video_id, webhook_url=webhook_url)
    # Commit so the job row is visible to the worker before we enqueue the task.
    db.commit()

    analyze_video_task.apply_async(
        kwargs={
            "job_id": job_id,
            "video_id": video_id,
            "path": path,
            "filename": filename,
            "source_platform": source_platform,
            "source_url": source_url,
            "webhook_url": webhook_url,
        }
    )
    log.info("analyze.enqueued", job_id=job_id, video_id=video_id)

    return JobAccepted(
        job_id=job_id,
        video_id=video_id,
        status=JobStatus.QUEUED,
        poll_url=f"{get_settings().api_prefix}/status/{job_id}",
        created_at=datetime.now(timezone.utc),
    )

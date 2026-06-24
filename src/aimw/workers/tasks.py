"""Celery tasks — the glue between the queue, the engine and persistence.

The task owns persistence and job-status transitions; the orchestrator owns the
analysis. The orchestrator's parallel phase (asyncio.gather) runs inside a fresh
event loop per task via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio

from ..config import get_settings
from ..db.base import init_engine, session_scope
from ..db.repositories import (
    ArtifactRepository,
    AuditRepository,
    JobRepository,
    VideoRepository,
)
from ..domain.enums import JobStatus
from ..domain.models import AnalysisArtifacts, PreparedVideo
from ..logging_config import get_logger
from ..orchestration.orchestrator import AnalysisOrchestrator
from ..utils.webhooks import deliver_webhook
from .celery_app import celery_app

log = get_logger(__name__)
init_engine()


def _set_status(job_id: str, status: JobStatus, progress: int | None = None,
                detail: str | None = None, error: str | None = None) -> None:
    with session_scope() as s:
        JobRepository(s).update_status(
            job_id, status=status, progress=progress, detail=detail, error=error
        )


@celery_app.task(name="aimw.analyze_video", bind=True, max_retries=0)
def analyze_video_task(
    self,  # noqa: ANN001
    *,
    job_id: str,
    video_id: str,
    path: str,
    filename: str,
    source_platform: str = "upload",
    source_url: str | None = None,
    webhook_url: str | None = None,
) -> dict:
    log.info("task.start", job_id=job_id, video_id=video_id)
    orchestrator = AnalysisOrchestrator()
    settings = get_settings()

    try:
        # ── Steps 1-3: prepare (ingestion + scenes + frames + audio) ─────────
        _set_status(job_id, JobStatus.INGESTING, 10, "probing + scene detection")
        prepared: PreparedVideo = orchestrator.prepare(
            video_id=video_id,
            path=path,
            filename=filename,
            source_platform=source_platform,
            source_url=source_url,
        )
        with session_scope() as s:
            VideoRepository(s).upsert(prepared.metadata, storage_path=path)
            ArtifactRepository(s).save_prepared(prepared)
            AuditRepository(s).record(
                stage="prepare", message="prepared video", video_id=video_id, job_id=job_id,
                payload={"scenes": len(prepared.scenes), "frames": len(prepared.frames)},
            )
        _set_status(job_id, JobStatus.EXTRACTING, 30, "frames extracted")

        # ── Steps 4-10: parallel analysis + fusion + judge + report ──────────
        def progress(status: JobStatus, pct: int, detail: str) -> None:
            _set_status(job_id, status, pct, detail)

        artifacts: AnalysisArtifacts = asyncio.run(orchestrator.run(prepared, progress))

        # ── persist everything (audit trail) ────────────────────────────────
        with session_scope() as s:
            ArtifactRepository(s).save_artifacts(video_id, artifacts)
            AuditRepository(s).record(
                stage="report", message="analysis complete", video_id=video_id, job_id=job_id,
                payload={
                    "risk_score": artifacts.report.risk_score,
                    "category": artifacts.report.category.value,
                    "fallback_used": artifacts.report.fallback_used,
                },
            )

        _set_status(job_id, JobStatus.COMPLETED, 100, "done")

        # ── webhook ──────────────────────────────────────────────────────────
        if webhook_url:
            deliver_webhook(
                webhook_url,
                {"job_id": job_id, "status": "completed",
                 "report": artifacts.report.model_dump(mode="json")},
            )

        log.info("task.done", job_id=job_id, risk_score=artifacts.report.risk_score)
        return {"job_id": job_id, "video_id": video_id, "risk_score": artifacts.report.risk_score}

    except Exception as exc:  # noqa: BLE001
        log.error("task.failed", job_id=job_id, error=str(exc))
        _set_status(job_id, JobStatus.FAILED, error=str(exc))
        with session_scope() as s:
            AuditRepository(s).record(
                stage="error", message=str(exc), video_id=video_id, job_id=job_id
            )
        if webhook_url:
            deliver_webhook(webhook_url, {"job_id": job_id, "status": "failed", "error": str(exc)})
        raise

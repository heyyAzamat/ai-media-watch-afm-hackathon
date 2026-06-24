"""GET /status/{job_id} — job lifecycle + progress."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....db.repositories import JobRepository
from ....domain.enums import JobStatus
from ....domain.schemas import JobStatusResponse
from ...deps import get_job_repo
from ...errors import NotFoundError

router = APIRouter()


@router.get("/status/{job_id}", response_model=JobStatusResponse, summary="Job status")
def get_status(job_id: str, jobs: JobRepository = Depends(get_job_repo)) -> JobStatusResponse:
    job = jobs.get(job_id)
    if job is None:
        raise NotFoundError(f"job '{job_id}' not found")
    return JobStatusResponse(
        job_id=job.job_id,
        video_id=job.video_id,
        status=JobStatus(job.status),
        progress=job.progress,
        stage_detail=job.stage_detail,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )

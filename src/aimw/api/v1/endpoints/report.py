"""GET /report/{id} and GET /analysis/{id} — the full report.

``id`` may be a video_id or a job_id (resolved transparently).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....db.repositories import ArtifactRepository, JobRepository
from ....domain.enums import JobStatus
from ....domain.models import AnalysisReport
from ....domain.schemas import AnalysisResponse, ReportResponse
from ...deps import get_artifact_repo, get_job_repo
from ...errors import NotFoundError

router = APIRouter()


def _resolve_video_id(identifier: str, jobs: JobRepository) -> str:
    job = jobs.get(identifier)
    return job.video_id if job else identifier


@router.get("/report/{identifier}", response_model=ReportResponse, summary="Full report")
def get_report(
    identifier: str,
    artifacts: ArtifactRepository = Depends(get_artifact_repo),
    jobs: JobRepository = Depends(get_job_repo),
) -> ReportResponse:
    video_id = _resolve_video_id(identifier, jobs)
    row = artifacts.get_report(video_id)
    if row is None:
        raise NotFoundError(f"no report for '{identifier}'")
    report = AnalysisReport.model_validate(row.report)
    return ReportResponse(video_id=video_id, report=report, metadata=report.metadata)


@router.get("/analysis/{identifier}", response_model=AnalysisResponse, summary="Analysis result")
def get_analysis(
    identifier: str,
    artifacts: ArtifactRepository = Depends(get_artifact_repo),
    jobs: JobRepository = Depends(get_job_repo),
) -> AnalysisResponse:
    job = jobs.get(identifier)
    video_id = job.video_id if job else identifier
    row = artifacts.get_report(video_id)
    status = JobStatus(job.status) if job else (
        JobStatus.COMPLETED if row else JobStatus.QUEUED
    )
    report = AnalysisReport.model_validate(row.report) if row else None
    if report is None and job is None:
        raise NotFoundError(f"no analysis for '{identifier}'")
    return AnalysisResponse(
        job_id=job.job_id if job else identifier, status=status, report=report
    )

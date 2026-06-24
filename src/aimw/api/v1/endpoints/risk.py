"""GET /risk/{id} — compact risk verdict (score / category / confidence)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....db.repositories import ArtifactRepository, JobRepository
from ....domain.enums import RiskCategory
from ....domain.schemas import RiskResponse
from ...deps import get_artifact_repo, get_job_repo
from ...errors import NotFoundError

router = APIRouter()


@router.get("/risk/{identifier}", response_model=RiskResponse, summary="Risk verdict")
def get_risk(
    identifier: str,
    artifacts: ArtifactRepository = Depends(get_artifact_repo),
    jobs: JobRepository = Depends(get_job_repo),
) -> RiskResponse:
    job = jobs.get(identifier)
    video_id = job.video_id if job else identifier
    row = artifacts.get_report(video_id)
    if row is None:
        raise NotFoundError(f"no risk verdict for '{identifier}'")
    return RiskResponse(
        video_id=video_id,
        risk_score=row.risk_score,
        category=RiskCategory(row.category),
        confidence=row.confidence,
        summary=row.summary,
        fallback_used=row.fallback_used,
    )

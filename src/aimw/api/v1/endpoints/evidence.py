"""GET /evidence/{id} — the per-modality evidence bundle (visual/audio/ocr)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....db.repositories import ArtifactRepository, JobRepository
from ....domain.models import AnalysisReport
from ....domain.schemas import EvidenceResponse
from ...deps import get_artifact_repo, get_job_repo
from ...errors import NotFoundError

router = APIRouter()


@router.get("/evidence/{identifier}", response_model=EvidenceResponse, summary="Evidence bundle")
def get_evidence(
    identifier: str,
    artifacts: ArtifactRepository = Depends(get_artifact_repo),
    jobs: JobRepository = Depends(get_job_repo),
) -> EvidenceResponse:
    job = jobs.get(identifier)
    video_id = job.video_id if job else identifier
    row = artifacts.get_report(video_id)
    if row is None:
        raise NotFoundError(f"no evidence for '{identifier}'")
    report = AnalysisReport.model_validate(row.report)
    return EvidenceResponse(video_id=video_id, evidence=report.evidence)

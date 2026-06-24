"""GET /timeline/{id} — suspicious-moments timeline + Evidence Player markers."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ....db.repositories import ArtifactRepository, JobRepository
from ....domain.models import EvidencePlayerMarker, TimelineEvent
from ....domain.schemas import TimelineResponse
from ...deps import get_artifact_repo, get_job_repo
from ...errors import NotFoundError

router = APIRouter()


@router.get("/timeline/{identifier}", response_model=TimelineResponse, summary="Risk timeline")
def get_timeline(
    identifier: str,
    artifacts: ArtifactRepository = Depends(get_artifact_repo),
    jobs: JobRepository = Depends(get_job_repo),
) -> TimelineResponse:
    job = jobs.get(identifier)
    video_id = job.video_id if job else identifier
    row = artifacts.get_timeline(video_id)
    if row is None:
        raise NotFoundError(f"no timeline for '{identifier}'")
    return TimelineResponse(
        video_id=video_id,
        events=[TimelineEvent.model_validate(e) for e in row.events],
        player_markers=[EvidencePlayerMarker.model_validate(m) for m in row.markers],
    )

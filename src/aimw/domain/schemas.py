"""API request/response schemas (the public contract).

Kept separate from the internal :mod:`domain.models` so the wire contract can
evolve independently from the engine's value objects.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from .enums import JobStatus, RiskCategory
from .models import (
    AnalysisReport,
    EvidenceBundle,
    EvidencePlayerMarker,
    TimelineEvent,
    VideoMetadata,
)


class AnalyzeRequest(BaseModel):
    """Request body for analysing a remote video URL (JSON form of POST /analyze)."""

    model_config = ConfigDict(extra="forbid")

    source_url: AnyHttpUrl | None = Field(
        default=None,
        description="URL of a TikTok / Reels / Shorts / Telegram / Facebook video.",
    )
    source_platform: str = Field(default="upload")
    webhook_url: AnyHttpUrl | None = Field(
        default=None, description="Optional URL POSTed with the final report on completion."
    )
    metadata: dict[str, str] = Field(default_factory=dict)


class JobAccepted(BaseModel):
    """202 response returned immediately by POST /analyze."""

    job_id: str
    video_id: str
    status: JobStatus = JobStatus.QUEUED
    poll_url: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    video_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage_detail: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class RiskResponse(BaseModel):
    video_id: str
    risk_score: int = Field(ge=0, le=100)
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    summary: str
    fallback_used: bool = False


class TimelineResponse(BaseModel):
    video_id: str
    events: list[TimelineEvent]
    player_markers: list[EvidencePlayerMarker]


class EvidenceResponse(BaseModel):
    video_id: str
    evidence: EvidenceBundle


class AnalysisResponse(BaseModel):
    """Full report — the OUTPUT FORMAT contract from the spec."""

    job_id: str
    status: JobStatus
    report: AnalysisReport | None = None


class ReportResponse(BaseModel):
    video_id: str
    report: AnalysisReport
    metadata: VideoMetadata | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    env: str
    checks: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None

"""Repository layer — the only place that talks SQLAlchemy ORM.

Services and the API depend on these repositories (injected), never on ORM
classes directly, keeping persistence swappable and the domain pure.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.enums import JobStatus
from ..domain.models import (
    AnalysisArtifacts,
    PreparedVideo,
    VideoMetadata,
    raw_payload,
)
from .models import (
    AuditLogORM,
    EvidenceGraphORM,
    FrameORM,
    JobORM,
    OcrResultORM,
    ReportORM,
    SceneORM,
    TimelineORM,
    TranscriptORM,
    VideoORM,
    VisualDetectionORM,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(self, *, stage: str, message: str = "", video_id: str | None = None,
               job_id: str | None = None, payload: dict | None = None) -> None:
        self._s.add(
            AuditLogORM(
                video_id=video_id,
                job_id=job_id,
                stage=stage,
                message=message,
                payload=payload or {},
            )
        )


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, *, job_id: str, video_id: str, webhook_url: str | None) -> JobORM:
        job = JobORM(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.QUEUED.value,
            progress=0,
            webhook_url=webhook_url,
        )
        self._s.add(job)
        return job

    def get(self, job_id: str) -> JobORM | None:
        return self._s.get(JobORM, job_id)

    def get_by_video(self, video_id: str) -> JobORM | None:
        stmt = (
            select(JobORM)
            .where(JobORM.video_id == video_id)
            .order_by(JobORM.created_at.desc())
            .limit(1)
        )
        return self._s.scalars(stmt).first()

    def update_status(
        self,
        job_id: str,
        *,
        status: JobStatus,
        progress: int | None = None,
        detail: str | None = None,
        error: str | None = None,
    ) -> JobORM | None:
        job = self.get(job_id)
        if job is None:
            return None
        job.status = status.value
        if progress is not None:
            job.progress = progress
        if detail is not None:
            job.stage_detail = detail
        if error is not None:
            job.error = error
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = _utcnow()
            if status == JobStatus.COMPLETED:
                job.progress = 100
        return job


class VideoRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def upsert(self, metadata: VideoMetadata, storage_path: str | None = None) -> VideoORM:
        video = self._s.get(VideoORM, metadata.video_id)
        if video is None:
            video = VideoORM(video_id=metadata.video_id)
            self._s.add(video)
        video.filename = metadata.filename
        video.source_platform = metadata.source_platform
        video.source_url = metadata.source_url
        video.duration_seconds = metadata.duration_seconds
        video.fps = metadata.fps
        video.width = metadata.width
        video.height = metadata.height
        video.size_bytes = metadata.size_bytes
        video.container = metadata.container
        video.storage_path = storage_path
        video.uploaded_at = metadata.uploaded_at
        video.meta = raw_payload(metadata)
        return video

    def get(self, video_id: str) -> VideoORM | None:
        return self._s.get(VideoORM, video_id)

    def to_metadata(self, video: VideoORM) -> VideoMetadata:
        return VideoMetadata.model_validate(video.meta)


class ArtifactRepository:
    """Persists prepared inputs and all analysis artifacts; reads them back."""

    def __init__(self, session: Session) -> None:
        self._s = session

    # ── writes ───────────────────────────────────────────────────────────────
    def save_prepared(self, prepared: PreparedVideo) -> None:
        vid = prepared.metadata.video_id
        self._s.query(SceneORM).filter_by(video_id=vid).delete()
        self._s.query(FrameORM).filter_by(video_id=vid).delete()
        for sc in prepared.scenes:
            self._s.add(SceneORM(video_id=vid, scene_id=sc.scene_id, start=sc.start, end=sc.end))
        for fr in prepared.frames:
            self._s.merge(
                FrameORM(
                    frame_id=fr.frame_id,
                    video_id=vid,
                    timestamp=fr.timestamp,
                    path=fr.path,
                    is_keyframe=fr.is_keyframe,
                    scene_id=fr.scene_id,
                )
            )

    def save_artifacts(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._save_ocr(video_id, artifacts)
        self._save_transcript(video_id, artifacts)
        self._save_visual(video_id, artifacts)
        self._save_graph(video_id, artifacts)
        self._save_timeline(video_id, artifacts)
        self._save_report(video_id, artifacts)

    def _save_ocr(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(OcrResultORM).filter_by(video_id=video_id).delete()
        for item in artifacts.modalities.ocr:
            self._s.add(
                OcrResultORM(
                    video_id=video_id,
                    timestamp=item.timestamp,
                    text=item.text,
                    confidence=item.confidence,
                    frame_id=item.frame_id,
                    raw=raw_payload(item),
                )
            )

    def _save_transcript(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(TranscriptORM).filter_by(video_id=video_id).delete()
        t = artifacts.modalities.transcript
        self._s.add(
            TranscriptORM(
                video_id=video_id,
                language=t.language,
                full_text=t.full_text,
                segments=[raw_payload(s) for s in t.segments],
            )
        )

    def _save_visual(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(VisualDetectionORM).filter_by(video_id=video_id).delete()
        for det in artifacts.modalities.visual:
            self._s.add(
                VisualDetectionORM(
                    video_id=video_id,
                    timestamp=det.timestamp,
                    frame_id=det.frame_id,
                    scores=det.scores,
                    evidence=det.evidence,
                )
            )

    def _save_graph(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(EvidenceGraphORM).filter_by(video_id=video_id).delete()
        self._s.add(
            EvidenceGraphORM(
                video_id=video_id,
                events=[raw_payload(e) for e in artifacts.graph.events],
                adjacency=artifacts.graph.adjacency,
            )
        )

    def _save_timeline(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(TimelineORM).filter_by(video_id=video_id).delete()
        self._s.add(
            TimelineORM(
                video_id=video_id,
                events=[raw_payload(e) for e in artifacts.timeline],
                markers=[raw_payload(m) for m in artifacts.report.player_markers],
            )
        )

    def _save_report(self, video_id: str, artifacts: AnalysisArtifacts) -> None:
        self._s.query(ReportORM).filter_by(video_id=video_id).delete()
        r = artifacts.report
        self._s.add(
            ReportORM(
                video_id=video_id,
                risk_score=r.risk_score,
                category=r.category.value,
                confidence=r.confidence,
                summary=r.summary,
                report=raw_payload(r),
                fallback_used=r.fallback_used,
            )
        )

    # ── reads ────────────────────────────────────────────────────────────────
    def get_report(self, video_id: str) -> ReportORM | None:
        return self._s.scalars(
            select(ReportORM).where(ReportORM.video_id == video_id)
        ).first()

    def get_timeline(self, video_id: str) -> TimelineORM | None:
        return self._s.scalars(
            select(TimelineORM).where(TimelineORM.video_id == video_id)
        ).first()

"""ORM models. Structured artifacts are stored as JSONB for auditability, with
key scalar columns promoted for indexing/querying. Every table is append-or-
upsert friendly so the full analysis history of a video is reconstructable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VideoORM(Base):
    __tablename__ = "videos"

    video_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    source_platform: Mapped[str] = mapped_column(String(64), default="upload")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    container: Mapped[str] = mapped_column(String(16), default="")
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    jobs: Mapped[list["JobORM"]] = relationship(back_populates="video")


class JobORM(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped[VideoORM] = relationship(back_populates="jobs")


class SceneORM(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True)
    scene_id: Mapped[int] = mapped_column(Integer)
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)


class FrameORM(Base):
    __tablename__ = "frames"

    frame_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    path: Mapped[str] = mapped_column(Text)
    is_keyframe: Mapped[bool] = mapped_column(Boolean, default=False)
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OcrResultORM(Base):
    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    frame_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (Index("ix_ocr_video_ts", "video_id", "timestamp"),)


class TranscriptORM(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True, unique=True)
    language: Mapped[str] = mapped_column(String(16), default="unknown")
    full_text: Mapped[str] = mapped_column(Text, default="")
    segments: Mapped[list] = mapped_column(JSONB, default=list)


class VisualDetectionORM(Base):
    __tablename__ = "visual_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True)
    timestamp: Mapped[float] = mapped_column(Float, index=True)
    frame_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)


class EvidenceGraphORM(Base):
    __tablename__ = "evidence_graphs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True, unique=True)
    events: Mapped[list] = mapped_column(JSONB, default=list)
    adjacency: Mapped[dict] = mapped_column(JSONB, default=dict)


class TimelineORM(Base):
    __tablename__ = "timelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True, unique=True)
    events: Mapped[list] = mapped_column(JSONB, default=list)
    markers: Mapped[list] = mapped_column(JSONB, default=list)


class ReportORM(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), index=True, unique=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    category: Mapped[str] = mapped_column(String(48), default="none", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLogORM(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    stage: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

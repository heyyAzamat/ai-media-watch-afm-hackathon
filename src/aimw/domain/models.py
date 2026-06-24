"""Core analysis value objects.

These Pydantic models are the *lingua franca* of the engine. Every service
consumes and produces these models, never raw dicts, so that data is validated
at each boundary and every artifact stays auditable and serialisable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import EvidenceSource, RiskCategory, Severity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# ── Ingestion ────────────────────────────────────────────────────────────────
class VideoMetadata(_Base):
    """Technical metadata extracted at ingestion (Step 1)."""

    video_id: str
    filename: str
    source_platform: str = "upload"
    source_url: str | None = None
    duration_seconds: float = Field(ge=0)
    fps: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    container: str = ""
    uploaded_at: datetime = Field(default_factory=_utcnow)

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


# ── Scenes & frames (Steps 2-3) ──────────────────────────────────────────────
class Scene(_Base):
    scene_id: int
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @property
    def keyframe_ts(self) -> float:
        """Representative timestamp for the scene (its midpoint)."""
        return round((self.start + self.end) / 2.0, 3)


class Frame(_Base):
    frame_id: str
    timestamp: float = Field(ge=0)
    path: str
    is_keyframe: bool = False
    scene_id: int | None = None


# ── Modality outputs (Steps 4-6) ─────────────────────────────────────────────
class OcrResult(_Base):
    """A single OCR text detection on a frame (Step 4)."""

    timestamp: float = Field(ge=0)
    text: str
    confidence: float = Field(ge=0, le=1)
    frame_id: str | None = None
    bbox: list[float] | None = None  # [x1, y1, x2, y2], optional


class TranscriptWord(_Base):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    word: str
    probability: float = Field(default=1.0, ge=0, le=1)


class TranscriptSegment(_Base):
    """A timestamped speech segment (Step 5)."""

    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    words: list[TranscriptWord] = Field(default_factory=list)


class Transcript(_Base):
    language: str = "unknown"
    segments: list[TranscriptSegment] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())


class VisualDetection(_Base):
    """Per-keyframe visual risk signal from the VLM (Step 6)."""

    timestamp: float = Field(ge=0)
    frame_id: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)  # label -> 0..1
    evidence: list[str] = Field(default_factory=list)

    @field_validator("scores")
    @classmethod
    def _clamp_scores(cls, v: dict[str, float]) -> dict[str, float]:
        return {k: max(0.0, min(1.0, float(val))) for k, val in v.items()}

    @property
    def top_label(self) -> tuple[str, float] | None:
        if not self.scores:
            return None
        label, score = max(self.scores.items(), key=lambda kv: kv[1])
        return label, score


class ModalityResults(_Base):
    """Bundle produced by the parallel analysis phase (Step 4-6 combined)."""

    ocr: list[OcrResult] = Field(default_factory=list)
    transcript: Transcript = Field(default_factory=Transcript)
    visual: list[VisualDetection] = Field(default_factory=list)


# ── Text risk analysis (Step 7) ──────────────────────────────────────────────
class TextRiskEvidence(_Base):
    """A risk signal derived from OCR or speech text (Step 7)."""

    timestamp: float = Field(ge=0)
    end: float | None = None
    source: EvidenceSource
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    text: str
    matched_terms: list[str] = Field(default_factory=list)


# ── Fusion & evidence graph (Step 8) ─────────────────────────────────────────
class EvidenceRef(_Base):
    """A normalised, single-modality evidence item feeding fusion."""

    source: EvidenceSource
    timestamp: float = Field(ge=0)
    end: float | None = None
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    detail: str = ""


class FusedEvent(_Base):
    """A cross-modal event produced by merging nearby evidence (Step 8)."""

    event_id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    sources: list[EvidenceSource] = Field(default_factory=list)
    refs: list[EvidenceRef] = Field(default_factory=list)


class EvidenceGraph(_Base):
    """Unified evidence graph: fused events + co-occurrence adjacency."""

    events: list[FusedEvent] = Field(default_factory=list)
    # event_id -> list of event_ids that overlap/corroborate it
    adjacency: dict[str, list[str]] = Field(default_factory=dict)


# ── Timeline (Step 9) ────────────────────────────────────────────────────────
class TimelineEvent(_Base):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    severity: Severity
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)


class EvidencePlayerMarker(_Base):
    """Frontend-jumpable marker (Evidence Player requirement)."""

    timestamp: float = Field(ge=0)
    label: str
    severity: Severity
    icon: str  # 🔴 / 🟠 / 🟡
    display_time: str  # "00:32"


# ── Final verdict (Step 10) ──────────────────────────────────────────────────
class JudgeVerdict(_Base):
    """Output of the single Qwen-72B compliance-officer call (Step 10)."""

    risk_score: int = Field(ge=0, le=100)
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    summary: str
    explanation: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    suspicious_timestamps: list[float] = Field(default_factory=list)
    model: str = ""
    fallback_used: bool = False


# ── Final report (output contract) ───────────────────────────────────────────
class EvidenceBundle(_Base):
    visual: list[VisualDetection] = Field(default_factory=list)
    audio: list[TextRiskEvidence] = Field(default_factory=list)
    ocr: list[TextRiskEvidence] = Field(default_factory=list)


class AnalysisReport(_Base):
    """The complete, explainable analysis result for a video."""

    video_id: str
    risk_score: int = Field(ge=0, le=100)
    category: RiskCategory
    confidence: float = Field(ge=0, le=1)
    summary: str
    explanation: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    player_markers: list[EvidencePlayerMarker] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    metadata: VideoMetadata | None = None
    fallback_used: bool = False
    generated_at: datetime = Field(default_factory=_utcnow)


# ── Engine input ─────────────────────────────────────────────────────────────
class PreparedVideo(_Base):
    """Everything the analysis brain needs after ingestion/extraction.

    This is what the orchestrator consumes; producing it (ffmpeg, scene
    detection, frame sampling) is the responsibility of the upstream services.
    """

    metadata: VideoMetadata
    scenes: list[Scene] = Field(default_factory=list)
    frames: list[Frame] = Field(default_factory=list)
    audio_path: str | None = None

    @property
    def keyframes(self) -> list[Frame]:
        kf = [f for f in self.frames if f.is_keyframe]
        return kf or self.frames


class AnalysisArtifacts(_Base):
    """Full intermediate state, persisted for audit + sub-resource endpoints."""

    modalities: ModalityResults
    text_risk: list[TextRiskEvidence]
    graph: EvidenceGraph
    timeline: list[TimelineEvent]
    verdict: JudgeVerdict
    report: AnalysisReport


def raw_payload(obj: BaseModel) -> dict[str, Any]:
    """Serialise a model to a JSON-safe dict for DB ``JSONB`` columns."""
    return obj.model_dump(mode="json")

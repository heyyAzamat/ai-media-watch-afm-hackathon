"""Reporting service — assemble the final, explainable AnalysisReport.

Combines the judge verdict with the timeline, player markers and the raw,
per-modality evidence so that every number in the report is traceable to its
source (visual / speech / OCR) with timestamps.
"""

from __future__ import annotations

from ..domain.enums import EvidenceSource
from ..domain.models import (
    AnalysisReport,
    EvidenceBundle,
    EvidencePlayerMarker,
    JudgeVerdict,
    ModalityResults,
    TextRiskEvidence,
    TimelineEvent,
    VideoMetadata,
)
from ..logging_config import get_logger

log = get_logger(__name__)


class ReportingService:
    def build(
        self,
        *,
        metadata: VideoMetadata,
        modalities: ModalityResults,
        text_risk: list[TextRiskEvidence],
        timeline: list[TimelineEvent],
        markers: list[EvidencePlayerMarker],
        verdict: JudgeVerdict,
    ) -> AnalysisReport:
        evidence = EvidenceBundle(
            visual=modalities.visual,
            audio=[e for e in text_risk if e.source == EvidenceSource.SPEECH],
            ocr=[e for e in text_risk if e.source == EvidenceSource.OCR],
        )
        report = AnalysisReport(
            video_id=metadata.video_id,
            risk_score=verdict.risk_score,
            category=verdict.category,
            confidence=verdict.confidence,
            summary=verdict.summary,
            explanation=verdict.explanation,
            timeline=timeline,
            player_markers=markers,
            evidence=evidence,
            metadata=metadata,
            fallback_used=verdict.fallback_used,
            llm_called=verdict.llm_called,
        )
        log.info(
            "reporting.done",
            video_id=metadata.video_id,
            risk_score=report.risk_score,
            category=report.category,
        )
        return report

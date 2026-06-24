"""End-to-end engine test with mock providers + deterministic fallback judge.

Runs the full parallel pipeline (OCR ‖ speech ‖ visual → fusion → timeline →
judge → report) without any DB, queue, GPU or network.
"""

from __future__ import annotations

import pytest

from aimw.domain.enums import EvidenceSource, RiskCategory
from aimw.domain.models import (
    ModalityResults,
    OcrResult,
    PreparedVideo,
    Transcript,
    VideoMetadata,
    VisualDetection,
)
from aimw.orchestration.orchestrator import AnalysisOrchestrator


@pytest.mark.asyncio
async def test_full_pipeline_flags_gambling(prepared_video: PreparedVideo):
    orchestrator = AnalysisOrchestrator()
    artifacts = await orchestrator.run(prepared_video)

    report = artifacts.report
    # The scripted mock content is an illegal-gambling / casino promo reel.
    assert report.risk_score >= 70
    assert report.category != RiskCategory.NONE
    assert report.summary

    # Explainability: every flag traces back to timestamped, multi-modal evidence.
    assert report.timeline, "expected a non-empty suspicious-moments timeline"
    assert report.player_markers, "expected Evidence Player markers"
    assert report.evidence.ocr or report.evidence.audio
    assert report.evidence.visual
    # at least one event corroborated by 2+ modalities
    assert any(len(e.sources) >= 2 for e in artifacts.graph.events)


@pytest.mark.asyncio
async def test_parallel_phase_returns_all_modalities(prepared_video: PreparedVideo):
    orchestrator = AnalysisOrchestrator()
    modalities: ModalityResults = await orchestrator.analyze_modalities(prepared_video)
    assert modalities.ocr
    assert modalities.transcript.segments
    assert modalities.visual


@pytest.mark.asyncio
async def test_honest_no_data_path_does_not_fabricate():
    """Critical control: with zero evidence the verdict must be NONE / score 0,
    never a fabricated analysis (see fusion + fallback judge)."""
    from aimw.services.fusion import FusionService
    from aimw.services.reasoning.base import compute_fallback_verdict
    from aimw.services.timeline import TimelineService

    graph = FusionService().fuse([], [])  # no text-risk, no visual
    timeline, _ = TimelineService().build(graph)
    metadata = VideoMetadata(
        video_id="vid_empty", filename="empty.mp4", duration_seconds=10.0,
        fps=30.0, width=0, height=0, size_bytes=0,
    )
    verdict = compute_fallback_verdict(metadata, graph, timeline)

    assert verdict.risk_score == 0
    assert verdict.category == RiskCategory.NONE
    assert verdict.confidence == 0.0
    assert not timeline


@pytest.mark.asyncio
async def test_benign_modalities_yield_low_risk(prepared_video: PreparedVideo):
    """A benign video (no risk terms, no risky visuals) must score low."""
    from aimw.services.fusion import FusionService
    from aimw.services.reasoning.base import compute_fallback_verdict
    from aimw.services.text_risk import TextRiskAnalyzer
    from aimw.services.timeline import TimelineService

    benign_ocr = [OcrResult(timestamp=2.0, text="Subscribe for more cat videos", confidence=0.97)]
    benign_transcript = Transcript()
    benign_visual: list[VisualDetection] = [VisualDetection(timestamp=4.0, scores={"casino": 0.05})]

    text_risk = TextRiskAnalyzer().analyze(benign_ocr, benign_transcript)
    graph = FusionService().fuse(text_risk, benign_visual)
    timeline, _ = TimelineService().build(graph)
    verdict = compute_fallback_verdict(prepared_video.metadata, graph, timeline)

    assert verdict.risk_score < 40
    assert EvidenceSource.OCR not in {s for e in graph.events for s in e.sources} or verdict.risk_score < 40

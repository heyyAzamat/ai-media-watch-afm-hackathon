"""VLM stage-gating logic (text_risk mode). Pure helpers, no providers needed."""

from __future__ import annotations

import os

from aimw.domain.enums import EvidenceSource, RiskCategory
from aimw.domain.models import Frame, TextRiskEvidence
from aimw.orchestration.orchestrator import AnalysisOrchestrator


def _frames(timestamps: list[float]) -> list[Frame]:
    return [
        Frame(frame_id=f"k{i}", timestamp=t, path=f"/x/{i}.jpg", is_keyframe=True)
        for i, t in enumerate(timestamps)
    ]


def _risk(ts: float, end: float | None = None) -> TextRiskEvidence:
    return TextRiskEvidence(
        timestamp=ts, end=end, source=EvidenceSource.OCR,
        category=RiskCategory.CASINO_ADVERTISING, confidence=0.8, text="casino",
    )


def _orch() -> AnalysisOrchestrator:
    os.environ["AIMW_VISUAL_GATING_WINDOW_SECONDS"] = "3.0"
    from aimw.config import get_settings

    get_settings.cache_clear()
    return AnalysisOrchestrator()


def test_keeps_keyframes_near_risk_drops_far_ones():
    orch = _orch()
    keyframes = _frames([2.0, 10.0, 30.0])
    gated = orch._gate_by_text_risk(keyframes, [_risk(2.5), _risk(31.0)])
    kept = {kf.timestamp for kf in gated}
    assert kept == {2.0, 30.0}  # 10.0 is far from any risk -> dropped


def test_empty_text_risk_does_not_prune():
    orch = _orch()
    keyframes = _frames([2.0, 10.0, 30.0])
    # text silent -> never prune (visual-only recall preserved)
    assert orch._gate_by_text_risk(keyframes, []) == keyframes


def test_never_prunes_to_empty():
    orch = _orch()
    keyframes = _frames([100.0, 200.0])
    # risk exists but no keyframe is near it -> keep all rather than analyze none
    gated = orch._gate_by_text_risk(keyframes, [_risk(5.0)])
    assert gated == keyframes


def test_risk_interval_end_extends_window():
    orch = _orch()
    keyframes = _frames([15.0])
    # risk spans 8-12; window 3 -> covers up to 15 -> keyframe kept
    assert orch._gate_by_text_risk(keyframes, [_risk(8.0, end=12.0)]) == keyframes

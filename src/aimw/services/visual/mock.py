"""Deterministic mock visual provider (no VLM, no GPU).

Emits scripted per-keyframe detections consistent with a gambling-promo reel so
fusion can corroborate visual signals against OCR/speech. Only selected when
AIMW_VISUAL_PROVIDER=mock.
"""

from __future__ import annotations

from ...domain.models import Frame, VisualDetection
from ...logging_config import get_logger

log = get_logger(__name__)


def _scores_for(index: int) -> tuple[dict[str, float], list[str]]:
    """Cycle through a few representative high-risk frames deterministically."""
    table = [
        (
            {"casino": 0.96, "roulette_wheel": 0.93, "slot_machine": 0.4, "luxury_marketing": 0.7},
            ["roulette wheel", "bonus banner", "deposit incentive"],
        ),
        (
            {"slot_machine": 0.91, "casino": 0.88, "urgency_tactics": 0.6},
            ["slot machine reels", "flashing jackpot banner"],
        ),
        (
            {"guaranteed_income_claim": 0.9, "fake_profit_screenshot": 0.85,
             "luxury_marketing": 0.8},
            ["profit screenshot", "luxury car", "guaranteed returns text"],
        ),
        (
            {"referral_marketing": 0.92, "manipulation_tactics": 0.6, "urgency_tactics": 0.55},
            ["referral promo code overlay", "limited time offer"],
        ),
    ]
    return table[index % len(table)]


class MockVisualProvider:
    name = "mock-qwen2.5-vl"

    async def analyze(self, keyframes: list[Frame]) -> list[VisualDetection]:
        detections: list[VisualDetection] = []
        for i, frame in enumerate(keyframes):
            scores, evidence = _scores_for(i)
            detections.append(
                VisualDetection(
                    timestamp=frame.timestamp,
                    frame_id=frame.frame_id,
                    scores=scores,
                    evidence=evidence,
                )
            )
        log.info("visual.mock.done", detections=len(detections))
        return detections

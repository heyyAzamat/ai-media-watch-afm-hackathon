"""Deterministic mock OCR provider for local dev, CI and demos.

It does NOT call any model. It emits a fixed, scripted set of on-screen text
overlays anchored to the available frame timestamps so the rest of the pipeline
(text-risk, fusion, timeline, judge) can be exercised end-to-end without a GPU.
The output is clearly synthetic and is only selected when AIMW_OCR_PROVIDER=mock.
"""

from __future__ import annotations

from ...domain.models import Frame, OcrResult
from ...logging_config import get_logger

log = get_logger(__name__)

# Scripted overlays a typical illegal-gambling promo reel might show on screen.
_SCRIPT: list[tuple[float, str, float]] = [
    (2.0, "1XCASINO — DEPOSIT BONUS 200%", 0.97),
    (5.0, "FREE SPINS • JACKPOT TODAY", 0.95),
    (9.0, "Earn 1000 dollars daily with no risk", 0.93),
    (14.0, "Promo code: LUCKY777 — link in bio", 0.94),
    (20.0, "Invite friends & double your money", 0.9),
]


class MockOcrProvider:
    name = "mock-ocr"

    async def run(self, frames: list[Frame]) -> list[OcrResult]:
        if not frames:
            return []
        max_ts = max(f.timestamp for f in frames)
        results: list[OcrResult] = []
        for ts, text, conf in _SCRIPT:
            if ts > max_ts + 1.0:
                continue
            nearest = min(frames, key=lambda f: abs(f.timestamp - ts))
            results.append(
                OcrResult(
                    timestamp=nearest.timestamp,
                    text=text,
                    confidence=conf,
                    frame_id=nearest.frame_id,
                )
            )
        log.info("ocr.mock.done", detections=len(results))
        return results

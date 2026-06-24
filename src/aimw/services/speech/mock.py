"""Deterministic mock speech provider (no model, no GPU).

Emits a scripted transcript with segment + word timestamps so the text-risk,
fusion and timeline stages have realistic speech evidence to work with. Only
selected when AIMW_SPEECH_PROVIDER=mock.
"""

from __future__ import annotations

from ...domain.models import Transcript, TranscriptSegment, TranscriptWord
from ...logging_config import get_logger

log = get_logger(__name__)

_SCRIPT: list[tuple[float, float, str]] = [
    (3.0, 6.5, "Welcome back, today I show you the best online casino bonus."),
    (8.5, 12.0, "You can make money every day without any risk, guaranteed income."),
    (13.0, 16.5, "Use my promo code and invite your friends to double your deposit."),
    (18.0, 21.0, "Sign up with the link in my bio and start winning the jackpot now."),
]


def _to_words(start: float, end: float, text: str) -> list[TranscriptWord]:
    tokens = text.split()
    if not tokens:
        return []
    step = (end - start) / len(tokens)
    return [
        TranscriptWord(
            start=round(start + i * step, 3),
            end=round(start + (i + 1) * step, 3),
            word=tok,
            probability=0.95,
        )
        for i, tok in enumerate(tokens)
    ]


class MockSpeechProvider:
    name = "mock-whisper"

    async def transcribe(self, audio_path: str | None) -> Transcript:
        segments = [
            TranscriptSegment(
                start=start,
                end=end,
                text=text,
                confidence=0.95,
                words=_to_words(start, end, text),
            )
            for start, end, text in _SCRIPT
        ]
        log.info("speech.mock.done", segments=len(segments))
        return Transcript(language="en", segments=segments)

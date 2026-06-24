"""Speech provider factory."""

from __future__ import annotations

from ...config import SpeechProviderMode
from ..interfaces import SpeechProvider


def build_speech_provider(mode: SpeechProviderMode) -> SpeechProvider:
    if mode == "real":
        from .whisper import WhisperSpeechProvider

        return WhisperSpeechProvider()
    if mode in ("none", "disabled"):  # synonyms: empty transcript, no fabrication
        from .none import NoneSpeechProvider

        return NoneSpeechProvider()
    from .mock import MockSpeechProvider

    return MockSpeechProvider()

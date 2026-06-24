"""Speech provider factory."""

from __future__ import annotations

from ...config import ProviderMode
from ..interfaces import SpeechProvider


def build_speech_provider(mode: ProviderMode) -> SpeechProvider:
    if mode == "real":
        from .whisper import WhisperSpeechProvider

        return WhisperSpeechProvider()
    from .mock import MockSpeechProvider

    return MockSpeechProvider()

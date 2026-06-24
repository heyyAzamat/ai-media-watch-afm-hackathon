"""Speech provider factory."""

from __future__ import annotations

from ...config import ProviderMode
from ..interfaces import SpeechProvider


class _NullSpeechProvider:
    """Speech turned off — returns an empty transcript (no fabrication)."""

    name = "disabled-speech"

    async def transcribe(self, audio_path):  # noqa: ANN001, ANN201
        from ...domain.models import Transcript

        return Transcript()


def build_speech_provider(mode: ProviderMode) -> SpeechProvider:
    if mode == "real":
        from .whisper import WhisperSpeechProvider

        return WhisperSpeechProvider()
    if mode == "disabled":
        return _NullSpeechProvider()
    from .mock import MockSpeechProvider

    return MockSpeechProvider()

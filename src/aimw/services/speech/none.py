"""No-op speech provider for the data-sovereign / no-audio-scam profile.

Returns an empty transcript. Unlike the mock provider (which emits a scripted,
fabricated scam transcript for tests), this is safe for a real run with no
Whisper model: the report carries no speech signal rather than invented
evidence. Selected with ``AIMW_SPEECH_PROVIDER=none``.
"""

from __future__ import annotations

from ...domain.models import Transcript


class NoneSpeechProvider:
    name = "none"

    async def transcribe(self, audio_path: str | None) -> Transcript:
        return Transcript()

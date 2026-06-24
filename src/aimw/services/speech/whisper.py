"""Real speech provider backed by faster-whisper (Whisper Large-v3).

Transcription is blocking/CPU-or-GPU bound, so it runs in a thread to stay
concurrent with OCR + visual analysis. Requires the ``ml`` extra.
"""

from __future__ import annotations

import asyncio

from ...config import get_settings
from ...domain.models import Transcript, TranscriptSegment, TranscriptWord
from ...logging_config import get_logger

log = get_logger(__name__)


class WhisperSpeechProvider:
    name = "whisper-large-v3"

    def __init__(self, model_size: str | None = None, device: str | None = None,
                 compute_type: str | None = None, vad_filter: bool | None = None) -> None:
        settings = get_settings()
        self._model_size = model_size or settings.whisper_model
        self._device = device or settings.whisper_device
        self._compute_type = compute_type or settings.whisper_compute_type
        self._vad_filter = settings.whisper_vad_filter if vad_filter is None else vad_filter
        self._beam_size = settings.whisper_beam_size
        self._batched = settings.whisper_batched
        self._batch_size = settings.whisper_batch_size
        self.name = f"whisper-{self._model_size}"
        self._model = None
        self._batched_pipe = None

    def _ensure_model(self):  # noqa: ANN201
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
        return self._model

    def _transcribe(self, audio_path: str):  # noqa: ANN202
        """Run transcription, preferring the batched pipeline, with fallback."""
        model = self._ensure_model()
        kwargs = dict(word_timestamps=True, vad_filter=self._vad_filter,
                      beam_size=self._beam_size)
        if self._batched:
            try:
                if self._batched_pipe is None:
                    from faster_whisper import BatchedInferencePipeline

                    self._batched_pipe = BatchedInferencePipeline(model=model)
                return self._batched_pipe.transcribe(
                    audio_path, batch_size=self._batch_size, **kwargs
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("speech.whisper.batched_fallback", error=str(exc))
        return model.transcribe(audio_path, **kwargs)

    def _transcribe_sync(self, audio_path: str) -> Transcript:
        segments_iter, info = self._transcribe(audio_path)
        segments: list[TranscriptSegment] = []
        for seg in segments_iter:
            words = [
                TranscriptWord(
                    start=round(w.start, 3),
                    end=round(w.end, 3),
                    word=w.word.strip(),
                    probability=float(getattr(w, "probability", 1.0) or 1.0),
                )
                for w in (seg.words or [])
            ]
            segments.append(
                TranscriptSegment(
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=seg.text.strip(),
                    confidence=float(getattr(seg, "avg_logprob", 0.0) or 0.0) and 1.0 or 0.9,
                    words=words,
                )
            )
        return Transcript(language=info.language or "unknown", segments=segments)

    async def transcribe(self, audio_path: str | None) -> Transcript:
        if not audio_path:
            log.info("speech.whisper.no_audio")
            return Transcript()
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(None, self._transcribe_sync, audio_path)
        log.info("speech.whisper.done", segments=len(transcript.segments),
                 language=transcript.language)
        return transcript

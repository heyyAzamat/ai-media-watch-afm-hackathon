"""Provider protocols (ports) for the analysis services.

These ``Protocol`` definitions decouple the orchestrator from concrete
implementations. Any class that satisfies the structural type can be injected —
real GPU-backed providers in production, deterministic mocks in tests/dev — with
no change to business logic. This is the seam that keeps the core engine
framework- and vendor-agnostic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import (
    Frame,
    JudgeVerdict,
    OcrResult,
    PreparedVideo,
    Scene,
    Transcript,
    VideoMetadata,
    VisualDetection,
)


@runtime_checkable
class IngestionService(Protocol):
    """Step 1 — probe a media file and produce :class:`VideoMetadata`."""

    def probe(self, *, video_id: str, path: str, filename: str,
              source_platform: str = "upload", source_url: str | None = None) -> VideoMetadata:
        ...


@runtime_checkable
class SceneDetector(Protocol):
    """Step 2 — detect scene boundaries with PySceneDetect."""

    def detect(self, video_path: str, duration: float) -> list[Scene]:
        ...


@runtime_checkable
class FrameExtractor(Protocol):
    """Step 3 — sample frames (1 fps + scene keyframes)."""

    def extract(self, video_path: str, video_id: str, scenes: list[Scene],
                fps: float) -> list[Frame]:
        ...


@runtime_checkable
class AudioExtractor(Protocol):
    """Demux audio to a wav file for the speech provider."""

    def extract_audio(self, video_path: str, video_id: str) -> str | None:
        ...


@runtime_checkable
class OcrProvider(Protocol):
    """Step 4 — OCR over frames (async to allow batched remote inference)."""

    name: str

    async def run(self, frames: list[Frame]) -> list[OcrResult]:
        ...


@runtime_checkable
class SpeechProvider(Protocol):
    """Step 5 — speech-to-text with word/segment timestamps."""

    name: str

    async def transcribe(self, audio_path: str | None) -> Transcript:
        ...


@runtime_checkable
class VisualProvider(Protocol):
    """Step 6 — visual risk analysis of scene keyframes with a VLM."""

    name: str

    async def analyze(self, keyframes: list[Frame]) -> list[VisualDetection]:
        ...


@runtime_checkable
class ReasoningEngine(Protocol):
    """Step 10 — the single final-reasoning compliance judge call."""

    model: str

    async def judge(self, context: dict) -> JudgeVerdict:
        ...


@runtime_checkable
class VideoPreparer(Protocol):
    """Aggregates ingestion + scene + frame + audio extraction (Steps 1-3)."""

    def prepare(self, *, video_id: str, path: str, filename: str,
                source_platform: str = "upload", source_url: str | None = None) -> PreparedVideo:
        ...

"""The analysis orchestrator — framework-agnostic core engine.

This class contains NO FastAPI and NO Celery imports. It can be driven from a
worker, a CLI, a test, or an SDK. Its defining feature is the *parallel*
modality phase: OCR, speech and visual analysis run concurrently via
``asyncio.gather`` rather than as a sequential pipeline.

    PreparedVideo
          │
   ┌──────┼──────┐
   ▼      ▼      ▼
  OCR   SPEECH  VISUAL      (asyncio.gather)
   └──────┼──────┘
          ▼
     TEXT RISK → FUSION → TIMELINE → JUDGE (1×) → REPORT
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from ..config import get_settings
from ..domain.enums import EvidenceSource, JobStatus
from ..domain.models import (
    AnalysisArtifacts,
    ModalityResults,
    PreparedVideo,
)
from ..logging_config import get_logger
from .container import EngineContainer, build_container

log = get_logger(__name__)


class ProgressSink(Protocol):
    """Receives stage transitions so callers can persist job progress."""

    def __call__(self, status: JobStatus, progress: int, detail: str) -> None:
        ...


def _noop(status: JobStatus, progress: int, detail: str) -> None:  # pragma: no cover
    return None


class AnalysisOrchestrator:
    def __init__(self, container: EngineContainer | None = None) -> None:
        self._c = container or build_container()

    # ── Steps 1-3: ingestion + scene + frame + audio (sync, CPU/IO) ──────────
    def prepare(
        self,
        *,
        video_id: str,
        path: str,
        filename: str,
        source_platform: str = "upload",
        source_url: str | None = None,
    ) -> PreparedVideo:
        c = self._c
        metadata = c.ingestion.probe(
            video_id=video_id,
            path=path,
            filename=filename,
            source_platform=source_platform,
            source_url=source_url,
        )
        scenes = c.scene.detect(path, metadata.duration_seconds)
        frames = c.frames.extract(
            path, video_id, scenes, fps=c.settings.frames_per_second
        )
        audio_path = c.audio.extract_audio(path, video_id)
        return PreparedVideo(
            metadata=metadata, scenes=scenes, frames=frames, audio_path=audio_path
        )

    # ── Steps 4-6: PARALLEL modality analysis ────────────────────────────────
    async def analyze_modalities(self, prepared: PreparedVideo) -> ModalityResults:
        c = self._c
        ocr_task = c.ocr.run(prepared.frames)
        speech_task = c.speech.transcribe(prepared.audio_path)
        visual_task = c.visual.analyze(prepared.keyframes)

        ocr, transcript, visual = await asyncio.gather(ocr_task, speech_task, visual_task)
        log.info(
            "orchestrator.modalities",
            ocr=len(ocr),
            segments=len(transcript.segments),
            visual=len(visual),
        )
        return ModalityResults(ocr=ocr, transcript=transcript, visual=visual)

    # ── Steps 7-10: analysis brain ───────────────────────────────────────────
    async def run(
        self, prepared: PreparedVideo, progress: ProgressSink | None = None
    ) -> AnalysisArtifacts:
        emit = progress or _noop
        c = self._c

        emit(JobStatus.ANALYZING, 40, "parallel OCR / speech / visual")
        modalities = await self.analyze_modalities(prepared)

        emit(JobStatus.FUSING, 65, "text-risk + fusion + timeline")
        text_risk = c.text_risk.analyze(modalities.ocr, modalities.transcript)
        graph = c.fusion.fuse(text_risk, modalities.visual)
        timeline, markers = c.timeline.build(graph)

        emit(JobStatus.JUDGING, 80, "final compliance reasoning")
        context = {
            "metadata": prepared.metadata,
            "ocr_risk": [e for e in text_risk if e.source == EvidenceSource.OCR],
            "speech_risk": [e for e in text_risk if e.source == EvidenceSource.SPEECH],
            "transcript": modalities.transcript,
            "visual": modalities.visual,
            "graph": graph,
            "timeline": timeline,
        }
        verdict = await c.reasoning.judge(context)

        emit(JobStatus.REPORTING, 92, "assembling report")
        report = c.reporting.build(
            metadata=prepared.metadata,
            modalities=modalities,
            text_risk=text_risk,
            timeline=timeline,
            markers=markers,
            verdict=verdict,
        )

        return AnalysisArtifacts(
            modalities=modalities,
            text_risk=text_risk,
            graph=graph,
            timeline=timeline,
            verdict=verdict,
            report=report,
        )


async def analyze_prepared(prepared: PreparedVideo) -> AnalysisArtifacts:
    """Convenience: run the analysis brain on an already-prepared video."""
    return await AnalysisOrchestrator().run(prepared)


def get_settings_summary() -> dict:  # small helper used by /health
    s = get_settings()
    return {
        "ocr_provider": s.ocr_provider,
        "speech_provider": s.speech_provider,
        "visual_provider": s.visual_provider,
        "reasoning_model": s.reasoning_model,
    }

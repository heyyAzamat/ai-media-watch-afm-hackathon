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
    Frame,
    ModalityResults,
    PreparedVideo,
)
from ..logging_config import get_logger
from ..services.reasoning import empty_evidence_verdict
from ..utils.frames import dedup_frames
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
    def _select_ocr_frames(self, prepared: PreparedVideo) -> list[Frame]:
        """Reduce the OCR frame set (OCR is the dominant cost). See config."""
        strategy = self._c.settings.ocr_frame_strategy
        if strategy == "keyframes":
            selected = prepared.keyframes
        elif strategy == "dedup":
            selected = dedup_frames(prepared.frames, self._c.settings.ocr_dedup_hamming)
        else:
            selected = prepared.frames
        log.info(
            "orchestrator.ocr_frames",
            strategy=strategy,
            selected=len(selected),
            total=len(prepared.frames),
        )
        return selected

    def _cap_keyframes(self, keyframes: list[Frame]) -> list[Frame]:
        cap = self._c.settings.visual_max_keyframes
        return keyframes[:cap] if cap and cap > 0 else keyframes

    def _distinct_keyframes(self, prepared: PreparedVideo) -> list[Frame]:
        """Visually-distinct keyframes (dedup) — the gating candidate set."""
        if self._c.settings.visual_gating == "off":
            return self._cap_keyframes(prepared.keyframes)
        return self._cap_keyframes(
            dedup_frames(prepared.keyframes, self._c.settings.visual_dedup_hamming)
        )

    def _gate_by_text_risk(
        self, keyframes: list[Frame], text_risk: list
    ) -> list[Frame]:
        """Keep keyframes near an OCR/speech risk hit. Never prune to empty, and
        never prune when text is silent (preserves visual-only recall)."""
        if not text_risk:
            return keyframes
        window = self._c.settings.visual_gating_window_seconds

        def near_risk(ts: float) -> bool:
            for e in text_risk:
                end = (e.end if e.end is not None else e.timestamp) + window
                if e.timestamp - window <= ts <= end:
                    return True
            return False

        gated = [kf for kf in keyframes if near_risk(kf.timestamp)]
        return gated or keyframes

    async def analyze_modalities(self, prepared: PreparedVideo) -> ModalityResults:
        c = self._c
        ocr_frames = self._select_ocr_frames(prepared)

        if c.settings.visual_gating == "text_risk":
            # Two-phase: OCR + speech first, then gate the VLM on text-risk hits.
            ocr, transcript = await asyncio.gather(
                c.ocr.run(ocr_frames), c.speech.transcribe(prepared.audio_path)
            )
            text_risk = c.text_risk.analyze(ocr, transcript)
            candidates = self._distinct_keyframes(prepared)
            keyframes = self._gate_by_text_risk(candidates, text_risk)
            log.info("orchestrator.visual_gating", strategy="text_risk",
                     keyframes=len(prepared.keyframes), candidates=len(candidates),
                     analyzed=len(keyframes))
            visual = await c.visual.analyze(keyframes)
        else:
            # off / dedup: visual is independent -> keep full parallelism.
            keyframes = self._distinct_keyframes(prepared)
            log.info("orchestrator.visual_gating", strategy=c.settings.visual_gating,
                     keyframes=len(prepared.keyframes), analyzed=len(keyframes))
            ocr, transcript, visual = await asyncio.gather(
                c.ocr.run(ocr_frames),
                c.speech.transcribe(prepared.audio_path),
                c.visual.analyze(keyframes),
            )

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

        # Skip the paid 72B judge entirely when there is no evidence to weigh —
        # the honest no-data path: return the definitive empty verdict, never a
        # fabricated one (llm_called=False).
        if c.settings.reasoning_skip_when_empty and not graph.events:
            emit(JobStatus.JUDGING, 80, "no evidence — judge skipped")
            log.info("orchestrator.judge_skipped", reason="no evidence")
            verdict = empty_evidence_verdict()
        else:
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

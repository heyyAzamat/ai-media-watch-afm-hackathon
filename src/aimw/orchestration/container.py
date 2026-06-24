"""Dependency-injection container (composition root).

Every concrete provider is instantiated here, driven by settings. Nothing else
in the codebase constructs providers directly, so swapping an implementation
(real ⇆ mock, or a new vendor) is a one-line change confined to this module or
achieved by injecting a custom container into the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, get_settings
from ..services.frame import FFmpegAudioExtractor, OpenCVFrameExtractor
from ..services.fusion import FusionService
from ..services.ingestion import OpenCVIngestionService
from ..services.interfaces import (
    AudioExtractor,
    FrameExtractor,
    IngestionService,
    OcrProvider,
    ReasoningEngine,
    SceneDetector,
    SpeechProvider,
    VisualProvider,
)
from ..services.ocr import build_ocr_provider
from ..services.reasoning import build_reasoning_engine
from ..services.reporting import ReportingService
from ..services.scene import PySceneDetectDetector
from ..services.speech import build_speech_provider
from ..services.text_risk import TextRiskAnalyzer
from ..services.timeline import TimelineService
from ..services.visual import build_visual_provider


@dataclass
class EngineContainer:
    """Holds every service the pipeline needs, fully wired."""

    settings: Settings
    ingestion: IngestionService
    scene: SceneDetector
    frames: FrameExtractor
    audio: AudioExtractor
    ocr: OcrProvider
    speech: SpeechProvider
    visual: VisualProvider
    text_risk: TextRiskAnalyzer
    fusion: FusionService
    timeline: TimelineService
    reasoning: ReasoningEngine
    reporting: ReportingService


def build_container(settings: Settings | None = None) -> EngineContainer:
    settings = settings or get_settings()
    return EngineContainer(
        settings=settings,
        ingestion=OpenCVIngestionService(),
        scene=PySceneDetectDetector(),
        frames=OpenCVFrameExtractor(settings.frames_dir),
        audio=FFmpegAudioExtractor(settings.frames_dir),
        ocr=build_ocr_provider(settings.ocr_provider),
        speech=build_speech_provider(settings.speech_provider),
        visual=build_visual_provider(settings.visual_provider),
        text_risk=TextRiskAnalyzer(),
        fusion=FusionService(settings.fusion_window_seconds),
        timeline=TimelineService(),
        reasoning=build_reasoning_engine(),
        reporting=ReportingService(),
    )

"""Default ScamModel: the existing analysis pipeline behind the contract.

Runs ingestion + (real) Whisper + fusion + deterministic verdict, then maps the
resulting AnalysisReport onto a ScamVerdict. This is what makes the product work
end-to-end before the ML team's model exists. When their model is ready, switch
AIMW_SCAM_MODEL_PROVIDER to ``ml`` — no other change.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from ...logging_config import get_logger
from ...orchestration.orchestrator import AnalysisOrchestrator
from ...utils.ids import new_video_id
from .base import ScamVerdict

log = get_logger(__name__)


class OrchestratorScamModel:
    name = "orchestrator-pipeline"

    def __init__(self) -> None:
        self._orch = AnalysisOrchestrator()

    def analyze(self, video_path: str) -> ScamVerdict:
        video_id = new_video_id()
        prepared = self._orch.prepare(
            video_id=video_id,
            path=video_path,
            filename=Path(video_path).name,
        )
        # analyze() is sync (the API calls it in a worker thread), so drive the
        # async pipeline with a fresh event loop here.
        artifacts = asyncio.run(self._orch.run(prepared))
        report = artifacts.report
        log.info(
            "scam_model.orchestrator.done",
            risk_score=report.risk_score,
            category=report.category.value,
        )
        return ScamVerdict(
            risk_score=report.risk_score,
            category=report.category.value,
            confidence=report.confidence,
            explanation=report.explanation or report.summary,
            model=self.name,
        )

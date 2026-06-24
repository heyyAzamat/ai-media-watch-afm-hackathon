"""The scam-detection model contract — the seam between the backend and the
ML team's model.

The backend codes against :class:`ScamModel`: give it a local video file path,
get back a :class:`ScamVerdict`. Three implementations satisfy the contract:

* ``orchestrator`` (default) — wraps the existing Whisper/fusion pipeline, so the
  product works end-to-end *today*, before the ML model exists.
* ``ml`` — the ML team's model (dropped in later as ``ml_model.MlScamModel``).
* ``mock`` — a fixed placeholder verdict, handy for frontend UI work.

Selected via ``AIMW_SCAM_MODEL_PROVIDER``. Swapping to the real model is a
one-value config change; no API or frontend changes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ...config import get_settings
from ...logging_config import get_logger

log = get_logger(__name__)


class ScamVerdict(BaseModel):
    """The verdict every model returns and the API serves to the frontend."""

    risk_score: int = Field(ge=0, le=100)
    category: str  # e.g. "illegal_gambling", "pyramid_scheme", "guaranteed_income", "none"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation: str = ""
    model: str = "unknown"


@runtime_checkable
class ScamModel(Protocol):
    """Take a local video file path, return a :class:`ScamVerdict`. Sync (the
    backend runs it in a worker thread)."""

    name: str

    def analyze(self, video_path: str) -> ScamVerdict:
        ...


class MockScamModel:
    """A fixed placeholder verdict. NOT real analysis — for frontend UI work and
    smoke tests before the real model is wired."""

    name = "mock-scam-model"

    def analyze(self, video_path: str) -> ScamVerdict:
        return ScamVerdict(
            risk_score=75,
            category="illegal_gambling",
            confidence=0.8,
            explanation="PLACEHOLDER verdict from the mock model — replace with the real model.",
            model=self.name,
        )


def build_scam_model() -> ScamModel:
    """Return the configured model. Default = the existing pipeline, so the
    product works before the ML model lands."""
    mode = get_settings().scam_model_provider
    if mode == "ml":
        from .ml_model import MlScamModel  # ML team drops this file in

        return MlScamModel()
    if mode == "mock":
        return MockScamModel()
    from .orchestrator_model import OrchestratorScamModel

    log.info("scam_model.build", provider="orchestrator")
    return OrchestratorScamModel()

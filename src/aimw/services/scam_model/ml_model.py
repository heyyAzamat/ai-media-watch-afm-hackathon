"""ML team's scam-detection model — TEMPLATE TO FILL IN.

This is the merge point. The ML teammate implements the two methods below; the
backend already calls this class when AIMW_SCAM_MODEL_PROVIDER=ml. Nothing else
changes — same /check endpoint, same frontend, same ScamVerdict response.

See docs/ML_MODEL_CONTRACT.md for the full contract.

Heavy dependencies (torch, transformers, the embedding model, etc.) go in
requirements-ml.txt, NOT the base requirements.
"""
from __future__ import annotations

from ...logging_config import get_logger
from .base import ScamVerdict

log = get_logger(__name__)


class MlScamModel:
    name = "ml-embedding-model"

    def __init__(self) -> None:
        # TODO(ML): load the embedding model + classifier ONCE here (not per call).
        #   e.g. self._model = load_my_model("path/or/hf-id")
        log.info("ml_model.init", note="MlScamModel constructed")

    def analyze(self, video_path: str) -> ScamVerdict:
        """Analyze a local video file and return a ScamVerdict.

        ``video_path`` is a local .mp4 the backend already downloaded. Do your
        own frame/audio extraction + embedding + classification, then return:

            return ScamVerdict(
                risk_score=...,       # int 0-100
                category="...",       # see docs/ML_MODEL_CONTRACT.md, or "none"
                confidence=...,       # float 0.0-1.0
                explanation="...",    # one human-readable line (optional)
                model=self.name,
            )
        """
        # TODO(ML): replace this with real inference on `video_path`.
        raise NotImplementedError(
            "MlScamModel.analyze is not implemented yet — fill it in "
            "(see docs/ML_MODEL_CONTRACT.md). Until then run with "
            "AIMW_SCAM_MODEL_PROVIDER=orchestrator (the default)."
        )

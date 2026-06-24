"""Scam-detection model contract + implementations."""

from .base import ScamModel, ScamVerdict, build_scam_model

__all__ = ["ScamModel", "ScamVerdict", "build_scam_model"]

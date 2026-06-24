"""Final reasoning engine (Step 10): the single Qwen-72B compliance judge."""

from .base import build_reasoning_engine, compute_fallback_verdict

__all__ = ["build_reasoning_engine", "compute_fallback_verdict"]

"""Semantic matcher factory + the embedder port.

The matcher is an *optional, additive* text-risk source: it emits the same
:class:`TextRiskEvidence` the lexicon does, so it flows through fusion → judge →
report unchanged. Selected with ``AIMW_SEMANTIC_PROVIDER=local`` (default off, so
tests/CI stay offline and the lexicon-only baseline is the A/B control).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...config import SemanticMode, get_settings


@runtime_checkable
class Embedder(Protocol):
    """Turns text into vectors. Real impl is local; tests inject a fake."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


def build_semantic_matcher(mode: SemanticMode):  # -> SemanticMatcher | None
    """Build the local matcher, or ``None`` when semantic matching is off."""
    if mode != "local":
        return None
    from .local import SemanticMatcher, SentenceTransformerEmbedder

    s = get_settings()
    return SemanticMatcher(
        embedder=SentenceTransformerEmbedder(s.semantic_model, s.semantic_device),
        threshold=s.semantic_threshold,
        weight=s.semantic_weight,
    )

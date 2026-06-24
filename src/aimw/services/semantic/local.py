"""Local embedding matcher — no external API, runs on CPU.

Embeds OCR/speech spans with a local sentence-transformers model and flags any
span whose meaning is close (cosine) to a known scam exemplar. Emits
:class:`TextRiskEvidence` citing the nearest exemplar (``~phrase (0.82)``) so a
semantic hit stays as traceable as a lexicon hit — just fuzzy instead of exact.
"""

from __future__ import annotations

import numpy as np

from ...domain.enums import EvidenceSource, RiskCategory
from ...domain.models import OcrResult, TextRiskEvidence, Transcript
from ...logging_config import get_logger
from .base import Embedder
from .exemplars import EXEMPLARS

log = get_logger(__name__)


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.clip(norms, 1e-12, None)


class SentenceTransformerEmbedder:
    """Lazy-loaded local model (only imported/loaded when semantic is enabled)."""

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name, device=device)
        log.info("semantic.model_loaded", model=model_name, device=device)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, batch_size=32, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32).tolist()


class SemanticMatcher:
    """Flags spans semantically close to a scam exemplar."""

    def __init__(self, embedder: Embedder, threshold: float = 0.6, weight: float = 0.8) -> None:
        self._embedder = embedder
        self._threshold = threshold
        self._weight = weight

        # Flatten exemplars and embed them once.
        self._phrases: list[str] = []
        self._categories: list[RiskCategory] = []
        for category, phrases in EXEMPLARS.items():
            for phrase in phrases:
                self._phrases.append(phrase)
                self._categories.append(category)
        self._exemplar_vecs = _normalize(
            np.asarray(self._embedder.embed(self._phrases), dtype=np.float32)
        )
        # category -> indices into the exemplar arrays (for best-per-category).
        self._cat_indices: dict[RiskCategory, list[int]] = {}
        for i, cat in enumerate(self._categories):
            self._cat_indices.setdefault(cat, []).append(i)

    def match(self, ocr: list[OcrResult], transcript: Transcript) -> list[TextRiskEvidence]:
        # Collect every text span with its provenance.
        spans: list[tuple[str, EvidenceSource, float, float | None, float]] = []
        for item in ocr:
            if item.text.strip():
                spans.append((item.text, EvidenceSource.OCR, item.timestamp, None, item.confidence))
        for seg in transcript.segments:
            if seg.text.strip():
                spans.append((seg.text, EvidenceSource.SPEECH, seg.start, seg.end, seg.confidence))
        if not spans:
            return []

        span_vecs = _normalize(
            np.asarray(self._embedder.embed([s[0] for s in spans]), dtype=np.float32)
        )
        sims = span_vecs @ self._exemplar_vecs.T  # (N spans, E exemplars), cosine

        evidence: list[TextRiskEvidence] = []
        for row, (text, source, ts, end, src_conf) in zip(sims, spans):
            for category, idxs in self._cat_indices.items():
                best = max(idxs, key=lambda i: row[i])
                sim = float(row[best])
                if sim < self._threshold:
                    continue
                evidence.append(
                    TextRiskEvidence(
                        timestamp=ts,
                        end=end,
                        source=source,
                        category=category,
                        confidence=round(min(1.0, self._weight * sim * src_conf), 3),
                        text=text,
                        matched_terms=[f"~{self._phrases[best]} ({sim:.2f})"],
                    )
                )
        log.info("semantic.done", findings=len(evidence), spans=len(spans))
        return evidence

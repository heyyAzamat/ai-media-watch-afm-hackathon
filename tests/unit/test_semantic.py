"""Semantic matcher logic — offline, no model download (fake embedder)."""

from __future__ import annotations

import numpy as np

from aimw.domain.enums import EvidenceSource, RiskCategory
from aimw.domain.models import OcrResult, Transcript, TranscriptSegment
from aimw.services.semantic.exemplars import EXEMPLARS
from aimw.services.semantic.local import SemanticMatcher
from aimw.services.text_risk import TextRiskAnalyzer

# A Ponzi exemplar we steer the fake embedder toward.
_PONZI_PHRASE = EXEMPLARS[RiskCategory.PONZI_SCHEME][0]


class FakeEmbedder:
    """Maps known strings to fixed unit vectors so cosine is deterministic.

    The Ponzi exemplar and a paraphrase both map to [1,0,0] (cosine 1.0); every
    other exemplar maps to [0,1,0]; benign text maps to [0,0,1] (orthogonal).
    """

    _ORTHOGONAL = {"the weather is nice and I had lunch", "welcome bonus free spins"}

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if t == _PONZI_PHRASE or t == "your deposit grows twofold each month":
                out.append([1.0, 0.0, 0.0])
            elif t in self._ORTHOGONAL:
                out.append([0.0, 0.0, 1.0])
            else:  # all other exemplars
                out.append([0.0, 1.0, 0.0])
        return np.asarray(out, dtype=np.float32).tolist()


def test_paraphrase_near_exemplar_is_flagged():
    matcher = SemanticMatcher(FakeEmbedder(), threshold=0.6, weight=0.8)
    ocr = [OcrResult(timestamp=3.0, text="your deposit grows twofold each month", confidence=1.0)]
    out = matcher.match(ocr, Transcript())

    ponzi = [e for e in out if e.category == RiskCategory.PONZI_SCHEME]
    assert ponzi, "paraphrase close to a Ponzi exemplar should be flagged"
    ev = ponzi[0]
    assert ev.source == EvidenceSource.OCR
    assert ev.timestamp == 3.0
    assert ev.matched_terms[0].startswith("~")  # cites the nearest exemplar, fuzzy
    assert ev.confidence == 0.8  # weight * sim(1.0) * src_conf(1.0)


def test_benign_text_below_threshold_is_silent():
    matcher = SemanticMatcher(FakeEmbedder(), threshold=0.6, weight=0.8)
    seg = Transcript(segments=[TranscriptSegment(
        start=1.0, end=2.0, text="the weather is nice and I had lunch", confidence=1.0)])
    assert matcher.match([], seg) == []


def test_analyzer_appends_semantic_to_lexicon():
    matcher = SemanticMatcher(FakeEmbedder(), threshold=0.6, weight=0.8)
    analyzer = TextRiskAnalyzer(semantic=matcher)
    # Lexicon-only text for casino + a Ponzi paraphrase the lexicon can't catch.
    ocr = [
        OcrResult(timestamp=1.0, text="welcome bonus free spins", confidence=1.0),
        OcrResult(timestamp=3.0, text="your deposit grows twofold each month", confidence=1.0),
    ]
    cats = {e.category for e in analyzer.analyze(ocr, Transcript())}
    assert RiskCategory.CASINO_ADVERTISING in cats  # from lexicon
    assert RiskCategory.PONZI_SCHEME in cats  # from semantic matcher

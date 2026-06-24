from __future__ import annotations

from aimw.domain.enums import EvidenceSource, RiskCategory
from aimw.domain.models import OcrResult, Transcript, TranscriptSegment
from aimw.services.text_risk import TextRiskAnalyzer


def test_detects_casino_in_ocr():
    analyzer = TextRiskAnalyzer()
    ocr = [OcrResult(timestamp=2.0, text="Welcome bonus 200% free spins jackpot", confidence=0.95)]
    out = analyzer.analyze(ocr, Transcript())
    cats = {e.category for e in out}
    assert RiskCategory.CASINO_ADVERTISING in cats
    casino = next(e for e in out if e.category == RiskCategory.CASINO_ADVERTISING)
    assert casino.source == EvidenceSource.OCR
    assert casino.matched_terms  # explainable: which terms fired
    assert 0 < casino.confidence <= 1


def test_detects_guaranteed_income_in_speech():
    analyzer = TextRiskAnalyzer()
    transcript = Transcript(
        segments=[
            TranscriptSegment(
                start=8.5, end=12.0,
                text="You can make money every day without any risk, guaranteed income.",
                confidence=0.95,
            )
        ]
    )
    out = analyzer.analyze([], transcript)
    cats = {e.category for e in out}
    assert RiskCategory.GUARANTEED_INCOME in cats
    gi = next(e for e in out if e.category == RiskCategory.GUARANTEED_INCOME)
    assert gi.source == EvidenceSource.SPEECH
    assert gi.end == 12.0


def test_no_false_positive_on_benign_text():
    analyzer = TextRiskAnalyzer()
    ocr = [OcrResult(timestamp=1.0, text="Thanks for watching, subscribe!", confidence=0.99)]
    out = analyzer.analyze(ocr, Transcript())
    assert out == []


def test_confidence_tempered_by_ocr_confidence():
    analyzer = TextRiskAnalyzer()
    hi = analyzer.analyze([OcrResult(timestamp=1.0, text="casino jackpot", confidence=1.0)], Transcript())
    lo = analyzer.analyze([OcrResult(timestamp=1.0, text="casino jackpot", confidence=0.5)], Transcript())
    assert hi[0].confidence > lo[0].confidence

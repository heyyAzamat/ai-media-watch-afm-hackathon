"""Step 7 — Text risk analysis over OCR text and speech transcripts.

A transparent, fully-deterministic lexicon/regex engine. Every hit carries the
exact matched terms and source timestamp, so a text risk score is always
traceable to the words that produced it (the core explainability principle).
This runs with zero model dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.enums import EvidenceSource, RiskCategory
from ..domain.models import OcrResult, TextRiskEvidence, Transcript
from ..logging_config import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class _Lexicon:
    category: RiskCategory
    terms: tuple[str, ...]
    weight: float  # base confidence contribution per matched term


# Ordered roughly by severity. Terms are matched case-insensitively with word
# boundaries; multi-word terms match as phrases.
_LEXICONS: tuple[_Lexicon, ...] = (
    _Lexicon(
        RiskCategory.CASINO_ADVERTISING,
        ("casino", "roulette", "slot machine", "slots", "jackpot", "free spins",
         "deposit bonus", "welcome bonus", "1xbet", "1xcasino", "spin to win"),
        0.45,
    ),
    _Lexicon(
        RiskCategory.SPORTS_BETTING,
        ("betting", "bet now", "bookmaker", "odds", "sportsbook", "place your bet",
         "accumulator", "parlay"),
        0.4,
    ),
    _Lexicon(
        RiskCategory.ILLEGAL_GAMBLING,
        ("gambling", "wager", "stake and win", "double your deposit", "deposit and win"),
        0.45,
    ),
    _Lexicon(
        RiskCategory.GUARANTEED_INCOME,
        ("guaranteed income", "guaranteed profit", "guaranteed returns", "passive income",
         "earn daily", "earn money every day", "make money every day", "no risk",
         "without any risk", "risk free", "financial freedom", "earn 1000",
         "earn 1000 dollars", "1000 dollars daily"),
        0.45,
    ),
    _Lexicon(
        RiskCategory.PONZI_SCHEME,
        ("double your money", "triple your money", "200% returns", "guaranteed daily return",
         "withdraw anytime profit", "investment doubles"),
        0.5,
    ),
    _Lexicon(
        RiskCategory.PYRAMID_SCHEME,
        ("recruit members", "downline", "multi level marketing", "mlm",
         "build your team and earn", "join my team"),
        0.5,
    ),
    _Lexicon(
        RiskCategory.REFERRAL_SCAM,
        ("referral", "invite friends", "invite your friends", "promo code", "promocode",
         "link in bio", "use my code", "use my link", "sign up with my link"),
        0.35,
    ),
    _Lexicon(
        RiskCategory.FAKE_INVESTMENT,
        ("crypto investment", "forex signals", "trading bot", "guaranteed trade",
         "investment opportunity", "fund manager", "copy trading"),
        0.4,
    ),
    _Lexicon(
        RiskCategory.FINANCIAL_MANIPULATION,
        ("act now", "limited time", "only today", "last chance", "dont miss out",
         "hurry up", "spots filling fast"),
        0.25,
    ),
    _Lexicon(
        RiskCategory.HIDDEN_ADVERTISING,
        ("sponsored", "paid partnership", "ad", "affiliate link", "discount code"),
        0.2,
    ),
)


def _compile(terms: tuple[str, ...]) -> list[tuple[str, re.Pattern[str]]]:
    compiled = []
    for term in terms:
        escaped = re.escape(term)
        # allow flexible whitespace between words of a phrase
        escaped = escaped.replace(r"\ ", r"\s+")
        compiled.append((term, re.compile(rf"\b{escaped}\b", re.IGNORECASE)))
    return compiled


_COMPILED: tuple[tuple[_Lexicon, list[tuple[str, re.Pattern[str]]]], ...] = tuple(
    (lex, _compile(lex.terms)) for lex in _LEXICONS
)


def _confidence(weight: float, num_hits: int) -> float:
    # Diminishing returns: first hit dominates, extra hits add saturating boost.
    return round(min(1.0, weight + 0.15 * (num_hits - 1) + (0.1 if num_hits > 1 else 0.0)), 3)


def _scan(text: str) -> list[tuple[RiskCategory, float, list[str]]]:
    findings: list[tuple[RiskCategory, float, list[str]]] = []
    for lex, patterns in _COMPILED:
        matched = [term for term, pat in patterns if pat.search(text)]
        if matched:
            findings.append((lex.category, _confidence(lex.weight, len(matched)), matched))
    return findings


class TextRiskAnalyzer:
    """Analyse OCR + transcript text and emit timestamped risk evidence.

    The lexicon scan is always run. An optional ``semantic`` matcher (local
    embeddings, no external API) appends paraphrase-based evidence in the same
    :class:`TextRiskEvidence` shape, so fusion/judge/report need no changes.
    """

    def __init__(self, semantic=None) -> None:  # semantic: SemanticMatcher | None
        self._semantic = semantic

    def analyze(
        self, ocr: list[OcrResult], transcript: Transcript
    ) -> list[TextRiskEvidence]:
        evidence: list[TextRiskEvidence] = []

        for item in ocr:
            for category, confidence, terms in _scan(item.text):
                evidence.append(
                    TextRiskEvidence(
                        timestamp=item.timestamp,
                        source=EvidenceSource.OCR,
                        category=category,
                        # temper by OCR confidence so blurry text counts for less
                        confidence=round(confidence * item.confidence, 3),
                        text=item.text,
                        matched_terms=terms,
                    )
                )

        for seg in transcript.segments:
            for category, confidence, terms in _scan(seg.text):
                evidence.append(
                    TextRiskEvidence(
                        timestamp=seg.start,
                        end=seg.end,
                        source=EvidenceSource.SPEECH,
                        category=category,
                        confidence=round(confidence * seg.confidence, 3),
                        text=seg.text,
                        matched_terms=terms,
                    )
                )

        if self._semantic is not None:
            evidence.extend(self._semantic.match(ocr, transcript))

        evidence.sort(key=lambda e: e.timestamp)
        log.info("text_risk.done", findings=len(evidence))
        return evidence

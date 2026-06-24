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
         "earn 1000 dollars", "1000 dollars daily",
         # Russian — daily-income lures (numeric "доход 3000Р в день" → _REGEX_RULES)
         "доход в день", "доход каждый день", "заработок в день", "пассивный доход",
         "гарантированный доход", "доход без вложений", "без вложений", "без риска",
         "зарабатывай каждый день", "деньги каждый день"),
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
        ("sponsored", "paid partnership", "ad", "affiliate link", "discount code",
         # Off-platform redirect — benign alone (low weight), strong when it
         # corroborates a recruitment/income lure nearby (fusion, Step 8).
         "telegram", "телеграм", "телеграмм", "телеграме", "телеграмме",
         "ссылка в телеграм", "ссылка в телеграмме", "ссылка в тг", "ссылка в описании",
         "ссылка в профиле", "ссылка в шапке", "пиши в телеграм", "пиши в личку",
         "пиши в лс", "подробности в телеграм", "переходи по ссылке"),
        0.2,
    ),
    _Lexicon(
        RiskCategory.ILLICIT_JOB_RECRUITMENT,
        ("работа курьером", "работа курьер", "ищем курьеров", "требуются курьеры",
         "нужны курьеры", "курьер", "курьеры", "лёгкий заработок", "легкий заработок",
         "быстрый заработок", "быстрые деньги", "лёгкие деньги", "легкие деньги",
         "быстрый доход", "подработка", "работа на дому", "удалённая работа",
         "удаленная работа", "работа без опыта", "без опыта", "вакансия курьер",
         # closed-channel drug-courier slang (закладчик recruiting)
         "закладка", "закладки", "оптовик", "склады и закладки"),
        0.45,
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


# Pattern rules for things a fixed lexicon can't enumerate (amounts vary, Russian
# declensions, and OCR noise). (category, weight, pattern).
_REGEX_RULES: tuple[tuple[RiskCategory, float, re.Pattern[str]], ...] = (
    # Courier / "job" recruitment — declension-robust (курьер\w*), but requires a
    # recruitment cue nearby so benign food-delivery talk isn't flagged. High
    # weight: "набирают курьеров без опыта" is a near-diagnostic дроп/закладчик lure.
    (RiskCategory.ILLICIT_JOB_RECRUITMENT, 0.65,
     re.compile(r"(?:набир\w*|набор|требу\w*|ищ\w+|нужн\w*|ваканс\w*|подработ\w*|срочно)"
                r"[^.\n]{0,30}курьер\w*", re.IGNORECASE)),
    # Income claim next to a currency — digit-tolerant: OCR often reads "3000" as
    # Cyrillic "З000", so don't require a literal digit ("Доход от З000 ₽" fires).
    (RiskCategory.GUARANTEED_INCOME, 0.5,
     re.compile(r"доход\w*[^.\n]{0,25}(?:₽|руб\w*|тенге|\bтг\b|\$|€)", re.IGNORECASE)),
    # "<verb> <amount>" income ("доход 3000", "зарабатывай 5000").
    (RiskCategory.GUARANTEED_INCOME, 0.45,
     re.compile(r"(?:доход|заработ\w*|зарплат\w*|\bзп\b|получай\w*|зарабатыва\w*)"
                r"[^.\n]{0,20}\d", re.IGNORECASE)),
    # "<amount> ₽/руб/тенге в день".
    (RiskCategory.GUARANTEED_INCOME, 0.45,
     re.compile(r"(?:от\s+)?\d[\d\s.,]*\s*(?:руб\w*|тенге|₽|тг|р|\$|€)\s*"
                r"[^.\n]{0,4}(?:в|/)\s*день", re.IGNORECASE)),
)


def _scan(text: str) -> list[tuple[RiskCategory, float, list[str]]]:
    findings: list[tuple[RiskCategory, float, list[str]]] = []
    for lex, patterns in _COMPILED:
        matched = [term for term, pat in patterns if pat.search(text)]
        if matched:
            findings.append((lex.category, _confidence(lex.weight, len(matched)), matched))
    for category, weight, pat in _REGEX_RULES:
        m = pat.search(text)
        if m:
            findings.append((category, round(weight, 3), [m.group(0).strip()]))
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

        # OCR splits one on-screen caption across several detections ("Срочно
        # набирают" / "курьеров"). Scan the per-frame concatenation so phrases
        # that span lines still match; group by timestamp (one frame).
        by_frame: dict[float, list[OcrResult]] = {}
        for item in ocr:
            by_frame.setdefault(item.timestamp, []).append(item)
        for ts, items in by_frame.items():
            joined = " ".join(i.text.strip() for i in items if i.text.strip())
            if not joined:
                continue
            src_conf = max(i.confidence for i in items)
            for category, confidence, terms in _scan(joined):
                evidence.append(
                    TextRiskEvidence(
                        timestamp=ts,
                        source=EvidenceSource.OCR,
                        category=category,
                        # temper by OCR confidence so blurry text counts for less
                        confidence=round(confidence * src_conf, 3),
                        text=joined,
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

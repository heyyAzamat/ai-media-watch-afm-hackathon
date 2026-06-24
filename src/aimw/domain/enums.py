"""Enumerations shared across the platform."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Lifecycle of an analysis job."""

    QUEUED = "queued"
    INGESTING = "ingesting"
    EXTRACTING = "extracting"  # scenes + frames
    ANALYZING = "analyzing"  # parallel OCR / speech / visual
    FUSING = "fusing"  # fusion + timeline
    JUDGING = "judging"  # final reasoning engine
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceSource(StrEnum):
    """Where a piece of evidence originated."""

    OCR = "ocr"
    SPEECH = "speech"
    VISUAL = "visual"


class RiskCategory(StrEnum):
    """Canonical taxonomy of harmful / fraudulent financial content."""

    ILLEGAL_GAMBLING = "illegal_gambling"
    CASINO_ADVERTISING = "casino_advertising"
    SPORTS_BETTING = "sports_betting"
    PYRAMID_SCHEME = "pyramid_scheme"
    PONZI_SCHEME = "ponzi_scheme"
    GUARANTEED_INCOME = "guaranteed_income"
    REFERRAL_SCAM = "referral_scam"
    FAKE_INVESTMENT = "fake_investment"
    FINANCIAL_MANIPULATION = "financial_manipulation"
    HIDDEN_ADVERTISING = "hidden_advertising"
    # Easy-money / courier "job" recruitment that redirects off-platform
    # (Telegram). The dominant Russian-language lure: дроп/закладчик recruiting.
    ILLICIT_JOB_RECRUITMENT = "illicit_job_recruitment"
    SUSPICIOUS_FINANCIAL = "suspicious_financial"
    NONE = "none"


# Categories that map onto regulated/illegal activity and should bias the
# score upward when corroborated across modalities.
HIGH_SEVERITY_CATEGORIES: frozenset[RiskCategory] = frozenset(
    {
        RiskCategory.ILLEGAL_GAMBLING,
        RiskCategory.CASINO_ADVERTISING,
        RiskCategory.SPORTS_BETTING,
        RiskCategory.PYRAMID_SCHEME,
        RiskCategory.PONZI_SCHEME,
        RiskCategory.ILLICIT_JOB_RECRUITMENT,
    }
)


class Severity(StrEnum):
    """Severity bucket for a timeline event."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def from_confidence(cls, confidence: float, category: RiskCategory) -> "Severity":
        """Map a confidence score + category to a severity bucket."""
        bias = 0.1 if category in HIGH_SEVERITY_CATEGORIES else 0.0
        score = min(1.0, confidence + bias)
        if score >= 0.75:
            return cls.HIGH
        if score >= 0.45:
            return cls.MEDIUM
        return cls.LOW

"""Reasoning-engine factory + deterministic fallback verdict.

The fallback is what makes the platform robust: if the LLM judge is unreachable
or keeps returning invalid JSON, we still emit a fully-traceable verdict derived
from the fused evidence graph, flagged with ``fallback_used=True``.
"""

from __future__ import annotations

from ...config import get_settings
from ...domain.enums import HIGH_SEVERITY_CATEGORIES, RiskCategory, Severity
from ...domain.models import EvidenceGraph, JudgeVerdict, TimelineEvent, VideoMetadata
from ...logging_config import get_logger
from ...utils.time_utils import format_timestamp
from ..interfaces import ReasoningEngine

log = get_logger(__name__)

_PLACEHOLDER_KEYS = {"", "sk-or-changeme"}


def build_reasoning_engine() -> ReasoningEngine:
    """Return the configured judge, or a deterministic fallback when no key is set."""
    settings = get_settings()
    if settings.openrouter_api_key.strip() in _PLACEHOLDER_KEYS:
        log.warning("reasoning.no_api_key", note="using deterministic fallback judge")
        return FallbackReasoningEngine()
    from .openrouter import OpenRouterReasoningEngine

    return OpenRouterReasoningEngine()


def _aggregate(graph: EvidenceGraph) -> dict[RiskCategory, float]:
    """Noisy-OR aggregate confidence per category across all fused events."""
    from math import prod

    per_cat: dict[RiskCategory, list[float]] = {}
    for ev in graph.events:
        per_cat.setdefault(ev.category, []).append(ev.confidence)
    return {
        cat: round(1.0 - prod(1.0 - min(c, 0.999) for c in confs), 3)
        for cat, confs in per_cat.items()
    }


def compute_fallback_verdict(
    metadata: VideoMetadata, graph: EvidenceGraph, timeline: list[TimelineEvent]
) -> JudgeVerdict:
    """Derive a transparent verdict purely from the evidence graph + timeline."""
    aggregates = _aggregate(graph)
    if not aggregates:
        return JudgeVerdict(
            risk_score=0,
            category=RiskCategory.NONE,
            confidence=0.0,
            summary="No suspicious financial, gambling or fraud indicators were detected.",
            explanation="No corroborating OCR, speech or visual evidence crossed the "
            "risk thresholds.",
            model="fallback-deterministic",
            fallback_used=True,
        )

    category = max(aggregates, key=lambda c: aggregates[c])
    base_conf = aggregates[category]
    distinct_sources = {s for ev in graph.events for s in ev.sources}
    corroboration_bonus = 0.1 * (len(distinct_sources) - 1)
    severity_bonus = 0.1 if category in HIGH_SEVERITY_CATEGORIES else 0.0
    confidence = round(min(1.0, base_conf), 3)
    risk_score = int(round(min(1.0, base_conf + corroboration_bonus + severity_bonus) * 100))

    high_events = [ev for ev in timeline if ev.severity in (Severity.HIGH, Severity.MEDIUM)]
    suspicious_ts = sorted({round(ev.start, 1) for ev in high_events})
    supporting = [
        f"{format_timestamp(ev.start)} {ev.category.value}: {', '.join(ev.evidence[:2])}"
        for ev in high_events[:8]
    ]
    label = category.value.replace("_", " ")
    summary = (
        f"The video shows strong indicators of {label}, corroborated across "
        f"{len(distinct_sources)} modality/modalities ({', '.join(sorted(s.value for s in distinct_sources))})."
    )
    explanation = (
        f"Deterministic fallback verdict. Highest aggregate category is '{label}' "
        f"(confidence {confidence}). {len(high_events)} medium/high-severity timeline "
        f"events support this assessment."
    )

    return JudgeVerdict(
        risk_score=risk_score,
        category=category,
        confidence=confidence,
        summary=summary,
        explanation=explanation,
        supporting_evidence=supporting,
        suspicious_timestamps=suspicious_ts,
        model="fallback-deterministic",
        fallback_used=True,
    )


class FallbackReasoningEngine:
    """A ReasoningEngine that never calls a network model (offline/dev/tests)."""

    model = "fallback-deterministic"

    async def judge(self, context: dict) -> JudgeVerdict:
        return compute_fallback_verdict(
            context["metadata"], context["graph"], context["timeline"]
        )

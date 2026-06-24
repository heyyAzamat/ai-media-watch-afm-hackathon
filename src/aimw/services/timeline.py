"""Step 9 — Timeline generation + Evidence Player markers.

Turns the fused evidence graph into a chronological list of suspicious moments
(a core output) and into frontend-jumpable markers (the Evidence Player
requirement). Each timeline event keeps its supporting evidence + source
modalities so the frontend can explain every flag.
"""

from __future__ import annotations

from ..domain.enums import RiskCategory, Severity
from ..domain.models import (
    EvidenceGraph,
    EvidencePlayerMarker,
    FusedEvent,
    TimelineEvent,
)
from ..logging_config import get_logger
from ..utils.time_utils import format_timestamp

log = get_logger(__name__)

_SEVERITY_ICON: dict[Severity, str] = {
    Severity.HIGH: "🔴",
    Severity.MEDIUM: "🟠",
    Severity.LOW: "🟡",
}

_CATEGORY_LABEL: dict[RiskCategory, str] = {
    RiskCategory.ILLEGAL_GAMBLING: "Illegal gambling",
    RiskCategory.CASINO_ADVERTISING: "Casino promotion",
    RiskCategory.SPORTS_BETTING: "Sports betting",
    RiskCategory.PYRAMID_SCHEME: "Pyramid scheme",
    RiskCategory.PONZI_SCHEME: "Ponzi scheme",
    RiskCategory.GUARANTEED_INCOME: "Guaranteed income claim",
    RiskCategory.REFERRAL_SCAM: "Referral scheme",
    RiskCategory.FAKE_INVESTMENT: "Fake investment",
    RiskCategory.FINANCIAL_MANIPULATION: "Manipulation tactic",
    RiskCategory.HIDDEN_ADVERTISING: "Hidden advertising",
    RiskCategory.SUSPICIOUS_FINANCIAL: "Suspicious financial content",
}


class TimelineService:
    def __init__(self, marker_min_severity: Severity = Severity.MEDIUM) -> None:
        self._marker_min = marker_min_severity

    def build(self, graph: EvidenceGraph) -> tuple[list[TimelineEvent], list[EvidencePlayerMarker]]:
        events = [self._to_timeline_event(e) for e in graph.events]
        events.sort(key=lambda e: e.start)
        markers = [
            self._to_marker(ev)
            for ev in events
            if self._severity_rank(ev.severity) >= self._severity_rank(self._marker_min)
        ]
        log.info("timeline.done", events=len(events), markers=len(markers))
        return events, markers

    def _to_timeline_event(self, event: FusedEvent) -> TimelineEvent:
        severity = Severity.from_confidence(event.confidence, event.category)
        evidence = [r.detail for r in event.refs if r.detail][:8]
        return TimelineEvent(
            start=event.start,
            end=event.end,
            severity=severity,
            category=event.category,
            confidence=event.confidence,
            evidence=evidence,
            sources=event.sources,
        )

    def _to_marker(self, ev: TimelineEvent) -> EvidencePlayerMarker:
        severity = ev.severity
        label = _CATEGORY_LABEL.get(ev.category, ev.category.value.replace("_", " ").title())
        return EvidencePlayerMarker(
            timestamp=ev.start,
            label=f"{label} detected",
            severity=severity,
            icon=_SEVERITY_ICON[severity],
            display_time=format_timestamp(ev.start),
        )

    @staticmethod
    def _severity_rank(severity: Severity) -> int:
        return {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}[severity]

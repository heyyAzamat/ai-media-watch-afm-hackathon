from __future__ import annotations

from aimw.domain.enums import EvidenceSource, RiskCategory, Severity
from aimw.domain.models import EvidenceRef, EvidenceGraph, FusedEvent
from aimw.services.timeline import TimelineService
from aimw.utils.ids import new_event_id


def _event(start, end, category, conf):
    return FusedEvent(
        event_id=new_event_id(), start=start, end=end, category=category, confidence=conf,
        sources=[EvidenceSource.OCR, EvidenceSource.VISUAL],
        refs=[EvidenceRef(source=EvidenceSource.OCR, timestamp=start, category=category,
                          confidence=conf, detail="roulette interface")],
    )


def test_builds_sorted_timeline_with_markers():
    graph = EvidenceGraph(
        events=[
            _event(32.2, 38.5, RiskCategory.ILLEGAL_GAMBLING, 0.94),
            _event(5.0, 6.0, RiskCategory.HIDDEN_ADVERTISING, 0.2),
        ]
    )
    events, markers = TimelineService().build(graph)
    assert [e.start for e in events] == sorted(e.start for e in events)
    high = next(e for e in events if e.category == RiskCategory.ILLEGAL_GAMBLING)
    assert high.severity == Severity.HIGH
    assert high.evidence  # carries explainable evidence
    # only medium+ severity events become player markers
    assert all(m.icon in ("🔴", "🟠") for m in markers)
    assert any(m.display_time == "00:32" for m in markers)


def test_low_severity_excluded_from_markers():
    graph = EvidenceGraph(events=[_event(5.0, 6.0, RiskCategory.HIDDEN_ADVERTISING, 0.2)])
    _, markers = TimelineService().build(graph)
    assert markers == []

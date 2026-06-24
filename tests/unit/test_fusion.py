from __future__ import annotations

from aimw.domain.enums import EvidenceSource, RiskCategory
from aimw.domain.models import TextRiskEvidence, VisualDetection
from aimw.services.fusion import FusionService


def test_merges_nearby_same_category_across_modalities():
    fusion = FusionService(window_seconds=1.5)
    text = [
        TextRiskEvidence(timestamp=42.1, source=EvidenceSource.OCR,
                         category=RiskCategory.CASINO_ADVERTISING, confidence=0.8,
                         text="casino bonus", matched_terms=["casino", "bonus"]),
        TextRiskEvidence(timestamp=42.3, source=EvidenceSource.SPEECH,
                         category=RiskCategory.CASINO_ADVERTISING, confidence=0.7,
                         text="best casino", matched_terms=["casino"]),
    ]
    visual = [VisualDetection(timestamp=42.6, scores={"casino": 0.9}, evidence=["roulette wheel"])]

    graph = fusion.fuse(text, visual)
    casino_events = [e for e in graph.events if e.category == RiskCategory.CASINO_ADVERTISING]
    assert len(casino_events) == 1
    ev = casino_events[0]
    assert ev.start == 42.1
    assert ev.end >= 42.6
    assert set(ev.sources) == {EvidenceSource.OCR, EvidenceSource.SPEECH, EvidenceSource.VISUAL}
    # corroboration raises confidence above any single source
    assert ev.confidence > 0.8


def test_distant_events_not_merged():
    fusion = FusionService(window_seconds=1.5)
    text = [
        TextRiskEvidence(timestamp=5.0, source=EvidenceSource.OCR,
                         category=RiskCategory.CASINO_ADVERTISING, confidence=0.8, text="casino"),
        TextRiskEvidence(timestamp=30.0, source=EvidenceSource.OCR,
                         category=RiskCategory.CASINO_ADVERTISING, confidence=0.8, text="casino"),
    ]
    graph = fusion.fuse(text, [])
    assert len([e for e in graph.events if e.category == RiskCategory.CASINO_ADVERTISING]) == 2


def test_adjacency_links_overlapping_different_categories():
    fusion = FusionService(window_seconds=1.5)
    text = [
        TextRiskEvidence(timestamp=10.0, source=EvidenceSource.OCR,
                         category=RiskCategory.CASINO_ADVERTISING, confidence=0.8, text="casino"),
        TextRiskEvidence(timestamp=10.4, source=EvidenceSource.SPEECH,
                         category=RiskCategory.REFERRAL_SCAM, confidence=0.7, text="invite friends"),
    ]
    graph = fusion.fuse(text, [])
    assert any(neighbors for neighbors in graph.adjacency.values())

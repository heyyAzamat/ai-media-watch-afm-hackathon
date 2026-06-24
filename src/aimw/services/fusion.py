"""Step 8 — Evidence fusion.

Normalises OCR/speech text-risk evidence and visual detections into a single
stream of :class:`EvidenceRef`, then merges temporally-close, same-category
evidence into cross-modal :class:`FusedEvent` objects. Co-occurring events of
different categories are linked into an adjacency map, forming the unified
evidence graph. Confidence is combined with a noisy-OR rule so corroboration
across modalities raises confidence (never lowers it).
"""

from __future__ import annotations

from math import prod

from ..config import get_settings
from ..domain.enums import EvidenceSource, RiskCategory
from ..domain.models import (
    EvidenceGraph,
    EvidenceRef,
    FusedEvent,
    TextRiskEvidence,
    VisualDetection,
)
from ..logging_config import get_logger
from ..utils.ids import new_event_id
from ..utils.time_utils import overlaps

log = get_logger(__name__)

# Map VLM labels to risk categories for fusion.
_VISUAL_CATEGORY_MAP: dict[str, RiskCategory] = {
    "casino": RiskCategory.CASINO_ADVERTISING,
    "roulette_wheel": RiskCategory.ILLEGAL_GAMBLING,
    "slot_machine": RiskCategory.ILLEGAL_GAMBLING,
    "sports_betting_app": RiskCategory.SPORTS_BETTING,
    "bookmaker_interface": RiskCategory.SPORTS_BETTING,
    "crypto_scam": RiskCategory.FAKE_INVESTMENT,
    "fake_profit_screenshot": RiskCategory.FAKE_INVESTMENT,
    "luxury_marketing": RiskCategory.FINANCIAL_MANIPULATION,
    "referral_marketing": RiskCategory.REFERRAL_SCAM,
    "guaranteed_income_claim": RiskCategory.GUARANTEED_INCOME,
    "urgency_tactics": RiskCategory.FINANCIAL_MANIPULATION,
    "manipulation_tactics": RiskCategory.FINANCIAL_MANIPULATION,
    "emotional_pressure": RiskCategory.FINANCIAL_MANIPULATION,
}


def _noisy_or(confidences: list[float]) -> float:
    if not confidences:
        return 0.0
    combined = 1.0 - prod(1.0 - min(max(c, 0.0), 0.999) for c in confidences)
    return round(combined, 3)


class FusionService:
    def __init__(self, window_seconds: float | None = None, visual_threshold: float = 0.5) -> None:
        self._window = window_seconds if window_seconds is not None \
            else get_settings().fusion_window_seconds
        self._visual_threshold = visual_threshold

    # ── normalisation ────────────────────────────────────────────────────────
    def _refs_from_text(self, text_risk: list[TextRiskEvidence]) -> list[EvidenceRef]:
        return [
            EvidenceRef(
                source=e.source,
                timestamp=e.timestamp,
                end=e.end,
                category=e.category,
                confidence=e.confidence,
                detail=f"{e.text} [{', '.join(e.matched_terms)}]",
            )
            for e in text_risk
        ]

    def _refs_from_visual(self, visual: list[VisualDetection]) -> list[EvidenceRef]:
        refs: list[EvidenceRef] = []
        for det in visual:
            for label, score in det.scores.items():
                if score < self._visual_threshold:
                    continue
                category = _VISUAL_CATEGORY_MAP.get(label)
                if category is None:
                    continue
                detail = label.replace("_", " ")
                if det.evidence:
                    detail += f": {', '.join(det.evidence[:3])}"
                refs.append(
                    EvidenceRef(
                        source=EvidenceSource.VISUAL,
                        timestamp=det.timestamp,
                        category=category,
                        confidence=round(score, 3),
                        detail=detail,
                    )
                )
        return refs

    # ── fusion ───────────────────────────────────────────────────────────────
    def fuse(
        self, text_risk: list[TextRiskEvidence], visual: list[VisualDetection]
    ) -> EvidenceGraph:
        refs = self._refs_from_text(text_risk) + self._refs_from_visual(visual)
        refs.sort(key=lambda r: r.timestamp)

        by_category: dict[RiskCategory, list[EvidenceRef]] = {}
        for ref in refs:
            by_category.setdefault(ref.category, []).append(ref)

        events: list[FusedEvent] = []
        for category, group in by_category.items():
            events.extend(self._merge_group(category, group))

        events.sort(key=lambda e: (e.start, -e.confidence))
        adjacency = self._build_adjacency(events)
        log.info("fusion.done", events=len(events))
        return EvidenceGraph(events=events, adjacency=adjacency)

    def _merge_group(self, category: RiskCategory, group: list[EvidenceRef]) -> list[FusedEvent]:
        events: list[FusedEvent] = []
        cluster: list[EvidenceRef] = []
        cluster_end = 0.0

        def flush() -> None:
            if not cluster:
                return
            start = min(r.timestamp for r in cluster)
            end = max((r.end or r.timestamp) for r in cluster)
            sources = sorted({r.source for r in cluster}, key=lambda s: s.value)
            base = _noisy_or([r.confidence for r in cluster])
            # corroboration bonus when 2+ distinct modalities agree
            bonus = 0.05 * (len(sources) - 1)
            confidence = round(min(1.0, base + bonus), 3)
            events.append(
                FusedEvent(
                    event_id=new_event_id(),
                    start=round(start, 3),
                    end=round(end, 3),
                    category=category,
                    confidence=confidence,
                    sources=list(sources),
                    refs=list(cluster),
                )
            )

        for ref in group:
            ref_end = ref.end or ref.timestamp
            if not cluster or ref.timestamp - cluster_end <= self._window:
                cluster.append(ref)
                cluster_end = max(cluster_end, ref_end)
            else:
                flush()
                cluster = [ref]
                cluster_end = ref_end
        flush()
        return events

    def _build_adjacency(self, events: list[FusedEvent]) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {e.event_id: [] for e in events}
        for i, a in enumerate(events):
            for b in events[i + 1 :]:
                if a.category == b.category:
                    continue
                if overlaps(a.start, a.end, b.start, b.end, slack=self._window):
                    adjacency[a.event_id].append(b.event_id)
                    adjacency[b.event_id].append(a.event_id)
        return adjacency

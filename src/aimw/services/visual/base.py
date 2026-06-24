"""Visual provider factory + the shared VLM prompt (Step 6)."""

from __future__ import annotations

from ...config import ProviderMode
from ..interfaces import VisualProvider

# The labels the VLM must score (0..1). Kept here so mock and real providers
# share one contract and the fusion stage can rely on a stable label set.
VISUAL_LABELS: tuple[str, ...] = (
    "casino",
    "roulette_wheel",
    "slot_machine",
    "sports_betting_app",
    "bookmaker_interface",
    "crypto_scam",
    "fake_profit_screenshot",
    "luxury_marketing",
    "referral_marketing",
    "guaranteed_income_claim",
    "urgency_tactics",
    "manipulation_tactics",
    "emotional_pressure",
)

VISUAL_PROMPT = """You are a visual risk analyst for financial-crime and gambling compliance.
Analyze the image and detect the presence of each of the following, scoring 0.0-1.0:
- casino interfaces, roulette wheels, slot machines
- sports betting apps, bookmaker interfaces
- cryptocurrency scams, fake profit screenshots
- luxury lifestyle marketing, referral marketing
- guaranteed income claims, urgency/manipulation/emotional-pressure tactics

Return ONLY valid JSON of the form:
{"casino": 0.0, "roulette_wheel": 0.0, "slot_machine": 0.0, "sports_betting_app": 0.0,
 "bookmaker_interface": 0.0, "crypto_scam": 0.0, "fake_profit_screenshot": 0.0,
 "luxury_marketing": 0.0, "referral_marketing": 0.0, "guaranteed_income_claim": 0.0,
 "urgency_tactics": 0.0, "manipulation_tactics": 0.0, "emotional_pressure": 0.0,
 "evidence": ["short phrase", "..."]}"""


class _NullVisualProvider:
    """Visual analysis turned off — returns no detections (honest demo,
    no fabrication, no external VLM)."""

    name = "disabled-visual"

    async def analyze(self, keyframes):  # noqa: ANN001, ANN201
        return []


def build_visual_provider(mode: ProviderMode) -> VisualProvider:
    if mode == "real":
        from .qwen_vl import QwenVLProvider

        return QwenVLProvider()
    if mode == "disabled":
        return _NullVisualProvider()
    from .mock import MockVisualProvider

    return MockVisualProvider()

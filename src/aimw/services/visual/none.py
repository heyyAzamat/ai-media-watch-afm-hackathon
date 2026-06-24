"""No-op visual provider for the data-sovereign CPU profile.

Returns no detections at all. Unlike the mock provider (which emits scripted,
fabricated detections for tests), this is safe for a real run with no VLM: the
report simply carries no visual signal rather than invented evidence. Selected
with ``AIMW_VISUAL_PROVIDER=none``.
"""

from __future__ import annotations

from ...domain.models import Frame, VisualDetection


class NoneVisualProvider:
    name = "none"

    async def analyze(self, keyframes: list[Frame]) -> list[VisualDetection]:
        return []

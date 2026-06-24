"""OCR provider factory."""

from __future__ import annotations

from ...config import ProviderMode
from ..interfaces import OcrProvider


class _NullOcrProvider:
    """OCR turned off — returns no detections (honest demo, no fabrication)."""

    name = "disabled-ocr"

    async def run(self, frames):  # noqa: ANN001, ANN201
        return []


def build_ocr_provider(mode: ProviderMode) -> OcrProvider:
    if mode == "real":
        from .paddle import PaddleOcrProvider

        return PaddleOcrProvider()
    if mode == "disabled":
        return _NullOcrProvider()
    from .mock import MockOcrProvider

    return MockOcrProvider()

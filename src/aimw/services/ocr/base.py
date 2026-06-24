"""OCR provider factory."""

from __future__ import annotations

from ...config import ProviderMode
from ..interfaces import OcrProvider


def build_ocr_provider(mode: ProviderMode) -> OcrProvider:
    if mode == "real":
        from .paddle import PaddleOcrProvider

        return PaddleOcrProvider()
    from .mock import MockOcrProvider

    return MockOcrProvider()

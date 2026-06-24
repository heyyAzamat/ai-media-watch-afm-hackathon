"""The 'disabled' provider mode returns empty results (no fabrication).

This is what lets an honest demo run on real speech only, with OCR/visual
turned off entirely — as opposed to 'mock', which injects a scripted casino
scenario and would flag every video."""
from __future__ import annotations

import pytest

from aimw.services.ocr import build_ocr_provider
from aimw.services.speech import build_speech_provider
from aimw.services.visual import build_visual_provider


@pytest.mark.asyncio
async def test_disabled_ocr_returns_empty():
    provider = build_ocr_provider("disabled")
    assert await provider.run([]) == []


@pytest.mark.asyncio
async def test_disabled_visual_returns_empty():
    provider = build_visual_provider("disabled")
    assert await provider.analyze([]) == []


@pytest.mark.asyncio
async def test_disabled_speech_returns_empty_transcript():
    provider = build_speech_provider("disabled")
    transcript = await provider.transcribe(None)
    assert transcript.segments == []

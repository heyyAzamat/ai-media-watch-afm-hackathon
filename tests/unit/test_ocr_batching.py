"""Batching logic of PaddleOcrProvider, tested with a fake engine (no paddle).

Verifies that one predict() call covers a chunk of frames, results map back to
the correct frame/timestamp, and that misaligned/failed batches fall back to
per-frame parsing without dropping frames.
"""

from __future__ import annotations

import pytest

from aimw.domain.models import Frame
from aimw.services.ocr.paddle import PaddleOcrProvider


def _frames(n: int) -> list[Frame]:
    return [Frame(frame_id=f"f{i}", timestamp=float(i), path=f"/x/{i}.jpg") for i in range(n)]


def _result(text: str) -> dict:
    # mimics a PaddleOCR 3.x OCRResult (dict subclass)
    return {"rec_texts": [text], "rec_scores": [0.97], "rec_polys": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}


class _FakeEngine:
    """Records predict() call sizes and returns one result per input image."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    def predict(self, paths):  # noqa: ANN001
        self.calls.append(len(paths))
        return [_result(f"text-{p.split('/')[-1]}") for p in paths]


class _MisalignedEngine:
    def predict(self, paths):  # noqa: ANN001
        return [_result("only-one")]  # wrong length -> should trigger fallback


def _provider(engine, batch_size: int) -> PaddleOcrProvider:
    p = PaddleOcrProvider()
    p._engine = engine  # inject, skip real init
    p._batch_size = batch_size
    return p


@pytest.mark.asyncio
async def test_batched_predict_one_call_per_chunk():
    engine = _FakeEngine()
    provider = _provider(engine, batch_size=4)
    results = await provider.run(_frames(10))
    # 10 frames / batch 4 -> chunk sizes [4, 4, 2]
    assert engine.calls == [4, 4, 2]
    assert len(results) == 10
    # results align to frame timestamps
    assert {r.timestamp for r in results} == {float(i) for i in range(10)}
    assert results[3].text == "text-3.jpg"


@pytest.mark.asyncio
async def test_single_batch_when_batch_size_covers_all():
    engine = _FakeEngine()
    provider = _provider(engine, batch_size=32)
    results = await provider.run(_frames(5))
    assert engine.calls == [5]  # one batched call
    assert len(results) == 5


@pytest.mark.asyncio
async def test_misaligned_batch_falls_back_per_frame():
    provider = _provider(_MisalignedEngine(), batch_size=8)
    results = await provider.run(_frames(3))
    # fallback re-runs each frame individually via predict([path]); each returns
    # one "only-one" result -> 3 results, one per frame, none dropped.
    assert len(results) == 3
    assert {r.timestamp for r in results} == {0.0, 1.0, 2.0}


@pytest.mark.asyncio
async def test_empty_frames_no_calls():
    engine = _FakeEngine()
    provider = _provider(engine, batch_size=8)
    assert await provider.run([]) == []
    assert engine.calls == []

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from aimw.domain.models import Frame
from aimw.utils.frames import dedup_frames, dhash, hamming

pytestmark = pytest.mark.filterwarnings("ignore")


def _save_gradient(path, vertical: bool) -> None:
    row = np.arange(64, dtype=np.uint8)
    arr = np.tile(row, (64, 1))
    if vertical:
        arr = arr.T
    Image.fromarray(arr, mode="L").convert("RGB").save(path)


def _frames(paths) -> list[Frame]:
    return [
        Frame(frame_id=f"f{i}", timestamp=float(i), path=str(p))
        for i, p in enumerate(paths)
    ]


def test_dhash_identical_images_match(tmp_path):
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    _save_gradient(a, vertical=False)
    _save_gradient(b, vertical=False)
    assert dhash(str(a)) is not None
    assert hamming(dhash(str(a)), dhash(str(b))) == 0


def test_dhash_distinct_images_differ(tmp_path):
    a, c = tmp_path / "a.jpg", tmp_path / "c.jpg"
    _save_gradient(a, vertical=False)
    _save_gradient(c, vertical=True)
    assert hamming(dhash(str(a)), dhash(str(c))) > 6


def test_dedup_collapses_near_duplicates(tmp_path):
    a, b, c = tmp_path / "a.jpg", tmp_path / "b.jpg", tmp_path / "c.jpg"
    _save_gradient(a, vertical=False)
    _save_gradient(b, vertical=False)  # duplicate of a
    _save_gradient(c, vertical=True)  # distinct
    kept = dedup_frames(_frames([a, b, c]), threshold=6)
    assert len(kept) == 2
    assert kept[0].timestamp == 0.0  # first occurrence kept
    assert kept[1].timestamp == 2.0


def test_unreadable_frames_are_kept(tmp_path):
    frames = _frames([tmp_path / "missing1.jpg", tmp_path / "missing2.jpg"])
    # cannot hash -> never silently dropped
    assert len(dedup_frames(frames)) == 2

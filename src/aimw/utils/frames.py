"""Frame selection helpers — cut OCR cost without losing on-screen text.

On-screen text changes at scene/cut granularity, not every second, so OCR-ing
every 1 fps frame re-reads the same overlay many times. ``dedup_frames`` keeps
only visually-distinct frames using a difference hash (dHash), which is the
single biggest accuracy-preserving speedup for the OCR stage.
"""

from __future__ import annotations

from ..domain.models import Frame
from ..logging_config import get_logger

log = get_logger(__name__)


def dhash(path: str, hash_size: int = 8) -> int | None:
    """64-bit difference hash of an image, or None if it can't be read."""
    resized = None
    try:
        import cv2

        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            resized = cv2.resize(img, (hash_size + 1, hash_size))
    except Exception:  # noqa: BLE001
        resized = None
    if resized is None:
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(path).convert("L").resize((hash_size + 1, hash_size))
            resized = np.asarray(img)
        except Exception:  # noqa: BLE001
            return None

    bits = 0
    for row in resized:
        for x in range(hash_size):
            bits = (bits << 1) | int(row[x + 1] > row[x])
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def dedup_frames(frames: list[Frame], threshold: int = 6) -> list[Frame]:
    """Keep first occurrence of each visually-distinct frame (time order).

    Frames whose image cannot be hashed are always kept (never silently drop
    data). With ``threshold`` Hamming distance, near-identical frames collapse.
    """
    kept: list[Frame] = []
    seen: list[int] = []
    for frame in frames:
        h = dhash(frame.path)
        if h is None:
            kept.append(frame)
            continue
        if any(hamming(h, prev) <= threshold for prev in seen):
            continue
        seen.append(h)
        kept.append(frame)
    return kept

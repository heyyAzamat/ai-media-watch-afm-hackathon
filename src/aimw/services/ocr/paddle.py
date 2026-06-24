"""Real OCR provider backed by PaddleOCR (Step 4).

Runs PaddleOCR over each extracted frame. Inference is offloaded to a thread
pool so the async orchestrator can run OCR concurrently with speech + visual.
Requires the ``ml`` extra (paddleocr, paddlepaddle).

The provider is robust to both PaddleOCR generations:
  - 2.x : ``engine.ocr(path)`` -> ``[[[box, (text, score)], ...]]``
  - 3.x : ``engine.predict(path)`` -> list of dict-like results with
          ``rec_texts`` / ``rec_scores`` / ``rec_polys``.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from ...domain.models import Frame, OcrResult
from ...logging_config import get_logger

log = get_logger(__name__)


class PaddleOcrProvider:
    name = "paddleocr"

    def __init__(self, lang: str = "en", min_confidence: float = 0.5) -> None:
        self._lang = lang
        self._min_conf = min_confidence
        self._engine = None  # lazily initialised (heavy)
        # Single worker: PaddleOCR engines are not thread-safe, so predict()
        # calls must be serialised. The executor still keeps OCR off the event
        # loop so speech + visual run concurrently with it.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddleocr")

    def _ensure_engine(self):  # noqa: ANN201
        if self._engine is None:
            from paddleocr import PaddleOCR

            # 3.x constructor (use_textline_orientation); fall back to 2.x kwargs.
            try:
                self._engine = PaddleOCR(lang=self._lang, use_textline_orientation=True)
            except TypeError:
                self._engine = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)
        return self._engine

    @staticmethod
    def _poly_bbox(poly: Any) -> list[float] | None:
        try:
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            return [min(xs), min(ys), max(xs), max(ys)]
        except Exception:  # noqa: BLE001
            return None

    def _parse(self, raw: Any, frame: Frame) -> list[OcrResult]:
        out: list[OcrResult] = []
        for res in raw or []:
            # ── 3.x: dict-like result (OCRResult subclasses dict) ────────────
            if isinstance(res, dict) and "rec_texts" in res:
                texts = res.get("rec_texts") or []
                scores = res.get("rec_scores") or []
                polys = res.get("rec_polys") or res.get("dt_polys") or []
                for i, text in enumerate(texts):
                    conf = float(scores[i]) if i < len(scores) else 1.0
                    if conf < self._min_conf or not str(text).strip():
                        continue
                    bbox = self._poly_bbox(polys[i]) if i < len(polys) else None
                    out.append(
                        OcrResult(timestamp=frame.timestamp, text=str(text).strip(),
                                  confidence=conf, frame_id=frame.frame_id, bbox=bbox)
                    )
                continue
            # ── 2.x: res is a "page" = list of [box, (text, score)] ──────────
            for line in res or []:
                try:
                    box, (text, conf) = line
                except (ValueError, TypeError):
                    continue
                if float(conf) < self._min_conf or not str(text).strip():
                    continue
                out.append(
                    OcrResult(timestamp=frame.timestamp, text=str(text).strip(),
                              confidence=float(conf), frame_id=frame.frame_id,
                              bbox=self._poly_bbox(box))
                )
        return out

    def _run_frame(self, frame: Frame) -> list[OcrResult]:
        engine = self._ensure_engine()
        try:
            raw = engine.predict(frame.path) if hasattr(engine, "predict") else engine.ocr(frame.path)
        except Exception as exc:  # noqa: BLE001
            try:
                raw = engine.ocr(frame.path)  # legacy fallback
            except Exception as exc2:  # noqa: BLE001
                log.warning("ocr.frame_failed", frame_id=frame.frame_id,
                            error=f"{exc} / {exc2}")
                return []
        return self._parse(raw, frame)

    async def run(self, frames: list[Frame]) -> list[OcrResult]:
        loop = asyncio.get_running_loop()
        results: list[OcrResult] = []
        # Serialised on a single-worker executor (engine is not thread-safe),
        # but still awaited so the event loop keeps speech + visual moving.
        for frame in frames:
            sub = await loop.run_in_executor(self._executor, partial(self._run_frame, frame))
            results.extend(sub)
        log.info("ocr.paddle.done", frames=len(frames), detections=len(results))
        return results

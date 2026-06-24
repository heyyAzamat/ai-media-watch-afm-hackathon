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

from ...config import get_settings
from ...domain.models import Frame, OcrResult
from ...logging_config import get_logger

log = get_logger(__name__)


class PaddleOcrProvider:
    name = "paddleocr"

    def __init__(self, lang: str | None = None, min_confidence: float | None = None) -> None:
        settings = get_settings()
        self._lang = lang or settings.ocr_lang
        self._min_conf = settings.ocr_min_confidence if min_confidence is None else min_confidence
        self._det_model = settings.ocr_det_model_name
        self._rec_model = settings.ocr_rec_model_name
        self._use_doc_preproc = settings.ocr_use_doc_preprocessing
        self._device = settings.ocr_device
        self._batch_size = max(1, settings.ocr_batch_size)
        self._engine = None  # lazily initialised (heavy)
        # Single worker: PaddleOCR engines are not thread-safe, so predict()
        # calls must be serialised. The executor still keeps OCR off the event
        # loop so speech + visual run concurrently with it. With batching we make
        # one predict() call per chunk of frames rather than one per frame.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paddleocr")

    def _engine_attempts(self) -> list[dict]:
        """Constructor kwargs to try, fastest first, degrading gracefully.

        Lighter mobile models + disabled document preprocessing (orientation /
        unwarping / textline-orientation — meant for scanned docs, not upright
        video overlays) are tried first; falls back to PaddleOCR defaults, then
        to the 2.x legacy constructor.
        """
        # enable_mkldnn=False is REQUIRED on PaddlePaddle 3.x CPU: the oneDNN +
        # new-PIR executor path crashes on every frame with
        # "ConvertPirAttribute2RuntimeAttribute not support" — disabling oneDNN
        # routes to the standard CPU kernels and OCR works.
        base: dict = {"lang": self._lang, "enable_mkldnn": False}
        if not self._use_doc_preproc:
            base.update(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        light = dict(base)
        if self._det_model:
            light["text_detection_model_name"] = self._det_model
        if self._rec_model:
            light["text_recognition_model_name"] = self._rec_model
        # Fastest first; each fallback drops the kwargs a given version may reject
        # (batch size, then device, then model names), preserving GPU/device use
        # as long as possible.
        fastest = dict(light, device=self._device, text_recognition_batch_size=self._batch_size)
        return [
            fastest,  # mobile + no doc preproc + device + batch size
            dict(light, device=self._device),  # drop batch-size kwarg
            dict(base, device=self._device),  # drop model names
            {"lang": self._lang, "enable_mkldnn": False},  # 3.x bundled defaults
            {"use_angle_cls": True, "lang": self._lang, "show_log": False},  # 2.x legacy
        ]

    def _ensure_engine(self):  # noqa: ANN201
        if self._engine is None:
            from paddleocr import PaddleOCR

            last_exc: Exception | None = None
            for kwargs in self._engine_attempts():
                try:
                    self._engine = PaddleOCR(**kwargs)
                    log.info(
                        "ocr.paddle.engine_ready",
                        det=kwargs.get("text_detection_model_name", "default"),
                        rec=kwargs.get("text_recognition_model_name", "default"),
                        device=kwargs.get("device", "cpu"),
                        rec_batch=kwargs.get("text_recognition_batch_size"),
                        doc_preproc=self._use_doc_preproc,
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    log.warning("ocr.paddle.engine_attempt_failed", error=str(exc)[:120])
            if self._engine is None:
                raise RuntimeError(f"could not initialise PaddleOCR: {last_exc}")
        return self._engine

    @staticmethod
    def _poly_bbox(poly: Any) -> list[float] | None:
        try:
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            return [min(xs), min(ys), max(xs), max(ys)]
        except Exception:  # noqa: BLE001
            return None

    def _parse_result(self, res: Any, frame: Frame) -> list[OcrResult]:
        """Parse the result for a SINGLE image (3.x dict-like, or a 2.x page)."""
        out: list[OcrResult] = []
        # ── 3.x: dict-like result (OCRResult subclasses dict) ────────────────
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
            return out
        # ── 2.x: res is a "page" = list of [box, (text, score)] ──────────────
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

    def _parse(self, raw: Any, frame: Frame) -> list[OcrResult]:
        """Parse the LIST that predict()/ocr() returns for a single image."""
        out: list[OcrResult] = []
        for res in raw or []:
            out.extend(self._parse_result(res, frame))
        return out

    def _run_frame(self, frame: Frame) -> list[OcrResult]:
        """Single-frame fallback (used when a batch call fails or misaligns)."""
        engine = self._ensure_engine()
        try:
            raw = engine.predict([frame.path]) if hasattr(engine, "predict") \
                else engine.ocr(frame.path)
        except Exception as exc:  # noqa: BLE001
            try:
                raw = engine.ocr(frame.path)  # legacy fallback
            except Exception as exc2:  # noqa: BLE001
                log.warning("ocr.frame_failed", frame_id=frame.frame_id,
                            error=f"{exc} / {exc2}")
                return []
        return self._parse(raw, frame)

    def _run_chunk(self, frames: list[Frame]) -> list[OcrResult]:
        """Batched predict() over a chunk of frames; aligns results to frames."""
        engine = self._ensure_engine()
        if hasattr(engine, "predict"):
            try:
                raw = engine.predict([f.path for f in frames])
            except Exception as exc:  # noqa: BLE001
                log.warning("ocr.batch_failed", error=str(exc)[:120], frames=len(frames))
                raw = None
            # predict(list) returns one result per input, in order.
            if raw is not None and len(raw) == len(frames):
                out: list[OcrResult] = []
                for frame, res in zip(frames, raw):
                    out.extend(self._parse_result(res, frame))
                return out
        # legacy engine, or batch failed / misaligned -> per-frame
        out = []
        for frame in frames:
            out.extend(self._run_frame(frame))
        return out

    async def run(self, frames: list[Frame]) -> list[OcrResult]:
        if not frames:
            return []
        loop = asyncio.get_running_loop()
        results: list[OcrResult] = []
        # One predict() call per chunk of `batch_size` frames. Serialised on a
        # single-worker executor (engine is not thread-safe) but awaited so the
        # loop keeps speech + visual moving concurrently.
        for i in range(0, len(frames), self._batch_size):
            chunk = frames[i : i + self._batch_size]
            sub = await loop.run_in_executor(self._executor, partial(self._run_chunk, chunk))
            results.extend(sub)
        log.info("ocr.paddle.done", frames=len(frames), detections=len(results),
                 device=self._device, batch_size=self._batch_size)
        return results

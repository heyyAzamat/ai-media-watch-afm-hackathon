"""Real visual provider backed by a Qwen2.5-VL endpoint (Step 6).

By default this talks to an OpenAI-compatible multimodal endpoint (e.g. a vLLM
server hosting Qwen2.5-VL, or OpenRouter). Each keyframe is analysed with the
shared VISUAL_PROMPT; the JSON response is parsed into a VisualDetection.
Keyframes are processed concurrently with bounded fan-out.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx

from ...config import get_settings
from ...domain.models import Frame, VisualDetection
from ...logging_config import get_logger
from ..reasoning.json_repair import parse_json_lenient
from .base import VISUAL_LABELS, VISUAL_PROMPT

log = get_logger(__name__)


class QwenVLProvider:
    name = "qwen2.5-vl"

    def __init__(self, model: str | None = None, max_concurrency: int | None = None) -> None:
        self._settings = get_settings()
        self._model = model or self._settings.visual_model
        self.name = self._model
        self._sem = asyncio.Semaphore(max_concurrency or self._settings.visual_max_concurrency)

    @staticmethod
    def _encode(path: str) -> str | None:
        p = Path(path)
        if not p.exists():
            return None
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"

    async def _analyze_one(self, client: httpx.AsyncClient, frame: Frame) -> VisualDetection:
        image_url = self._encode(frame.path)
        if image_url is None:
            return VisualDetection(timestamp=frame.timestamp, frame_id=frame.frame_id)
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISUAL_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._settings.openrouter_api_key}"}
        async with self._sem:
            try:
                resp = await client.post(
                    f"{self._settings.openrouter_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
                data = parse_json_lenient(content) or {}
            except Exception as exc:  # noqa: BLE001
                log.warning("visual.frame_failed", frame_id=frame.frame_id, error=str(exc))
                return VisualDetection(timestamp=frame.timestamp, frame_id=frame.frame_id)

        scores = {k: float(data.get(k, 0.0) or 0.0) for k in VISUAL_LABELS}
        evidence = [str(e) for e in (data.get("evidence") or [])]
        return VisualDetection(
            timestamp=frame.timestamp, frame_id=frame.frame_id, scores=scores, evidence=evidence
        )

    async def analyze(self, keyframes: list[Frame]) -> list[VisualDetection]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = [self._analyze_one(client, f) for f in keyframes]
            detections = await asyncio.gather(*tasks)
        log.info("visual.qwen.done", detections=len(detections))
        return list(detections)

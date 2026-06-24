"""Step 1 — Video ingestion: probe technical metadata."""

from __future__ import annotations

import os
from pathlib import Path

from ..domain.models import VideoMetadata
from ..logging_config import get_logger

log = get_logger(__name__)


class OpenCVIngestionService:
    """Probe a video file using OpenCV, falling back to ffprobe-less defaults."""

    def probe(
        self,
        *,
        video_id: str,
        path: str,
        filename: str,
        source_platform: str = "upload",
        source_url: str | None = None,
    ) -> VideoMetadata:
        size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
        container = Path(filename).suffix.lstrip(".").lower()
        fps, width, height, duration = self._probe_streams(path)

        meta = VideoMetadata(
            video_id=video_id,
            filename=filename,
            source_platform=source_platform,
            source_url=source_url,
            duration_seconds=round(duration, 3),
            fps=round(fps, 3),
            width=width,
            height=height,
            size_bytes=size_bytes,
            container=container,
        )
        log.info(
            "ingestion.probed",
            video_id=video_id,
            duration=meta.duration_seconds,
            fps=meta.fps,
            resolution=meta.resolution,
        )
        return meta

    @staticmethod
    def _probe_streams(path: str) -> tuple[float, int, int, float]:
        try:
            import cv2  # imported lazily so the API image needn't bundle GPU libs

            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return 0.0, 0, 0, 0.0
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
            frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            duration = frame_count / fps if fps > 0 else 0.0
            return fps, width, height, duration
        except Exception as exc:  # noqa: BLE001
            log.warning("ingestion.probe_failed", error=str(exc), path=path)
            return 0.0, 0, 0, 0.0

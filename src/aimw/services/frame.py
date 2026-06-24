"""Step 3 — Frame extraction (1 fps + scene keyframes) and audio demux."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..config import get_settings
from ..domain.models import Frame, Scene
from ..logging_config import get_logger
from ..utils.ids import new_frame_id

log = get_logger(__name__)


class OpenCVFrameExtractor:
    """Sample frames at a fixed rate and tag scene keyframes."""

    def __init__(self, frames_dir: Path | None = None) -> None:
        self._frames_dir = frames_dir or get_settings().frames_dir

    def extract(
        self, video_path: str, video_id: str, scenes: list[Scene], fps: float
    ) -> list[Frame]:
        out_dir = self._frames_dir / video_id
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            import cv2

            return self._extract_cv2(cv2, video_path, video_id, scenes, fps, out_dir)
        except Exception as exc:  # noqa: BLE001
            log.warning("frame.extract_failed", error=str(exc), video_id=video_id)
            # Even without decode we still emit logical keyframe placeholders so
            # downstream services have timestamps to anchor against.
            return self._placeholder_keyframes(video_id, scenes, out_dir)

    def _extract_cv2(self, cv2, video_path, video_id, scenes, fps, out_dir) -> list[Frame]:  # noqa: ANN001
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return self._placeholder_keyframes(video_id, scenes, out_dir)

        native_fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / native_fps if native_fps else 0.0

        sample_interval = 1.0 / max(fps, 0.1)
        keyframe_ts = {round(s.keyframe_ts, 3): s.scene_id for s in scenes}

        # Build the full set of timestamps we want a frame for.
        wanted: dict[float, int | None] = {}
        t = 0.0
        while t <= duration:
            wanted.setdefault(round(t, 3), None)
            t += sample_interval
        for kf_ts, scene_id in keyframe_ts.items():
            wanted[kf_ts] = scene_id

        frames: list[Frame] = []
        for ts in sorted(wanted):
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
            ok, image = cap.read()
            if not ok or image is None:
                continue
            frame_id = new_frame_id(video_id, ts)
            path = out_dir / f"{frame_id}.jpg"
            cv2.imwrite(str(path), image)
            frames.append(
                Frame(
                    frame_id=frame_id,
                    timestamp=ts,
                    path=str(path),
                    is_keyframe=wanted[ts] is not None,
                    scene_id=wanted[ts],
                )
            )
        cap.release()
        log.info("frame.extracted", video_id=video_id, count=len(frames))
        return frames

    def _placeholder_keyframes(self, video_id, scenes, out_dir) -> list[Frame]:  # noqa: ANN001
        frames = [
            Frame(
                frame_id=new_frame_id(video_id, s.keyframe_ts),
                timestamp=s.keyframe_ts,
                path=str(out_dir / f"{new_frame_id(video_id, s.keyframe_ts)}.jpg"),
                is_keyframe=True,
                scene_id=s.scene_id,
            )
            for s in scenes
        ]
        log.info("frame.placeholders", video_id=video_id, count=len(frames))
        return frames


class FFmpegAudioExtractor:
    """Demux audio to a 16 kHz mono wav for the speech provider."""

    def __init__(self, frames_dir: Path | None = None) -> None:
        self._dir = frames_dir or get_settings().frames_dir

    def extract_audio(self, video_path: str, video_id: str) -> str | None:
        if shutil.which("ffmpeg") is None:
            log.warning("audio.ffmpeg_missing", video_id=video_id)
            return None
        out_dir = self._dir / video_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "audio.wav"
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ac", "1", "-ar", "16000", "-vn", str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            log.info("audio.extracted", video_id=video_id, path=str(out_path))
            return str(out_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("audio.extract_failed", error=str(exc), video_id=video_id)
            return None

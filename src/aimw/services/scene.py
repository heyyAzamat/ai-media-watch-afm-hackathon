"""Step 2 — Scene detection using PySceneDetect (content-aware)."""

from __future__ import annotations

from ..domain.models import Scene
from ..logging_config import get_logger

log = get_logger(__name__)


class PySceneDetectDetector:
    """Detect scene boundaries; degrade gracefully to fixed windows."""

    def __init__(self, threshold: float = 27.0, fallback_window: float = 5.0) -> None:
        self._threshold = threshold
        self._fallback_window = fallback_window

    def detect(self, video_path: str, duration: float) -> list[Scene]:
        scenes = self._detect_with_scenedetect(video_path)
        if scenes:
            log.info("scene.detected", count=len(scenes), method="pyscenedetect")
            return scenes
        scenes = self._fixed_windows(duration)
        log.info("scene.detected", count=len(scenes), method="fixed_window")
        return scenes

    def _detect_with_scenedetect(self, video_path: str) -> list[Scene]:
        try:
            from scenedetect import ContentDetector, SceneManager, open_video

            video = open_video(video_path)
            manager = SceneManager()
            manager.add_detector(ContentDetector(threshold=self._threshold))
            manager.detect_scenes(video)
            scene_list = manager.get_scene_list()
            return [
                Scene(
                    scene_id=i + 1,
                    start=round(start.get_seconds(), 3),
                    end=round(end.get_seconds(), 3),
                )
                for i, (start, end) in enumerate(scene_list)
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("scene.detect_failed", error=str(exc))
            return []

    def _fixed_windows(self, duration: float) -> list[Scene]:
        if duration <= 0:
            return [Scene(scene_id=1, start=0.0, end=0.0)]
        scenes: list[Scene] = []
        start = 0.0
        idx = 1
        while start < duration:
            end = min(start + self._fallback_window, duration)
            scenes.append(Scene(scene_id=idx, start=round(start, 3), end=round(end, 3)))
            start = end
            idx += 1
        return scenes

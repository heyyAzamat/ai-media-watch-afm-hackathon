"""Shared fixtures. All tests run offline with mock providers + fallback judge."""

from __future__ import annotations

import os

import pytest

from aimw.domain.models import Frame, PreparedVideo, Scene, VideoMetadata
from aimw.utils.ids import new_frame_id, new_video_id


@pytest.fixture(autouse=True, scope="session")
def _hermetic_settings() -> None:
    """Force mock providers + placeholder key so the suite never touches the
    network, regardless of any local .env (env vars override .env in
    pydantic-settings)."""
    os.environ.update(
        {
            "AIMW_OCR_PROVIDER": "mock",
            "AIMW_SPEECH_PROVIDER": "mock",
            "AIMW_VISUAL_PROVIDER": "mock",
            "AIMW_OPENROUTER_API_KEY": "sk-or-changeme",
        }
    )
    from aimw.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def prepared_video() -> PreparedVideo:
    video_id = new_video_id()
    metadata = VideoMetadata(
        video_id=video_id,
        filename="sample.mp4",
        source_platform="upload",
        duration_seconds=25.0,
        fps=30.0,
        width=1080,
        height=1920,
        size_bytes=1_000_000,
        container="mp4",
    )
    scenes = [
        Scene(scene_id=1, start=0.0, end=8.0),
        Scene(scene_id=2, start=8.0, end=16.0),
        Scene(scene_id=3, start=16.0, end=25.0),
    ]
    frames: list[Frame] = []
    t = 0.0
    keyframe_ts = {s.keyframe_ts for s in scenes}
    while t <= 25.0:
        is_kf = round(t, 3) in {round(k, 3) for k in keyframe_ts}
        frames.append(
            Frame(
                frame_id=new_frame_id(video_id, t),
                timestamp=round(t, 3),
                path=f"/tmp/{video_id}_{int(t)}.jpg",
                is_keyframe=is_kf,
            )
        )
        t += 1.0
    # ensure keyframes present
    for s in scenes:
        frames.append(
            Frame(
                frame_id=new_frame_id(video_id, s.keyframe_ts),
                timestamp=s.keyframe_ts,
                path=f"/tmp/{video_id}_kf{s.scene_id}.jpg",
                is_keyframe=True,
                scene_id=s.scene_id,
            )
        )
    return PreparedVideo(metadata=metadata, scenes=scenes, frames=frames, audio_path=None)

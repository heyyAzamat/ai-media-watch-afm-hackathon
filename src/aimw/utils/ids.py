"""Opaque, sortable identifier helpers."""

from __future__ import annotations

import uuid


def new_video_id() -> str:
    return f"vid_{uuid.uuid4().hex[:20]}"


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:20]}"


def new_frame_id(video_id: str, timestamp: float) -> str:
    return f"frm_{video_id.removeprefix('vid_')}_{int(round(timestamp * 1000)):08d}"


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:16]}"


def new_request_id() -> str:
    return uuid.uuid4().hex

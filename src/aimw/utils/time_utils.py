"""Timestamp formatting helpers used by the timeline / evidence player."""

from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    """Render seconds as ``MM:SS`` (or ``HH:MM:SS`` past one hour)."""
    seconds = max(0.0, seconds)
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def overlaps(a_start: float, a_end: float, b_start: float, b_end: float, slack: float = 0.0) -> bool:
    """Return True if two intervals overlap, with optional ``slack`` padding."""
    return a_start - slack <= b_end and b_start - slack <= a_end

"""Platform-aware media downloader.

Downloads a video from a social-media page URL (TikTok / Instagram /
YouTube Shorts) via yt-dlp and returns the local path. Framework-agnostic:
no FastAPI / Celery imports. yt-dlp is imported lazily so tests can patch it.
"""
from __future__ import annotations

from pathlib import Path

from ..logging_config import get_logger

log = get_logger(__name__)


class DownloadError(RuntimeError):
    """Raised when a media URL cannot be downloaded."""


def download_media(url: str, video_id: str, dest_dir: Path) -> Path:
    """Download ``url`` into ``dest_dir`` as ``{video_id}.mp4`` and return it."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest_dir / f"{video_id}.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        from yt_dlp import YoutubeDL  # lazy import; patchable in tests

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
    except Exception as exc:  # noqa: BLE001
        raise DownloadError(f"could not download {url!r}: {exc}") from exc

    if not path.exists():
        merged = dest_dir / f"{video_id}.mp4"
        if merged.exists():
            path = merged
        else:
            raise DownloadError(f"download reported success but no file at {path}")
    log.info("download.done", url=url, path=str(path))
    return path

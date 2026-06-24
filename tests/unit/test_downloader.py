"""Offline tests for the yt-dlp-backed downloader. yt_dlp is patched into
sys.modules so the suite never touches the network and yt-dlp need not be
installed to run these tests."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from aimw.services.downloader import DownloadError, download_media


class _FakeYDL:
    def __init__(self, opts):
        self.opts = opts
        self._tmpl = opts["outtmpl"]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download):
        out = Path(self._tmpl.replace("%(ext)s", "mp4"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake-bytes")
        return {"ext": "mp4"}

    def prepare_filename(self, info):
        return self._tmpl.replace("%(ext)s", "mp4")


def _install_fake_ytdlp(monkeypatch, ydl_cls):
    module = types.ModuleType("yt_dlp")
    module.YoutubeDL = ydl_cls
    monkeypatch.setitem(sys.modules, "yt_dlp", module)


def test_download_media_writes_named_file(tmp_path, monkeypatch):
    _install_fake_ytdlp(monkeypatch, _FakeYDL)
    out = download_media("https://www.tiktok.com/@u/video/123", "vid_test", tmp_path)
    assert out.exists()
    assert out.name == "vid_test.mp4"


def test_download_media_raises_downloaderror_on_failure(tmp_path, monkeypatch):
    class _BoomYDL(_FakeYDL):
        def extract_info(self, url, download):
            raise RuntimeError("private or removed video")

    _install_fake_ytdlp(monkeypatch, _BoomYDL)
    with pytest.raises(DownloadError):
        download_media("https://www.tiktok.com/@u/video/bad", "vid_x", tmp_path)

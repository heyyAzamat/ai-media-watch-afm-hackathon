"""Offline test for the synchronous /check endpoint. Patches the downloader
and the scam model so no real video, network, or model is needed."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import aimw.api.v1.endpoints.check as check_mod
from aimw.services.scam_model import ScamVerdict


def test_check_returns_verdict(monkeypatch):
    def fake_download(url, video_id, dest_dir):
        p = Path(dest_dir) / f"{video_id}.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(check_mod, "download_media", fake_download)

    class _FakeModel:
        name = "fake"

        def analyze(self, video_path):
            return ScamVerdict(
                risk_score=87,
                category="illegal_gambling",
                confidence=0.9,
                explanation="said 'guaranteed win'",
            )

    monkeypatch.setattr(check_mod, "_model", _FakeModel())

    from aimw.main import create_app

    client = TestClient(create_app())
    resp = client.post(
        "/api/v1/check", data={"source_url": "https://www.tiktok.com/@u/video/1"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_score"] == 87
    assert body["category"] == "illegal_gambling"


def test_check_rejects_blank_source_url():
    """A present-but-blank source_url hits our own .strip() guard -> 400.
    (A fully missing field is rejected by FastAPI with 422 before our code
    runs; the TestClient drops empty-valued form fields, so we send whitespace
    to reach the handler.)"""
    from aimw.main import create_app

    client = TestClient(create_app())
    resp = client.post("/api/v1/check", data={"source_url": "   "})
    assert resp.status_code == 400

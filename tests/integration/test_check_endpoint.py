"""Offline test for the synchronous /check endpoint. Patches the downloader
and the orchestrator so no real video, network, or providers are needed.

The endpoint only reads ``artifacts.report``, so the fake orchestrator returns a
lightweight stand-in with a ``.report`` attribute instead of a full
AnalysisArtifacts (which requires every pipeline field)."""
from __future__ import annotations

import types
from pathlib import Path

from fastapi.testclient import TestClient

import aimw.api.v1.endpoints.check as check_mod
from aimw.domain.enums import RiskCategory
from aimw.domain.models import AnalysisReport


def _fake_report() -> AnalysisReport:
    return AnalysisReport(
        video_id="vid_test",
        risk_score=87,
        category=RiskCategory.ILLEGAL_GAMBLING,
        confidence=0.9,
        summary="casino promo",
    )


def test_check_returns_report(monkeypatch):
    def fake_download(url, video_id, dest_dir):
        p = Path(dest_dir) / f"{video_id}.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(check_mod, "download_media", fake_download)

    class _FakeOrch:
        def prepare(self, **kw):
            return {"video_id": kw["video_id"]}

        async def run(self, prepared, progress=None):
            return types.SimpleNamespace(report=_fake_report())

    monkeypatch.setattr(check_mod, "_orchestrator", _FakeOrch())

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

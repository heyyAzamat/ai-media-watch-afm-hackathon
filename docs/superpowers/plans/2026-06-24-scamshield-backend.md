# ScamShield Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing AI Media Watch backend accept a real TikTok / Instagram / YouTube Shorts link, download the real video, and return an explainable scam verdict in a single synchronous request — running fully on local/self-hosted AI (no external services, no Docker/Redis/Postgres).

**Architecture:** Reuse the existing framework-agnostic analysis engine (`AnalysisOrchestrator`, which already runs standalone — see `scripts/run_local.py`). Add (1) a `yt-dlp` downloader service and (2) a new synchronous `POST /api/v1/check` endpoint that downloads a video and runs `prepare()` + `run()` in-process, returning the report directly. The existing async `/analyze` + Celery path stays untouched (the scalable/regulator path) but is not used for the demo. Configure the runtime for local Whisper + the deterministic (offline) judge.

**Tech Stack:** Python 3.12, FastAPI, faster-whisper (local), yt-dlp, pytest, ffmpeg (already installed), uvicorn.

## Global Constraints

- Python 3.12 (faster-whisper has cp312 wheels).
- Tests run **offline** — never hit the real network (mock/patch `yt_dlp` and the orchestrator).
- Demo config uses **no `AIMW_OPENROUTER_API_KEY`** so the deterministic judge auto-activates (criterion #2 — independent AI). Verified: `build_reasoning_engine()` returns `FallbackReasoningEngine` when the key is `""`/`"sk-or-changeme"`.
- The existing async API contract (`docs/API_CONTRACTS.md`) and Celery path stay **unchanged**. We only ADD a new endpoint.
- Framework-agnostic core rule: files under `services/` must not import FastAPI/Celery.
- No Docker, no sudo, no Redis, no Postgres required by anything in this plan.

---

### Task 1: Environment baseline (project runs, tests green)

Nothing is installed yet. Get the project runnable and prove the existing engine works before touching anything. (ffmpeg is already present — no system install needed.)

**Files:**
- Create: `.venv/` (local virtualenv, gitignored)

**Interfaces:**
- Produces: a working `python -m pytest` and an importable `aimw` package for all later tasks.

- [ ] **Step 1: Create venv and install the package + test deps**

Run:
```bash
cd /home/mansur_ai/projects/afm
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
pip install pytest pytest-asyncio
```
Expected: installs without error (pulls FastAPI, opencv-python-headless, scenedetect, etc.); `pip show aimw` shows the package.

- [ ] **Step 2: Run the existing test suite (baseline)**

Run:
```bash
. .venv/bin/activate
python -m pytest -q
```
Expected: **all** existing tests PASS (count is whatever the repo currently has — do not assume a number). If any fail, stop and report — do not proceed until baseline is green.

- [ ] **Step 3: Ensure .venv is gitignored, commit if needed**

```bash
grep -q '^\.venv' .gitignore || echo '.venv/' >> .gitignore
git add .gitignore
git commit -m "chore: ignore local .venv" || echo "nothing to commit"
```

---

### Task 2: Add a platform-aware downloader service (TDD)

The first new piece of backend code. A small, framework-agnostic function that downloads a video from a platform page URL via yt-dlp.

**Files:**
- Create: `src/aimw/services/downloader.py`
- Test: `tests/unit/test_downloader.py`
- Modify: `requirements.txt` (add `yt-dlp`), `pyproject.toml` (add `yt-dlp` to dependencies)

**Interfaces:**
- Produces:
  - `class DownloadError(RuntimeError)`
  - `def download_media(url: str, video_id: str, dest_dir: Path) -> Path` — downloads into `dest_dir/{video_id}.mp4`, returns the path, raises `DownloadError` on any failure.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_downloader.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
. .venv/bin/activate
python -m pytest tests/unit/test_downloader.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'aimw.services.downloader'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/aimw/services/downloader.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
. .venv/bin/activate
python -m pytest tests/unit/test_downloader.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Add yt-dlp as a real dependency**

Edit `requirements.txt` — add after `httpx>=0.27`:
```
yt-dlp>=2024.8
```
Edit `pyproject.toml` — add `"yt-dlp>=2024.8",` to the `dependencies` list (match existing formatting). Then:
```bash
. .venv/bin/activate
pip install "yt-dlp>=2024.8"
```

- [ ] **Step 6: Run the full suite (nothing regressed)**

Run:
```bash
. .venv/bin/activate
python -m pytest -q
```
Expected: all tests PASS (existing + 2 new).

- [ ] **Step 7: Commit**

```bash
git add src/aimw/services/downloader.py tests/unit/test_downloader.py requirements.txt pyproject.toml
git commit -m "feat: add yt-dlp platform media downloader service"
```

---

### Task 3: Add the synchronous `POST /api/v1/check` endpoint (TDD)

A new endpoint that downloads a video by URL and runs the analysis engine in-process (no Celery/DB), returning the explainable report directly. This is the consumer "paste a link → verdict" flow.

**Files:**
- Create: `src/aimw/api/v1/endpoints/check.py`
- Test: `tests/integration/test_check_endpoint.py`
- Modify: `src/aimw/api/v1/router.py` (register the new router)

**Interfaces:**
- Consumes: `download_media`, `DownloadError` (Task 2); `AnalysisOrchestrator` (`prepare()` is blocking; `run()` is async and returns an object whose `.report` is a Pydantic model).
- Produces: `POST /api/v1/check` form field `source_url` (required) → `200` with the report JSON, or `400` on bad/missing URL or download failure.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_check_endpoint.py`:
```python
"""Offline test for the synchronous /check endpoint. Patches the downloader
and the orchestrator so no real video, network, or providers are needed."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import aimw.api.v1.endpoints.check as check_mod
from aimw.domain.enums import RiskCategory
from aimw.domain.models import AnalysisArtifacts, PreparedVideo, VideoMetadata


def _fake_report():
    # Minimal stand-in matching the report shape the endpoint returns.
    from aimw.domain.models import AnalysisReport

    return AnalysisReport(
        video_id="vid_test",
        risk_score=87,
        category=RiskCategory.ILLEGAL_GAMBLING,
        confidence=0.9,
        summary="casino promo",
        explanation="said 'guaranteed win'",
        metadata=VideoMetadata(
            video_id="vid_test", filename="vid_test.mp4", duration_seconds=10.0,
            fps=30.0, width=0, height=0, size_bytes=0,
        ),
        fallback_used=True,
    )


def test_check_returns_report(monkeypatch, tmp_path):
    def fake_download(url, video_id, dest_dir):
        p = Path(dest_dir) / f"{video_id}.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(check_mod, "download_media", fake_download)

    class _FakeOrch:
        def prepare(self, **kw):
            return PreparedVideo(
                metadata=VideoMetadata(
                    video_id=kw["video_id"], filename=kw["filename"],
                    duration_seconds=10.0, fps=30.0, width=0, height=0, size_bytes=0,
                ),
                scenes=[], frames=[], audio_path=None,
            )

        async def run(self, prepared, progress=None):
            return AnalysisArtifacts(report=_fake_report())

    monkeypatch.setattr(check_mod, "_orchestrator", _FakeOrch())

    from aimw.main import create_app

    client = TestClient(create_app())
    resp = client.post("/api/v1/check", data={"source_url": "https://www.tiktok.com/@u/video/1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_score"] == 87
    assert body["category"] == "illegal_gambling"


def test_check_requires_source_url():
    from aimw.main import create_app

    client = TestClient(create_app())
    resp = client.post("/api/v1/check", data={})
    assert resp.status_code == 400
```

NOTE for the implementer: `AnalysisArtifacts` requires only the fields the endpoint reads (`.report`). If its constructor demands more fields, construct it with the minimum the model allows (check `domain/models.py`) — the test asserts behavior, not every field. Adjust the fake objects to satisfy the real model signatures you find, keeping the asserted values (`risk_score=87`, `category=illegal_gambling`).

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
. .venv/bin/activate
python -m pytest tests/integration/test_check_endpoint.py -v
```
Expected: FAIL (module `aimw.api.v1.endpoints.check` does not exist).

- [ ] **Step 3: Write the endpoint**

Create `src/aimw/api/v1/endpoints/check.py`:
```python
"""POST /check — synchronous one-shot analysis for the consumer app.

Downloads a video from a platform URL, runs the analysis engine in-process
(no Celery/DB), and returns the explainable report directly. Built for the
'paste a link, get a verdict' flow. The async /analyze path is unaffected.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Form, status

from ....config import get_settings
from ....logging_config import get_logger
from ....orchestration.orchestrator import AnalysisOrchestrator
from ....services.downloader import DownloadError, download_media
from ....utils.ids import new_video_id
from ...errors import APIError

router = APIRouter()
log = get_logger(__name__)

# Build once at import (wires the DI container / loads provider config).
_orchestrator = AnalysisOrchestrator()


@router.post("/check", summary="Synchronously analyze a video URL and return a verdict")
async def check(source_url: str = Form(...)):
    if not source_url.strip():
        raise APIError("source_url is required")

    settings = get_settings()
    settings.ensure_dirs()
    video_id = new_video_id()

    try:
        path = await asyncio.to_thread(
            download_media, source_url, video_id, settings.uploads_dir
        )
    except DownloadError as exc:
        raise APIError(
            "failed to download video from URL",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    prepared = await asyncio.to_thread(
        _orchestrator.prepare,
        video_id=video_id,
        path=str(path),
        filename=path.name,
        source_url=source_url,
    )
    artifacts = await _orchestrator.run(prepared)
    log.info("check.done", video_id=video_id, risk_score=artifacts.report.risk_score)
    return artifacts.report
```

(`source_url: str = Form(...)` makes it required — a missing field yields `422`; an empty string yields our `400`. The test's empty-form case asserts `400`; if FastAPI returns `422` for a fully missing field, adjust the test to send `{"source_url": ""}` to hit the `400` branch.)

- [ ] **Step 4: Register the router**

Modify `src/aimw/api/v1/router.py`:
- Add `check` to the import line: `from .endpoints import analyze, check, evidence, report, risk, status, timeline`
- Add after the analyze include: `api_router.include_router(check.router, tags=["analysis"])`

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
. .venv/bin/activate
python -m pytest tests/integration/test_check_endpoint.py -v
```
Expected: both tests PASS. If the empty-form case returned `422`, apply the Step 3 note and re-run.

- [ ] **Step 6: Full suite + app import check**

Run:
```bash
. .venv/bin/activate
python -c "from aimw.main import create_app; create_app(); print('app ok')"
python -m pytest -q
```
Expected: `app ok`; all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aimw/api/v1/endpoints/check.py tests/integration/test_check_endpoint.py src/aimw/api/v1/router.py
git commit -m "feat: add synchronous /check endpoint for consumer flow"
```

---

### Task 4: Install local Whisper + write the independent demo config

Switch the runtime from mock to local real AI for audio, and lock in the offline judge.

**Files:**
- Create: `.env` (gitignored — confirm it's in `.gitignore`)

**Interfaces:**
- Produces: a runtime where `speech_provider` is `real` and `build_reasoning_engine().model == "fallback-deterministic"`.

- [ ] **Step 1: Install faster-whisper (local speech) — must-have**

Run:
```bash
. .venv/bin/activate
pip install faster-whisper
```
Expected: installs. (CPU int8 is the default in `config.py`.)

- [ ] **Step 2: Try PaddleOCR (local on-screen text) — optional**

Run:
```bash
. .venv/bin/activate
pip install paddleocr paddlepaddle || echo "PADDLE INSTALL FAILED — leave OCR on mock"
```
If it fails/slow, keep `AIMW_OCR_PROVIDER=mock`. Audio (Whisper) is the core signal.

- [ ] **Step 3: Write the demo `.env` (independent config)**

Confirm `.env` is gitignored (`grep -q '^\.env$' .gitignore || echo '.env' >> .gitignore`), then create `/home/mansur_ai/projects/afm/.env`:
```
AIMW_ENV=development
AIMW_SPEECH_PROVIDER=real
AIMW_OCR_PROVIDER=mock
AIMW_VISUAL_PROVIDER=mock
AIMW_WHISPER_MODEL=base
AIMW_WHISPER_COMPUTE_TYPE=int8
AIMW_FRAMES_PER_SECOND=0.5
```
No `AIMW_OPENROUTER_API_KEY` line → deterministic judge. If PaddleOCR worked in Step 2, set `AIMW_OCR_PROVIDER=real`.

- [ ] **Step 4: Verify config loads and selects the offline judge**

Run:
```bash
. .venv/bin/activate
python -c "
from aimw.config import get_settings; get_settings.cache_clear()
from aimw.services.reasoning.base import build_reasoning_engine
print('speech:', get_settings().speech_provider)
print('judge :', build_reasoning_engine().model)
"
```
Expected: `speech: real` and `judge : fallback-deterministic`.

---

### Task 5: End-to-end smoke test on a real video (no Docker)

Prove the full path works on a real downloaded video over a locally-run API — the way the demo runs. Operational verification (no automated test; it needs a real network + Whisper).

**Files:** none.

**Interfaces:**
- Consumes: everything above.
- Produces: a confirmed `URL → verdict` over HTTP, reachable from a phone.

- [ ] **Step 1: Start the API locally (binds all interfaces so a phone can reach it)**

Run (in its own terminal):
```bash
cd /home/mansur_ai/projects/afm
. .venv/bin/activate
uvicorn aimw.main:app --host 0.0.0.0 --port 8000
```
In another terminal, confirm: `curl -s localhost:8000/health` → `{"status":"ok",...}` and open `http://localhost:8000/docs`.

- [ ] **Step 2: Analyze a real video by URL (one synchronous request)**

Use a YouTube Shorts URL first (most reliable for yt-dlp). Replace `<URL>`:
```bash
curl -s -X POST localhost:8000/api/v1/check \
  -F "source_url=<URL>" | python3 -m json.tool
```
Expected: a report JSON with `risk_score`, `category`, `summary`, `explanation`, a `timeline`, and `fallback_used: true` (proves the offline judge ran). First call is slow (Whisper downloads the `base` model once); later calls are faster.

- [ ] **Step 3: Confirm a phone can reach it**

Find the laptop's LAN IP (`hostname -I | awk '{print $1}'`). From a phone on the **same Wi-Fi**, open `http://<that-ip>:8000/docs`. Give the frontend dev `http://<that-ip>:8000` as the API base. CORS is already wide-open in `main.py`. (Optional public URL: install `pip install pyngrok` and run a tunnel — needs a free ngrok token.)

- [ ] **Step 4: Record a backup demo capture**

Run the full flow once and screen-record it. If venue Wi-Fi or yt-dlp fails on stage, fall back to the recording (and pre-download the demo clips so a local-file path is available).

---

## Self-Review

**Spec coverage:**
- §6.1 yt-dlp downloader → Task 2 ✅
- §6.1 the analyze flow → Task 3 (sync `/check` reusing the engine; simpler than async given no Redis/Postgres/Docker on this machine) ✅
- §6.1 run config (real speech, mock visual, offline judge, base Whisper) → Task 4 ✅
- §6.1 reachability (CORS already done; LAN IP / optional tunnel) → Task 5 Step 3 ✅
- §7 independence (no OpenRouter key → deterministic judge; verified in code) → Task 4 ✅
- §8 the report shape returned by `/check` matches the existing report contract (we return the same `AnalysisReport`) ✅
- §9 download error → clear 400 → Task 3 Step 3 (`DownloadError` → `APIError 400`) ✅
- §10 testing (existing tests still pass; new offline downloader + endpoint tests) → Tasks 1,2,3 ✅
- §13 risks (yt-dlp blocked → backup recording + pre-downloaded clips) → Task 5 Step 4 ✅
- Frontend (§6.2) / ML (§6.3) are teammates' tracks — the interface is `/check`'s request/response.

**Deviation from spec:** spec §5/§8 described the async submit→poll→report flow. This machine has no Docker/Redis/Postgres and the consumer flow is naturally one-shot, so we expose a **synchronous** `/check` instead. The async path remains in the repo for the scalable/regulator story. (Approved with the user before execution.)

**Placeholder scan:** `<URL>` (Task 5) is a runtime input the operator supplies, not an unfilled plan value. No "TBD/TODO".

**Type consistency:** `download_media(url, video_id, dest_dir) -> Path` and `DownloadError` are named identically across Task 2 (def + test) and Task 3 (consumer). The `/check` endpoint and its test agree on `source_url` (form), `200` + report JSON, and `400` on failure.

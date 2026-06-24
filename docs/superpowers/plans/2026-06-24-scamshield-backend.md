# ScamShield Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing AI Media Watch backend accept a real TikTok / Instagram / YouTube Shorts link, download the real video, and return an explainable scam verdict — running fully on local/self-hosted AI (no external services).

**Architecture:** Reuse the existing FastAPI + Celery analysis engine unchanged. Add one new framework-agnostic `downloader` service (yt-dlp), wire it into the `/analyze` endpoint's URL path, and configure the runtime to use local Whisper + the deterministic (offline) judge. Expose the laptop to a phone via a tunnel.

**Tech Stack:** Python 3.12, FastAPI, Celery, faster-whisper, yt-dlp, pytest, ffmpeg, ngrok.

## Global Constraints

- Python 3.12 (project targets 3.12+; PaddleOCR/faster-whisper have cp312 wheels).
- No `any`-style shortcuts that break the existing typed domain models.
- Tests run **offline** — never hit the real network in a test (mock/patch `yt_dlp`).
- The demo config must use **no `AIMW_OPENROUTER_API_KEY`** so the deterministic judge auto-activates (criterion #2 — independent AI).
- API contract in `docs/API_CONTRACTS.md` stays **unchanged**; the frontend depends on it.
- Framework-agnostic core rule: files under `services/` must not import FastAPI/Celery.

---

### Task 1: Environment baseline (project runs, tests green)

Nothing is installed yet. This task gets the project runnable and proves the existing engine works before we touch anything.

**Files:**
- Create: `.venv/` (local virtualenv, gitignored)
- Modify: none

**Interfaces:**
- Produces: a working `python -m pytest` and an importable `aimw` package for all later tasks.

- [ ] **Step 1: Install system ffmpeg (needed for audio extraction + yt-dlp remux)**

Run:
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
ffmpeg -version | head -1
```
Expected: prints an ffmpeg version line.

- [ ] **Step 2: Create venv and install the package + test deps**

Run:
```bash
cd /home/mansur_ai/projects/afm
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
pip install pytest pytest-asyncio
```
Expected: installs without error; `pip show aimw` shows the package.

- [ ] **Step 3: Run the existing test suite (baseline)**

Run:
```bash
. .venv/bin/activate
python -m pytest -q
```
Expected: all existing tests PASS (the README claims 19). If any fail, stop and report — do not proceed until baseline is green.

- [ ] **Step 4: Commit (only if a .gitignore change is needed)**

```bash
grep -q '^\.venv' .gitignore || echo '.venv/' >> .gitignore
git add .gitignore
git commit -m "chore: ignore local .venv" || echo "nothing to commit"
```

---

### Task 2: Add a platform-aware downloader service (TDD)

The one genuinely new piece of backend code. A small, framework-agnostic function that downloads a video from a platform page URL via yt-dlp.

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

Edit `requirements.txt` — add this line after `httpx>=0.27`:
```
yt-dlp>=2024.8
```
Edit `pyproject.toml` — add `"yt-dlp>=2024.8",` to the `dependencies` list (match the existing formatting). Then install it:
```bash
. .venv/bin/activate
pip install "yt-dlp>=2024.8"
```
Expected: yt-dlp installs.

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

### Task 3: Route platform URLs through the downloader in /analyze

Wire the new service into the API. Direct media URLs keep streaming via httpx; platform page URLs go through yt-dlp (run off the event loop with `asyncio.to_thread`, since yt-dlp blocks).

**Files:**
- Modify: `src/aimw/api/v1/endpoints/analyze.py` (the `_download_url` function + imports)

**Interfaces:**
- Consumes: `download_media`, `DownloadError` from Task 2.
- Produces: `/analyze` accepting a TikTok/IG/Shorts `source_url`. Contract unchanged.

- [ ] **Step 1: Add imports**

In `src/aimw/api/v1/endpoints/analyze.py`, add near the top (after `from pathlib import Path`):
```python
import asyncio
```
And with the other relative imports (near `from ....domain.models import VideoMetadata`):
```python
from ....services.downloader import DownloadError, download_media
```

- [ ] **Step 2: Replace `_download_url` with the platform-aware version**

Replace the entire existing `async def _download_url(...)` function body with:
```python
async def _download_url(url: str, video_id: str) -> str:
    """Fetch a video. Direct media URLs (.mp4/.mov/.webm) stream via httpx;
    platform page URLs (TikTok/Instagram/YouTube Shorts) go through yt-dlp."""
    settings = get_settings()
    settings.ensure_dirs()

    if url.split("?")[0].lower().endswith((".mp4", ".mov", ".webm")):
        dest = settings.uploads_dir / f"{video_id}.mp4"
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with dest.open("wb") as fh:
                        async for chunk in resp.aiter_bytes(1024 * 1024):
                            fh.write(chunk)
        except Exception as exc:  # noqa: BLE001
            raise APIError(
                "failed to fetch source_url",
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return str(dest)

    # Platform page URL → yt-dlp (blocking, so run in a thread).
    try:
        path = await asyncio.to_thread(
            download_media, url, video_id, settings.uploads_dir
        )
    except DownloadError as exc:
        raise APIError(
            "failed to download from platform URL",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return str(path)
```

- [ ] **Step 3: Verify the app still imports and tests pass**

Run:
```bash
. .venv/bin/activate
python -c "from aimw.main import create_app; create_app(); print('app ok')"
python -m pytest -q
```
Expected: prints `app ok`; all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/aimw/api/v1/endpoints/analyze.py
git commit -m "feat: route platform URLs through yt-dlp in /analyze"
```

---

### Task 4: Install local AI providers + write the independent demo config

Switch the runtime from mock to local real AI for audio, and lock in the offline judge. Whisper is the must-have; OCR (PaddleOCR) is a nice-to-have if it installs cleanly.

**Files:**
- Create: `.env` (gitignored — confirm it's in `.gitignore`)

**Interfaces:**
- Produces: a runtime where `/health` reports `speech_provider: real` and `reasoning_model: fallback`-style behavior (no OpenRouter key).

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
If it fails or is slow, that's fine — we keep `AIMW_OCR_PROVIDER=mock`. Audio is the core signal.

- [ ] **Step 3: Write the demo `.env` (independent config)**

Confirm `.env` is gitignored, then create `/home/mansur_ai/projects/afm/.env`:
```
AIMW_ENV=development
AIMW_SPEECH_PROVIDER=real
AIMW_OCR_PROVIDER=mock
AIMW_VISUAL_PROVIDER=mock
AIMW_WHISPER_MODEL=base
AIMW_WHISPER_COMPUTE_TYPE=int8
AIMW_FRAMES_PER_SECOND=0.5
```
(No `AIMW_OPENROUTER_API_KEY` line → `build_reasoning_engine()` returns the deterministic `FallbackReasoningEngine`. If you installed PaddleOCR in Step 2 and it works, set `AIMW_OCR_PROVIDER=real`.)

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

- [ ] **Step 5: Commit (config example only — not the real .env)**

```bash
# .env is gitignored; commit nothing secret. Document the demo config instead.
git status --short
echo "demo env documented in plan; .env stays local"
```

---

### Task 5: End-to-end smoke test on a real video + expose to a phone

Prove the whole path works on a real downloaded video, the way the demo runs. This is a manual verification task (it needs Postgres + Redis + a worker, which aren't unit-testable here).

**Files:** none (operational).

**Interfaces:**
- Consumes: everything above.
- Produces: a confirmed end-to-end `link → verdict` and a public URL the phone can reach.

- [ ] **Step 1: Bring up the full stack**

Run (Docker is simplest — it includes Postgres, Redis, the API and a worker):
```bash
cd /home/mansur_ai/projects/afm
cp .env .env.docker 2>/dev/null || true
make up
sleep 8
curl -s localhost:8000/health
```
Expected: `{"status":"ok",...}`. If `make up` can't use the local `.env`, set the same `AIMW_*` vars in `docker-compose.yml`'s api+worker services.

- [ ] **Step 2: Submit a real video by URL and poll**

First test with a YouTube Shorts URL (most reliable for yt-dlp). Replace `<URL>`:
```bash
JOB=$(curl -s -F "source_url=<URL>" -F "source_platform=youtube" \
      localhost:8000/api/v1/analyze | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
echo "job=$JOB"
# poll
for i in $(seq 1 30); do curl -s localhost:8000/api/v1/status/$JOB; echo; sleep 3; done
```
Expected: status walks `queued → ingesting → analyzing → fusing → judging → completed`.

- [ ] **Step 3: Fetch the explainable report**

Run:
```bash
curl -s localhost:8000/api/v1/report/$JOB | python3 -m json.tool
```
Expected: a report with `risk_score`, `category`, `summary`, `explanation`, and a non-empty `timeline` for a scam video. Confirm `fallback_used` is `true` (proves the offline judge ran).

- [ ] **Step 4: Expose to a phone via ngrok**

Run:
```bash
ngrok http 8000
```
Give the frontend dev the `https://….ngrok-free.app` URL. Confirm from a phone browser that `https://<ngrok>/docs` loads and a test `/analyze` works. CORS is already wide-open in `main.py`, so the PWA can call it directly.

- [ ] **Step 5: Record a backup demo capture**

Run the full flow once and screen-record it (phone + this terminal). If venue Wi-Fi or yt-dlp fails on stage, you fall back to the recording + the **upload** path with pre-downloaded clips.

---

## Self-Review

**Spec coverage:**
- §6.1 yt-dlp downloader → Tasks 2-3 ✅
- §6.1 run config (real speech, mock visual, offline judge, base Whisper) → Task 4 ✅
- §6.1 reachability (CORS already done; ngrok) → Task 5 Step 4 ✅
- §7 independence (no OpenRouter key → deterministic judge) → Task 4 Steps 3-4 ✅
- §8 API contract unchanged → Task 3 keeps the contract ✅
- §9 download error → clear 400 → Task 3 Step 2 (`DownloadError` → `APIError 400`) ✅
- §10 testing (existing tests still pass; new downloader unit test, offline) → Tasks 1,2 ✅
- §13 risks (yt-dlp blocked → upload fallback; pre-downloaded clips; backup recording) → Task 5 Step 5 ✅
- Frontend (§6.2) and ML (§6.3) are owned by teammates — out of scope for this backend plan; the interface to them is the unchanged API contract (§8).

**Placeholder scan:** `<URL>` in Task 5 Step 2 is an intentional runtime input (a real video link the user supplies at demo prep), not an unfilled plan placeholder. No "TBD/TODO/implement later" remain.

**Type consistency:** `download_media(url, video_id, dest_dir) -> Path` and `DownloadError` are named identically in Task 2 (definition), the Task 2 test, and Task 3 (consumer). Consistent.

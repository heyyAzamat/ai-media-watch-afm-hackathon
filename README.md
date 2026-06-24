# AI Media Watch

**Explainable, multimodal video risk-analysis platform.**

AI Media Watch ingests social-media videos (TikTok, Instagram Reels, YouTube
Shorts, Telegram, Facebook, or uploaded `MP4/MOV/WEBM`) and automatically
detects potentially harmful, fraudulent or illegal **financial** content —
illegal gambling, casino/betting promotion, pyramid & Ponzi schemes,
guaranteed-income and referral scams, fake investments, hidden advertising, and
other high-risk financial manipulation.

Every decision is **explainable**. There are no black-box outputs: every risk
score traces back to **visual**, **speech** and **OCR** evidence with exact
timestamps.

---

## Why it's different

- **Explainable by construction.** Risk → timeline event → fused evidence →
  source modality (OCR / speech / visual) → matched terms + timestamp.
- **Parallel, not sequential.** OCR, speech-to-text and visual analysis run
  concurrently (`asyncio.gather`); the 72B reasoning model is called **once** per
  video as a final "compliance officer", never per-frame.
- **Service-oriented & swappable.** Every stage is a `Protocol`; real GPU
  providers and deterministic mocks are interchangeable via one DI container.
- **Framework-agnostic core.** The analysis engine imports neither FastAPI nor
  Celery, so it can be embedded in a worker, a CLI, an SDK, or a serverless fn.
- **Robust.** Retries, timeouts, automatic JSON repair, and a deterministic
  fallback verdict mean the pipeline still produces a traceable result when the
  LLM judge is unreachable.

## Architecture at a glance

```
                          VIDEO
                            │
        ┌──────────── ingestion / scene / frame / audio ───────────┐
        │                   (Steps 1–3)                             │
        ▼                                                           ▼
  ┌───────────────────── PARALLEL (asyncio.gather) ─────────────────────┐
  │       OCR WORKER          AUDIO WORKER          VISUAL WORKER        │
  │       PaddleOCR        Whisper Large-v3         Qwen2.5-VL           │
  └─────────┬───────────────────┬─────────────────────┬────────────────┘
            └───────────────────┼─────────────────────┘
                                ▼
                        TEXT-RISK ANALYSIS  (Step 7)
                                ▼
                          FUSION SERVICE     (Step 8, evidence graph)
                                ▼
                       TIMELINE GENERATION   (Step 9, + player markers)
                                ▼
                   Qwen2.5-72B JUDGE  (Step 10, OpenRouter, 1× per video)
                                ▼
                          FINAL REPORT
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full breakdown.

## Tech stack

| Concern        | Choice                                                |
|----------------|-------------------------------------------------------|
| Language       | Python 3.12+                                           |
| API            | FastAPI + Pydantic v2                                  |
| Workers/queue  | Celery + Redis                                         |
| Database       | PostgreSQL (SQLAlchemy 2.0, psycopg3)                  |
| Media          | FFmpeg, OpenCV, PySceneDetect                          |
| OCR            | PaddleOCR  (`mock` available)                          |
| Speech         | Whisper Large-v3 / faster-whisper (`mock` available)  |
| Visual         | Qwen2.5-VL (`mock` available)                          |
| Reasoning      | `qwen/qwen-2.5-72b-instruct` via OpenRouter           |
| Packaging      | Docker + Docker Compose (Kubernetes-ready)            |

## Quick start (Docker, zero GPU)

```bash
cp .env.example .env          # mock providers by default — no GPU/keys needed
make up                       # postgres + redis + migrate + api + worker
curl localhost:8000/health
```

Submit a video and poll:

```bash
# upload a file
curl -F "file=@sample.mp4" localhost:8000/api/v1/analyze
# -> {"job_id":"job_...","video_id":"vid_...","status":"queued","poll_url":"..."}

curl localhost:8000/api/v1/status/job_xxx
curl localhost:8000/api/v1/report/job_xxx        # full report once completed
curl localhost:8000/api/v1/timeline/job_xxx      # timeline + player markers
```

Interactive API docs: <http://localhost:8000/docs>.

## Run the engine with no services (demo / CI)

```bash
make install                  # lightweight deps
python -m aimw.scripts.run_local sample.mp4   # full pipeline, mock providers
make test                     # unit + integration (offline, deterministic)
```

## Going to production (real models)

1. Build/run worker nodes with the ML extra: `pip install -e ".[ml]"` (GPU).
2. Set providers to real and supply an OpenRouter key in `.env`:
   ```
   AIMW_OCR_PROVIDER=real
   AIMW_SPEECH_PROVIDER=real
   AIMW_VISUAL_PROVIDER=real
   AIMW_OPENROUTER_API_KEY=sk-or-...
   ```
3. Point `AIMW_VISUAL`/VLM at your Qwen2.5-VL endpoint (see
   `services/visual/qwen_vl.py`). For platform URLs (TikTok/Reels/…), plug a
   `yt-dlp`-based downloader into `api/v1/endpoints/analyze.py::_download_url`.

## Project layout

```
src/aimw/
  domain/         enums, value objects (models.py), API schemas
  services/       ingestion, scene, frame, ocr/, speech/, visual/,
                  text_risk, fusion, timeline, reasoning/, reporting
  orchestration/  container (DI) + orchestrator (asyncio.gather)
  workers/        celery_app + tasks (persistence + webhooks)
  api/            FastAPI app, v1 endpoints, deps, error handlers
  db/             SQLAlchemy engine, ORM models, repositories
  scripts/        init_db, run_local
tests/            unit/ + integration/  (offline, deterministic)
docs/             implementation plan, architecture, DB schema, API contracts
```

## Documentation

- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [API contracts](docs/API_CONTRACTS.md)

## License

Apache-2.0.

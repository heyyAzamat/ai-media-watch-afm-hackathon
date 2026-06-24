# Implementation Plan

Status legend: ✅ implemented in this repo · 🔧 integration point (wire your
infra) · 🔭 roadmap.

## Phase 0 — Foundations ✅
- Settings (`pydantic-settings`), structured logging (`structlog`), IDs, time
  helpers.
- Domain layer: enums, Pydantic value objects, API schemas.
- DI container + provider `Protocol`s.

## Phase 1 — Media pipeline ✅
- Step 1 Ingestion (OpenCV probe) ✅
- Step 2 Scene detection (PySceneDetect, fixed-window fallback) ✅
- Step 3 Frame extraction (1 fps + scene keyframes) + audio demux (FFmpeg) ✅

## Phase 2 — Modality analysis (parallel) ✅
- Step 4 OCR: PaddleOCR provider + deterministic mock ✅
- Step 5 Speech: faster-whisper (Large-v3) provider + mock ✅
- Step 6 Visual: Qwen2.5-VL (OpenAI-compatible endpoint) provider + mock ✅
- Parallel dispatch via `asyncio.gather` ✅

## Phase 3 — Reasoning & explainability ✅
- Step 7 Text-risk lexicon/regex engine (transparent, term-level evidence) ✅
- Step 8 Fusion service + evidence graph (noisy-OR, adjacency) ✅
- Step 9 Timeline + Evidence Player markers ✅
- Step 10 OpenRouter judge: retries, timeout, JSON repair, regeneration,
  validation, rate-limit, deterministic fallback ✅
- Reporting service (final `AnalysisReport`) ✅

## Phase 4 — Async platform ✅
- Celery app + `analyze_video` task (persist every stage, progress updates) ✅
- Signed, retried webhooks on completion/failure ✅
- PostgreSQL schema (videos, jobs, scenes, frames, ocr, transcripts, visual,
  evidence_graphs, timelines, reports, audit_log) + repositories ✅

## Phase 5 — API ✅
- `POST /analyze`, `GET /status|analysis|report|timeline|evidence|risk`,
  `GET /health` ✅
- Request-ID middleware, uniform error contract, OpenAPI docs ✅

## Phase 6 — Delivery ✅
- Dockerfile (CPU base) + `requirements-ml.txt` (GPU) ✅
- docker-compose (postgres, redis, migrate, api, worker) ✅
- Makefile, `.env.example`, tests (unit + integration, offline) ✅

## Integration points 🔧
- **Platform downloaders** (TikTok/Reels/Shorts/Telegram/Facebook): plug a
  `yt-dlp`-based fetcher into `_download_url`.
- **VLM endpoint**: point `QwenVLProvider` at your vLLM/OpenRouter host.
- **Object storage**: swap local `storage/` for S3/GCS in frame/ingestion IO.
- **Migrations**: replace `scripts/init_db` with Alembic for production.

## Roadmap 🔭
- Alembic migrations + seed data.
- Per-frame batching/back-pressure for very long videos.
- Language-aware lexicons (multilingual OCR/speech).
- Human-in-the-loop review queue + label feedback loop to tune thresholds.
- SDKs: Python / TypeScript / Go generated from OpenAPI.
- Prometheus metrics + OpenTelemetry traces; Grafana dashboards.
- AuthN/Z (API keys / OAuth) and per-tenant isolation.

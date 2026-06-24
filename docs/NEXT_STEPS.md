# Next Steps / Handoff

Snapshot of what's done and what remains, so a fresh session (ideally on a
cheaper model) can continue cleanly.

## ✅ Done & verified
- Full platform scaffold (API, workers, DB, engine, services, docker, docs).
- `make test` → 19 tests pass, hermetic (mock providers, no network).
- **Real Whisper** (faster-whisper `small`, CPU) executed end-to-end.
- **Qwen2.5-VL via OpenRouter** (`qwen/qwen2.5-vl-72b-instruct`) executed — real
  image analysis returning scores + on-frame evidence.
- **72B judge via OpenRouter** (`qwen/qwen-2.5-72b-instruct`) executed once,
  `fallback_used=False`, real verdict (score 85, illegal_gambling).
- `.env` wired for real providers (gitignored). **ROTATE the OpenRouter key.**
- Python 3.13 installed (PaddlePaddle has no cp314 wheel; the 3.14 venv can't
  host PaddleOCR).
- `services/ocr/paddle.py` made robust to PaddleOCR 2.x (`.ocr`) and 3.x
  (`.predict`) return formats.

## 🔧 In progress — fully-real OCR leg
1. Create a 3.13 venv:
   `/opt/homebrew/opt/python@3.13/bin/python3.13 -m venv .venv313`
2. Install: `pydantic pydantic-settings structlog orjson tenacity httpx
   numpy Pillow paddleocr paddlepaddle`
3. Run real OCR on `scratchpad/frame.jpg` through `PaddleOcrProvider`
   (ocr=real, speech/visual=mock, fallback judge → no paid calls):
   `AIMW_OCR_PROVIDER=real AIMW_SPEECH_PROVIDER=mock AIMW_VISUAL_PROVIDER=mock
    AIMW_OPENROUTER_API_KEY=sk-or-changeme PYTHONPATH=src python <runner>`
4. Confirm `ocr.paddle.done detections>0` and OCR-derived timeline events.

## 🔭 Remaining to be "production-real"
- **Real video through Celery + Postgres**: `make up`, `POST /analyze` a real
  mp4, poll `/status`, fetch `/report`. Needs ffmpeg+OpenCV in the worker image
  (already in Dockerfile) and `AIMW_*_PROVIDER=real` on GPU workers.
- **Platform downloaders** (TikTok/Reels/Shorts/Telegram/FB): plug `yt-dlp`
  into `api/v1/endpoints/analyze.py::_download_url`.
- **Alembic migrations** to replace `scripts/init_db` create_all.
- **GPU image** (`requirements-ml.txt`) + provider env for real OCR/speech/VLM
  at scale; keep CPU API image lean.
- **AuthN/Z**, rate limiting, metrics (Prometheus/OTel), and per-tenant scoping.
- Multilingual lexicons; per-frame batching/back-pressure for long videos.
- Generate SDKs (Python/TS/Go) from the OpenAPI schema.

## Cost note
This session ran on Opus/xhigh with a very large injected system prompt; token
cost is dominated by model tier × context size × turns. For installs/wiring,
use Sonnet and `/compact` between phases.

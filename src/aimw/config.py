"""Centralized, environment-driven application settings.

Settings are framework-agnostic and importable from anywhere (API, workers,
core engine, tests). Nothing here imports FastAPI or Celery.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderMode = Literal["mock", "real", "disabled"]
OcrFrameStrategy = Literal["all", "keyframes", "dedup"]
VisualGating = Literal["off", "dedup", "text_risk"]


class Settings(BaseSettings):
    """Application configuration loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_prefix="AIMW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ─────────────────────────────────────────────────────────
    env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True
    api_prefix: str = "/api/v1"

    # ── Storage ─────────────────────────────────────────────────────────────
    storage_dir: Path = Path("./storage")
    max_upload_mb: int = 512
    allowed_extensions: str = "mp4,mov,webm"

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://aimw:aimw@localhost:5432/aimw"

    # ── Redis / Celery ──────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Scam model (the /check verdict source) ──────────────────────────────
    # "orchestrator" -> existing Whisper/fusion pipeline (default; works today)
    # "ml"           -> the ML team's model (services/scam_model/ml_model.py)
    # "mock"         -> fixed placeholder verdict (frontend UI work)
    scam_model_provider: Literal["orchestrator", "ml", "mock"] = "orchestrator"

    # ── Pipeline ────────────────────────────────────────────────────────────
    ocr_provider: ProviderMode = "mock"
    speech_provider: ProviderMode = "mock"
    visual_provider: ProviderMode = "mock"
    frames_per_second: float = 1.0
    fusion_window_seconds: float = 1.5
    # OCR is the dominant cost: only OCR visually-distinct frames by default.
    #   all       -> OCR every sampled frame (most thorough, slowest)
    #   keyframes -> OCR scene keyframes only (fastest)
    #   dedup     -> OCR perceptual-hash-deduplicated frames (best tradeoff)
    ocr_frame_strategy: OcrFrameStrategy = "dedup"
    ocr_dedup_hamming: int = 6  # max Hamming distance treated as a duplicate
    # OCR engine (PaddleOCR). Mobile det/rec + no document preprocessing is
    # ~3x faster on upright social-media overlay text at negligible accuracy
    # cost. Set model names to None to use PaddleOCR's bundled defaults.
    ocr_lang: str = "en"
    ocr_min_confidence: float = 0.5
    ocr_det_model_name: str | None = "PP-OCRv5_mobile_det"
    ocr_rec_model_name: str | None = "PP-OCRv5_mobile_rec"
    ocr_use_doc_preprocessing: bool = False  # doc-orientation + unwarp + textline-ori
    # GPU batching: send N frames per predict() call (also the recognition batch
    # size). On "gpu" this batches crops on-device for a large speedup; on "cpu"
    # it mainly removes per-call overhead.
    ocr_device: str = "cpu"  # "cpu" | "gpu" | "gpu:0"
    ocr_batch_size: int = 8

    # ── Speech (Whisper / faster-whisper) ───────────────────────────────────
    # On GPU use device="cuda", compute_type="float16". On CPU keep "int8".
    # distil-large-v3 is ~6x faster than large-v3 at near-equal accuracy.
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"
    whisper_vad_filter: bool = True
    whisper_beam_size: int = 1  # greedy; ~2-3x faster than beam=5, tiny WER cost
    whisper_batched: bool = True  # BatchedInferencePipeline (~4x on long audio)
    whisper_batch_size: int = 8

    # ── Visual (Qwen2.5-VL via OpenRouter, OpenAI-compatible) ────────────────
    visual_model: str = "qwen/qwen2.5-vl-72b-instruct"
    visual_max_concurrency: int = 4
    # Stage-gating cuts VLM calls (each is a paid remote request):
    #   off       -> analyze every scene keyframe
    #   dedup     -> analyze only visually-distinct keyframes (default; no recall
    #                loss, keeps OCR/speech/visual parallelism)
    #   text_risk -> analyze only keyframes near an OCR/speech risk hit; falls
    #                back to the dedup set when text is silent so visual-only
    #                risk is never missed. Runs visual AFTER OCR + speech.
    visual_gating: VisualGating = "dedup"
    visual_dedup_hamming: int = 6
    visual_gating_window_seconds: float = 3.0
    visual_max_keyframes: int = 0  # 0 = unlimited; else hard cap on VLM calls

    # ── Reasoning engine (OpenRouter) ───────────────────────────────────────
    openrouter_api_key: str = "sk-or-changeme"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    reasoning_model: str = "qwen/qwen-2.5-72b-instruct"
    reasoning_timeout_seconds: float = 120.0
    reasoning_max_retries: int = 3
    reasoning_allow_fallback: bool = True
    # Skip the (paid, ~10s) 72B judge entirely when fusion produced no evidence
    # and return the definitive empty verdict. Saves cost on benign videos.
    reasoning_skip_when_empty: bool = True
    # Faster judge cascade: run reasoning_fast_model (e.g. a 32B) first and only
    # escalate to reasoning_model (the authoritative 72B) when the fast judge is
    # uncertain (confidence below threshold, or catch-all category). Set
    # reasoning_escalation=false to disable the cascade (use reasoning_model
    # directly — which itself can be pointed at a 32B for pure speed).
    reasoning_fast_model: str = "qwen/qwen3-32b"
    reasoning_escalation: bool = False
    reasoning_escalation_confidence: float = 0.6

    # ── Webhooks ────────────────────────────────────────────────────────────
    webhook_timeout_seconds: float = 10.0
    webhook_max_retries: int = 3
    webhook_signing_secret: str = "change-me-webhook-secret"

    @field_validator("storage_dir")
    @classmethod
    def _resolve_storage(cls, v: Path) -> Path:
        return v.expanduser()

    @property
    def allowed_extension_set(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()}

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def frames_dir(self) -> Path:
        return self.storage_dir / "frames"

    def ensure_dirs(self) -> None:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()

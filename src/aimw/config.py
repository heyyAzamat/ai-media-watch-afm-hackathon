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

ProviderMode = Literal["mock", "real"]


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

    # ── Pipeline ────────────────────────────────────────────────────────────
    ocr_provider: ProviderMode = "mock"
    speech_provider: ProviderMode = "mock"
    visual_provider: ProviderMode = "mock"
    frames_per_second: float = 1.0
    fusion_window_seconds: float = 1.5

    # ── Speech (Whisper / faster-whisper) ───────────────────────────────────
    # On GPU use device="cuda", compute_type="float16". On CPU keep "int8".
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"
    whisper_vad_filter: bool = True

    # ── Visual (Qwen2.5-VL via OpenRouter, OpenAI-compatible) ────────────────
    visual_model: str = "qwen/qwen2.5-vl-72b-instruct"
    visual_max_concurrency: int = 4

    # ── Reasoning engine (OpenRouter) ───────────────────────────────────────
    openrouter_api_key: str = "sk-or-changeme"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    reasoning_model: str = "qwen/qwen-2.5-72b-instruct"
    reasoning_timeout_seconds: float = 120.0
    reasoning_max_retries: int = 3
    reasoning_allow_fallback: bool = True

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

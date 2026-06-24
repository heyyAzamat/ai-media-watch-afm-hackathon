"""Celery application factory."""

from __future__ import annotations

from celery import Celery

from ..config import get_settings
from ..logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)

celery_app = Celery(
    "aimw",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["aimw.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # heavy tasks: one at a time per worker process
    task_time_limit=60 * 60,  # hard limit 1h
    task_soft_time_limit=55 * 60,
    result_expires=60 * 60 * 24,
)

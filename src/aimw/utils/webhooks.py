"""Signed webhook delivery with retry/backoff.

On job completion the platform POSTs the final report to a caller-supplied
``webhook_url``. Payloads are signed with HMAC-SHA256 so receivers can verify
authenticity (header ``X-AIMW-Signature: sha256=<hex>``).
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
import orjson
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import get_settings
from ..logging_config import get_logger

log = get_logger(__name__)


def sign_payload(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def deliver_webhook(url: str, body: dict) -> bool:
    """Deliver a webhook synchronously with bounded retries.

    Returns True on a 2xx response, False if all attempts fail. Never raises —
    a failed webhook must not fail the analysis job.
    """
    settings = get_settings()
    payload = orjson.dumps(body)
    signature = sign_payload(payload, settings.webhook_signing_secret)
    headers = {
        "Content-Type": "application/json",
        "X-AIMW-Signature": signature,
        "User-Agent": "ai-media-watch-webhook/1.0",
    }

    @retry(
        stop=stop_after_attempt(settings.webhook_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        reraise=True,
    )
    def _post() -> httpx.Response:
        with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
            resp = client.post(url, content=payload, headers=headers)
            resp.raise_for_status()
            return resp

    try:
        _post()
        log.info("webhook.delivered", url=url)
        return True
    except Exception as exc:  # noqa: BLE001 - deliberately swallow, log instead
        log.warning("webhook.failed", url=url, error=str(exc))
        return False

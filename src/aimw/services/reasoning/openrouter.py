"""OpenRouter-backed final reasoning engine (Step 10).

Calls ``qwen/qwen-2.5-72b-instruct`` exactly once per video (with bounded
regeneration attempts on invalid JSON). Implements: retries with exponential
backoff, request timeout, response validation against :class:`JudgeVerdict`,
automatic JSON repair, a one-shot regeneration prompt, and a deterministic
fallback when everything else fails.
"""

from __future__ import annotations

import asyncio

import httpx
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...config import get_settings
from ...domain.enums import RiskCategory
from ...domain.models import JudgeVerdict
from ...logging_config import get_logger
from .base import compute_fallback_verdict
from .json_repair import parse_json_lenient
from .prompts import REPAIR_PROMPT, SYSTEM_PROMPT, build_user_prompt

log = get_logger(__name__)


class JudgeTransportError(RuntimeError):
    """Raised on retryable transport-level failures (network/5xx/429)."""


class OpenRouterReasoningEngine:
    def __init__(self) -> None:
        self._settings = get_settings()
        self.model = self._settings.reasoning_model  # authoritative (e.g. 72B)
        self._fast_model = self._settings.reasoning_fast_model.strip()
        self._escalation = self._settings.reasoning_escalation and bool(self._fast_model)
        self._escalation_conf = self._settings.reasoning_escalation_confidence
        # simple in-process rate limiter: max 1 concurrent judge call
        self._limiter = asyncio.Semaphore(1)

    async def judge(self, context: dict) -> JudgeVerdict:
        user_prompt = build_user_prompt(
            metadata=context["metadata"],
            ocr_risk=context["ocr_risk"],
            speech_risk=context["speech_risk"],
            transcript=context["transcript"],
            visual=context["visual"],
            graph=context["graph"],
            timeline=context["timeline"],
            allowed_categories=[c.value for c in RiskCategory],
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            async with self._limiter, httpx.AsyncClient(
                timeout=self._settings.reasoning_timeout_seconds
            ) as client:
                verdict = await self._cascade(client, messages)
            log.info("reasoning.done", risk_score=verdict.risk_score,
                     category=verdict.category, model=verdict.model)
            return verdict
        except Exception as exc:  # noqa: BLE001
            if self._settings.reasoning_allow_fallback:
                log.warning("reasoning.fallback", error=str(exc))
                return compute_fallback_verdict(
                    context["metadata"], context["graph"], context["timeline"]
                )
            raise

    def _should_escalate(self, verdict: JudgeVerdict) -> bool:
        """Escalate to the authoritative model when the fast judge is unsure:
        low confidence, or it fell back to the catch-all category."""
        return (
            verdict.confidence < self._escalation_conf
            or verdict.category == RiskCategory.SUSPICIOUS_FINANCIAL
        )

    async def _cascade(
        self, client: httpx.AsyncClient, messages: list[dict]
    ) -> JudgeVerdict:
        """Fast 32B first, escalating to the 72B only when the fast judge is
        uncertain. Without escalation, just use the configured model."""
        if not self._escalation:
            return await self._evaluate(client, messages, self.model)

        fast_verdict = await self._evaluate(client, messages, self._fast_model)
        if not self._should_escalate(fast_verdict):
            return fast_verdict
        log.info("reasoning.escalate", fast_model=self._fast_model,
                 fast_confidence=fast_verdict.confidence, to=self.model)
        return await self._evaluate(client, messages, self.model)

    async def _evaluate(
        self, client: httpx.AsyncClient, messages: list[dict], model: str
    ) -> JudgeVerdict:
        """One judge evaluation against ``model`` with a JSON-repair regeneration."""
        content = await self._call(client, messages, model)
        verdict = self._validate(content)
        if verdict is None:
            # One regeneration attempt with an explicit repair instruction.
            log.warning("reasoning.invalid_json", model=model, note="requesting regeneration")
            repair_messages = [
                *messages,
                {"role": "assistant", "content": content},
                {"role": "user", "content": REPAIR_PROMPT},
            ]
            content = await self._call(client, repair_messages, model)
            verdict = self._validate(content)
        if verdict is None:
            raise ValueError(f"judge ({model}) returned invalid JSON after regeneration")
        verdict.model = model
        return verdict

    @retry(
        retry=retry_if_exception_type(JudgeTransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call(self, client: httpx.AsyncClient, messages: list[dict], model: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "HTTP-Referer": "https://ai-media-watch.local",
            "X-Title": "AI Media Watch",
        }
        try:
            resp = await client.post(
                f"{self._settings.openrouter_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise JudgeTransportError(str(exc)) from exc

        if resp.status_code in (429, 500, 502, 503, 504):
            raise JudgeTransportError(f"retryable status {resp.status_code}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _validate(content: str) -> JudgeVerdict | None:
        data = parse_json_lenient(content)
        if data is None:
            return None
        data = _normalise(data)
        try:
            return JudgeVerdict.model_validate(data)
        except ValidationError as exc:
            log.warning("reasoning.validation_failed", error=str(exc))
            return None


def _normalise(data: dict) -> dict:
    """Coerce common LLM deviations into the JudgeVerdict shape."""
    out = dict(data)
    # category may arrive as a free-form string; map unknowns to SUSPICIOUS_FINANCIAL
    cat = str(out.get("category", "")).strip().lower().replace(" ", "_")
    valid = {c.value for c in RiskCategory}
    out["category"] = cat if cat in valid else (
        RiskCategory.SUSPICIOUS_FINANCIAL.value if out.get("risk_score", 0) else RiskCategory.NONE.value
    )
    try:
        out["risk_score"] = max(0, min(100, int(round(float(out.get("risk_score", 0))))))
    except (TypeError, ValueError):
        out["risk_score"] = 0
    try:
        out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.0))))
    except (TypeError, ValueError):
        out["confidence"] = 0.0
    out.setdefault("summary", "")
    ts = out.get("suspicious_timestamps") or []
    out["suspicious_timestamps"] = [
        float(t) for t in ts if isinstance(t, (int, float)) or str(t).replace(".", "", 1).isdigit()
    ]
    return out

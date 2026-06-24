"""Faster-judge cascade: fast 32B first, escalate to 72B only when unsure.

The HTTP layer (`_evaluate`) is monkeypatched so no network is touched; we only
assert the routing decisions.
"""

from __future__ import annotations

import pytest

from aimw.domain.enums import RiskCategory
from aimw.domain.models import JudgeVerdict
from aimw.services.reasoning.openrouter import OpenRouterReasoningEngine

FAST = "qwen/qwen3-32b"
BIG = "qwen/qwen-2.5-72b-instruct"


def _engine(*, escalation: bool, conf_threshold: float = 0.6) -> OpenRouterReasoningEngine:
    eng = OpenRouterReasoningEngine.__new__(OpenRouterReasoningEngine)  # skip __init__/settings
    eng.model = BIG
    eng._fast_model = FAST
    eng._escalation = escalation
    eng._escalation_conf = conf_threshold
    import asyncio

    eng._limiter = asyncio.Semaphore(1)
    return eng


def _verdict(confidence: float, category: RiskCategory = RiskCategory.ILLEGAL_GAMBLING) -> JudgeVerdict:
    return JudgeVerdict(risk_score=80, category=category, confidence=confidence, summary="x")


def _patch_evaluate(engine, verdict_by_model: dict[str, JudgeVerdict], calls: list[str]):
    async def fake_evaluate(client, messages, model):  # noqa: ANN001
        calls.append(model)
        v = verdict_by_model[model]
        v.model = model
        return v

    engine._evaluate = fake_evaluate  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_no_escalation_uses_primary_only():
    calls: list[str] = []
    eng = _engine(escalation=False)
    _patch_evaluate(eng, {BIG: _verdict(0.9)}, calls)
    v = await eng._cascade(client=None, messages=[])
    assert calls == [BIG]
    assert v.model == BIG


@pytest.mark.asyncio
async def test_confident_fast_judge_is_not_escalated():
    calls: list[str] = []
    eng = _engine(escalation=True, conf_threshold=0.6)
    _patch_evaluate(eng, {FAST: _verdict(0.92)}, calls)
    v = await eng._cascade(client=None, messages=[])
    assert calls == [FAST]  # 72B never called
    assert v.model == FAST


@pytest.mark.asyncio
async def test_low_confidence_fast_judge_escalates_to_72b():
    calls: list[str] = []
    eng = _engine(escalation=True, conf_threshold=0.6)
    _patch_evaluate(eng, {FAST: _verdict(0.4), BIG: _verdict(0.95)}, calls)
    v = await eng._cascade(client=None, messages=[])
    assert calls == [FAST, BIG]
    assert v.model == BIG  # authoritative verdict wins


@pytest.mark.asyncio
async def test_catch_all_category_escalates():
    calls: list[str] = []
    eng = _engine(escalation=True, conf_threshold=0.6)
    _patch_evaluate(
        eng,
        {FAST: _verdict(0.9, RiskCategory.SUSPICIOUS_FINANCIAL), BIG: _verdict(0.9)},
        calls,
    )
    await eng._cascade(client=None, messages=[])
    assert calls == [FAST, BIG]  # uncertain classification -> escalate

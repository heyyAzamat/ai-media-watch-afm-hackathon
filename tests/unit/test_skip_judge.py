"""Skip-judge-on-empty-evidence: the judge must NOT run when there's no evidence.

This is the critical honest-no-data control — the system must not fabricate a
verdict (or pay for an LLM call) for a video that produced no signals.
"""

from __future__ import annotations

import pytest

from aimw.domain.enums import RiskCategory
from aimw.domain.models import JudgeVerdict, Transcript
from aimw.orchestration.container import build_container
from aimw.orchestration.orchestrator import AnalysisOrchestrator


class _SpyJudge:
    model = "spy"

    def __init__(self) -> None:
        self.called = False

    async def judge(self, context: dict) -> JudgeVerdict:
        self.called = True
        return JudgeVerdict(
            risk_score=99, category=RiskCategory.ILLEGAL_GAMBLING, confidence=1.0,
            summary="should not be used when evidence is empty",
        )


class _SilentOcr:
    name = "silent"

    async def run(self, frames):  # noqa: ANN001
        return []


class _SilentSpeech:
    name = "silent"

    async def transcribe(self, audio_path):  # noqa: ANN001
        return Transcript()


class _SilentVisual:
    name = "silent"

    async def analyze(self, keyframes):  # noqa: ANN001
        return []


def _orchestrator_with(judge, *, silent: bool) -> AnalysisOrchestrator:
    container = build_container()
    container.reasoning = judge
    if silent:
        container.ocr = _SilentOcr()
        container.speech = _SilentSpeech()
        container.visual = _SilentVisual()
    return AnalysisOrchestrator(container)


@pytest.mark.asyncio
async def test_judge_skipped_when_no_evidence(prepared_video):
    spy = _SpyJudge()
    orch = _orchestrator_with(spy, silent=True)
    artifacts = await orch.run(prepared_video)

    assert spy.called is False, "judge must not be invoked on empty evidence"
    r = artifacts.report
    assert r.risk_score == 0
    assert r.category == RiskCategory.NONE
    assert r.llm_called is False
    assert r.fallback_used is False  # definitive answer, not a degraded fallback


@pytest.mark.asyncio
async def test_judge_called_when_evidence_present(prepared_video):
    # default mock providers emit scripted gambling content -> evidence exists
    spy = _SpyJudge()
    orch = _orchestrator_with(spy, silent=False)
    artifacts = await orch.run(prepared_video)

    assert spy.called is True
    assert artifacts.report.llm_called is True

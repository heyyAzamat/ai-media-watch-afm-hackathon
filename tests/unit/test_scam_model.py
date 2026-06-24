"""Tests for the ScamModel contract + loader."""
from __future__ import annotations

from aimw.config import get_settings
from aimw.services.scam_model import ScamModel, ScamVerdict, build_scam_model
from aimw.services.scam_model.base import MockScamModel


def test_mock_model_satisfies_contract_and_returns_verdict():
    model = MockScamModel()
    assert isinstance(model, ScamModel)  # runtime_checkable Protocol
    verdict = model.analyze("/tmp/whatever.mp4")
    assert isinstance(verdict, ScamVerdict)
    assert 0 <= verdict.risk_score <= 100
    assert verdict.category


def test_build_scam_model_selects_mock(monkeypatch):
    monkeypatch.setenv("AIMW_SCAM_MODEL_PROVIDER", "mock")
    get_settings.cache_clear()
    try:
        model = build_scam_model()
        assert model.name == "mock-scam-model"
    finally:
        get_settings.cache_clear()


def test_build_scam_model_defaults_to_orchestrator(monkeypatch):
    monkeypatch.delenv("AIMW_SCAM_MODEL_PROVIDER", raising=False)
    get_settings.cache_clear()
    try:
        model = build_scam_model()
        assert model.name == "orchestrator-pipeline"
    finally:
        get_settings.cache_clear()

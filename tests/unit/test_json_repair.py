from __future__ import annotations

from aimw.services.reasoning.json_repair import parse_json_lenient


def test_plain_json():
    assert parse_json_lenient('{"a": 1}') == {"a": 1}


def test_code_fenced_json():
    raw = "Here is the result:\n```json\n{\"risk_score\": 92}\n```\nDone."
    assert parse_json_lenient(raw) == {"risk_score": 92}


def test_json_embedded_in_prose():
    raw = 'The verdict is {"category": "illegal_gambling", "risk_score": 88} based on evidence.'
    assert parse_json_lenient(raw) == {"category": "illegal_gambling", "risk_score": 88}


def test_trailing_comma_repaired():
    assert parse_json_lenient('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_nested_braces_balanced():
    raw = '{"evidence": {"ocr": ["a", "b"]}, "score": 5}'
    assert parse_json_lenient(raw) == {"evidence": {"ocr": ["a", "b"]}, "score": 5}


def test_invalid_returns_none():
    assert parse_json_lenient("not json at all") is None
    assert parse_json_lenient("") is None

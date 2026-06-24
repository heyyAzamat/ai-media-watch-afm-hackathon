"""Lenient JSON parsing + repair for LLM responses.

LLMs sometimes wrap JSON in prose or code fences, emit trailing commas, or use
single quotes. This module extracts and repairs the most common deviations so a
single judge call rarely needs a regeneration round-trip.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _extract_braced(text: str) -> str | None:
    """Return the first balanced ``{...}`` block in ``text``."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_json_lenient(raw: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object from a possibly-noisy LLM response."""
    if not raw:
        return None

    candidates: list[str] = []
    fence = _FENCE_RE.search(raw)
    if fence:
        candidates.append(fence.group(1))
    braced = _extract_braced(raw)
    if braced:
        candidates.append(braced)
    candidates.append(raw.strip())

    for candidate in candidates:
        for attempt in (candidate, _repair(candidate)):
            try:
                result = json.loads(attempt)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def _repair(text: str) -> str:
    repaired = _TRAILING_COMMA_RE.sub(r"\1", text)
    # Replace single-quoted keys/values only when no double quotes are present
    # (avoids corrupting apostrophes inside valid JSON strings).
    if '"' not in repaired and "'" in repaired:
        repaired = repaired.replace("'", '"')
    return repaired

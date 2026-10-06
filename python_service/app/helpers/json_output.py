"""Helpers for parsing structured JSON out of agent model output."""

from __future__ import annotations

import json
from typing import Any


def first_json_object(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object embedded in model output.

    Agent outputs may wrap JSON in markdown fences or prefix it with prose;
    this scans the text for the first balanced JSON object.
    """
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, TypeError):
                    return None
    return None

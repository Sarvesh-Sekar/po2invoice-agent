"""Serialization helpers for the persisted HITL context blob.

The ``agent_runs.hitl_context`` column stores a JSON string shaped like
``{"question": "...", "context": {...}}`` so the frontend can tell which
human decision a paused run is waiting for (e.g. ``create_customer`` vs
``purchase_order_review``).
"""

from __future__ import annotations

import json
from typing import Any


def interrupt_hitl_payload(hint: Any) -> dict[str, Any]:
    """Project a LangGraph interrupt value onto the persisted hitl blob."""
    hint_dict = hint if isinstance(hint, dict) else {}
    return {
        "question": hint_dict.get("question") if isinstance(hint_dict, dict) else None,
        "context": (hint_dict.get("context") or {}) if isinstance(hint_dict, dict) else {},
    }


def parse_hitl_context(raw: str | None) -> dict[str, Any]:
    """Parse the persisted blob back into ``{"question", "context"}``.

    Legacy blobs that stored the bare context dict are still understood.
    """
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    if not isinstance(parsed, dict):
        return {"question": None, "context": {}}
    if isinstance(parsed.get("context"), dict):
        return parsed
    return {"question": None, "context": parsed}

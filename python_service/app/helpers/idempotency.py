"""Idempotency helpers for event-driven workflows."""

from __future__ import annotations

from datetime import UTC, datetime

from app.exceptions.base import BaseAppError


class DuplicateEventError(BaseAppError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            "DUPLICATE_EVENT",
            f"Event with idempotency key '{idempotency_key}' has already been processed",
            status_code=409,
        )


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def normalize_idempotency_key(event: str | None, sale_id: str) -> str:
    """Build a stable idempotency key from an optional key and the sale id.

    A whitespace-only key is treated as absent: trimming first keeps a blank
    key from collapsing into the empty string, which every event would share.
    """
    if event and (trimmed := str(event).strip()):
        return trimmed
    return f"sale:{sale_id}"

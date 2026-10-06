"""Internal event payloads (Go service -> Python service)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

#: Canonical event name in the documented contract.
_EVENT_NAME = "SALE_DELIVERED"


class SaleDeliveredEvent(BaseModel):
    sale_id: uuid.UUID
    event: Literal["SALE_DELIVERED"] = "SALE_DELIVERED"
    occurred_at: str | None = Field(default=None, description="ISO-8601 timestamp")
    idempotency_key: str | None = None

    @field_validator("event", mode="before")
    @classmethod
    def _normalize_event_name(cls, value: str) -> str:
        # Tolerate the Go client's historical "sale-delivered"/"sale_delivered"
        # spellings without weakening the canonical contract for other callers.
        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        if normalized != _EVENT_NAME:
            raise ValueError(f"event must be {_EVENT_NAME}")
        return _EVENT_NAME

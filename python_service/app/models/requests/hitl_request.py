"""HITL decision request model."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HITLDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT", "EDIT"]
    changes: dict | None = Field(default=None, description="Edits applied when decision is EDIT")
    reason: str | None = Field(default=None, description="Human annotation for the decision")

"""Agent HTTP responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WorkflowName = Literal["PURCHASE_ORDER", "INVOICE"]
WorkflowStatus = Literal["QUEUED", "RUNNING", "WAITING_FOR_HUMAN", "COMPLETED", "FAILED"]


class HitlContext(BaseModel):
    message: str = Field(default="Purchase order requires human decision")
    options: list[str] = Field(default_factory=lambda: ["APPROVE", "REJECT", "EDIT"])
    question: str | None = Field(default=None, description="Which human decision is pending")
    context: dict = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    run_id: str
    workflow: WorkflowName
    status: WorkflowStatus
    current_step: str | None = None
    po_id: str | None = None
    sale_id: str | None = None
    invoice_id: str | None = None
    hitl: HitlContext | None = None

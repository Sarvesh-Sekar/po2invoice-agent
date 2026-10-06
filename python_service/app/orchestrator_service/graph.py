"""LangGraph workflow state definitions.

Routers/services pass workflow input; agents update state fields; nodes are
pure routing/evaluation functions kept separate from agent logic.
"""

from __future__ import annotations

from typing import TypedDict


class POWorkflowState(TypedDict, total=False):
    # identity / tracing
    run_id: str
    thread_id: str
    workflow: str

    # source document
    file_bytes: bytes
    file_name: str
    mime_type: str
    source_file_url: str

    # extraction (subgraph)
    extracted_po: dict | None
    po_total_amount: float
    extracted_header_fields: list | None
    extracted_line_item_fields: list | None
    extraction_result: dict | None
    extraction_error: str | None
    extraction_error_code: str | None
    #: Resolved by extraction; a hint for the verifier's header branch, which
    #: remains the authoritative owner of the customer identity.
    customer_id: str | None

    # verification (VerifierAgent subgraph: header | line item | commercial)
    verification_result: dict | None
    criteria_met: bool
    hitl_required: bool
    hitl_context: dict | None

    # HITL / edits
    hitl_decision: dict | None
    edits_applied: bool
    edit_rounds: int

    # outcome
    po_id: str | None
    sale_id: str | None
    sale_status: str | None

    # workflow lifecycle
    status: str
    current_step: str
    workflow_error: dict | None


class InvoiceWorkflowState(TypedDict, total=False):
    # identity / tracing
    run_id: str
    thread_id: str
    workflow: str
    idempotency_key: str

    # inputs
    sale_id: str
    sale: dict | None

    # invoice generation
    invoice_id: str | None
    invoice_number: str | None
    invoice_status: str | None
    s3_url: str | None

    # workflow lifecycle
    status: str
    current_step: str
    workflow_error: dict | None

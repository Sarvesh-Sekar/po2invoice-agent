"""State schema for the Extraction Agent subgraph."""

from __future__ import annotations

from typing import Any, TypedDict


class ExtractionState(TypedDict, total=False):
    # inherited / identity fields
    run_id: str
    workflow: str | None
    thread_id: str | None

    # document source
    file_bytes: bytes | None
    document: bytes | None
    mime_type: str
    source_file_url: str | None
    po_id: str | None

    # document processing output
    document_text: str
    document_lines: list[dict[str, Any]]

    # customer identification
    customer_id: str | None
    customer_name: str | None
    customer_gst_no: str | None

    # memory + field catalogue
    field_definitions: list[dict[str, Any]]
    memories: list[dict[str, Any]]

    # semantic extraction
    candidates: list[dict[str, Any]]
    verdicts: list[dict[str, Any]]

    # persisted output
    extracted_header_fields: list[dict[str, Any]]
    extracted_line_item_fields: list[list[dict[str, Any]]]
    extraction_result: dict[str, Any]

    # forward-compatible view for the parent graph (ExtractedPO shape)
    extracted_po: dict[str, Any] | None
    po_total_amount: float | None

    # control/flags
    retry_count: int
    extraction_error: str | None
    extraction_error_code: str | None
    status: str
    current_step: str


def init_extraction_state(**overrides: Any) -> ExtractionState:
    state: ExtractionState = {
        "run_id": "",
        "workflow": "po_workflow",
        "thread_id": None,
        "file_bytes": None,
        "document": None,
        "mime_type": "application/pdf",
        "source_file_url": None,
        "po_id": None,
        "document_text": "",
        "document_lines": [],
        "customer_id": None,
        "customer_name": None,
        "customer_gst_no": None,
        "field_definitions": [],
        "memories": [],
        "candidates": [],
        "verdicts": [],
        "extracted_header_fields": [],
        "extracted_line_item_fields": [],
        "extraction_result": {},
        "extracted_po": None,
        "po_total_amount": None,
        "retry_count": 0,
        "extraction_error": None,
        "extraction_error_code": None,
        "status": "RUNNING",
        "current_step": "start",
    }
    state.update(overrides)
    return state

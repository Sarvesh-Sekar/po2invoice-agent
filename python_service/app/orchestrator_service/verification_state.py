"""State schema for the Verifier Agent subgraph.

The three business validations are independent, so each owns its own state key
and the fan-out needs no reducer. ``aggregate`` is the single fan-in node that
collapses them into one normalized ``verification_result``.
"""

from __future__ import annotations

from typing import Any, TypedDict

#: Branch name -> state key holding that branch's result.
BRANCH_KEYS: dict[str, str] = {
    "header": "header_validation",
    "line_item": "line_item_validation",
    "commercial": "commercial_validation",
}

#: Node name mapping used by the verifier subgraph.
NODE_KEYS: dict[str, str] = {
    "header": "header_field_verifier",
    "line_item": "line_item_field_verifier",
    "commercial": "commercial_field_verifier",
}


class VerificationState(TypedDict, total=False):
    # inherited / identity fields
    run_id: str
    thread_id: str | None
    workflow: str | None

    # inputs
    extracted_po: dict[str, Any] | None
    po_total_amount: float | None
    #: Resolved by the extraction subgraph; a hint only. The header branch is
    #: the authoritative owner of the customer identity.
    customer_id: str | None

    # branch outputs (one key per branch: parallel writes never collide)
    header_validation: dict[str, Any] | None
    line_item_validation: dict[str, Any] | None
    commercial_validation: dict[str, Any] | None

    # aggregate output
    verification_result: dict[str, Any] | None
    criteria_met: bool
    hitl_required: bool
    hitl_context: dict[str, Any] | None

    # lifecycle
    current_step: str
    status: str


def init_verification_state(**overrides: Any) -> VerificationState:
    """Build a fresh verification state.

    Every invocation starts clean so a HITL edit that re-enters the verifier
    can never inherit a stale branch result from a previous round.
    """
    state: VerificationState = {
        "run_id": "",
        "workflow": "po_workflow",
        "thread_id": None,
        "extracted_po": None,
        "po_total_amount": None,
        "customer_id": None,
        "header_validation": None,
        "line_item_validation": None,
        "commercial_validation": None,
        "verification_result": None,
        "criteria_met": False,
        "hitl_required": False,
        "hitl_context": None,
        "current_step": "start",
        "status": "RUNNING",
    }
    state.update(overrides)
    return state

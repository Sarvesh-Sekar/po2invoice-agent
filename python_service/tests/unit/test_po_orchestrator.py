"""PO orchestrator workflow: happy path, HITL approve/reject/edit."""

from __future__ import annotations

import uuid

from app.orchestrator_service.po_orchestrator import POOrchestrator
from tests.conftest import _StubVerifier


def _thread() -> str:
    return f"po-{uuid.uuid4()}"


async def test_happy_path_routes_straight_to_sales(
    checkpointer, stub_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    orch = POOrchestrator(
        extraction_agent=stub_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()

    result = await orch.invoke(
        {
            "run_id": str(uuid.uuid4()),
            "thread_id": _thread(),
            "workflow": "PURCHASE_ORDER",
            "file_bytes": b"pdf",
            "file_name": "po.pdf",
            "mime_type": "application/pdf",
            "status": "RUNNING",
        },
        "happy",
    )
    assert result["criteria_met"] is True
    assert result.get("sale_id")
    assert result.get("status") == "COMPLETED"
    assert "__interrupt__" not in result


async def test_blocking_issue_goes_to_hitl_then_approve(
    checkpointer, stub_bad_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    orch = POOrchestrator(
        extraction_agent=stub_bad_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    first = await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    assert "__interrupt__" in first
    assert first["hitl_required"] is True

    resumed = await orch.resume(thread, {"decision": "APPROVE", "reason": "ok"})
    assert resumed.get("sale_id")
    assert resumed.get("status") == "COMPLETED"


async def test_reject_ends_without_sale(checkpointer, stub_bad_extraction_agent, stub_verifier_agent, stub_sales_agent):
    orch = POOrchestrator(
        extraction_agent=stub_bad_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    resumed = await orch.resume(thread, {"decision": "REJECT", "reason": "no"})
    assert not resumed.get("sale_id")
    assert resumed.get("po_id") is None


async def test_edit_reverifies_then_sales(
    checkpointer, stub_bad_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    orch = POOrchestrator(
        extraction_agent=stub_bad_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    first = await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    assert "__interrupt__" in first

    resumed = await orch.resume(
        thread,
        {"decision": "EDIT", "changes": {"customer": "Acme Ltd.", "gst_no": "GST001"}},
    )
    assert resumed.get("sale_id")
    assert resumed["criteria_met"] is True


async def test_edit_does_not_re_extract_the_document(
    checkpointer, stub_bad_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    """An HITL edit corrects the extracted PO; re-parsing would discard it."""
    orch = POOrchestrator(
        extraction_agent=stub_bad_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    assert stub_bad_extraction_agent.calls == 1

    await orch.resume(thread, {"decision": "EDIT", "changes": {"customer": "Acme Ltd."}})

    assert stub_bad_extraction_agent.calls == 1, "HITL edit re-ran extraction"
    # Verification re-ran on the edited PO, which is the whole point of the edit loop.
    assert stub_verifier_agent.calls == 2


async def test_one_branch_failure_reaches_hitl(checkpointer, stub_extraction_agent, stub_sales_agent):
    orch = POOrchestrator(
        extraction_agent=stub_extraction_agent,
        verifier_agent=_StubVerifier(failing_branch="commercial"),
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    result = await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    assert "__interrupt__" in result
    assert "VALIDATION_BRANCH_FAILED" in [issue["code"] for issue in result["hitl_context"]["blocking_issues"]]


async def test_extraction_failure_terminates_without_hitting_verifier(
    checkpointer, stub_failed_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    orch = POOrchestrator(
        extraction_agent=stub_failed_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()

    result = await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )
    assert result["status"] == "FAILED"
    assert result["workflow_error"]["code"] == "DOCUMENT_PROCESSING_FAILED"
    assert "__interrupt__" not in result
    assert not result.get("sale_id")
    assert stub_verifier_agent.calls == 0, "verification ran on an unreadable document"


async def test_resume_completes_thread_checkpoint(
    checkpointer, stub_bad_extraction_agent, stub_verifier_agent, stub_sales_agent
):
    orch = POOrchestrator(
        extraction_agent=stub_bad_extraction_agent,
        verifier_agent=stub_verifier_agent,
        sales_agent=stub_sales_agent,
        checkpointer=checkpointer,
    )
    await orch.compile()
    thread = _thread()
    await orch.invoke(
        {"run_id": str(uuid.uuid4()), "thread_id": thread, "workflow": "PURCHASE_ORDER", "file_bytes": b"pdf"},
        thread,
    )

    # One decision per run; a second decision must not replay the graph.
    await orch.resume(thread, {"decision": "REJECT", "reason": "no"})
    state = await orch.get_state(thread)
    assert "hitl" not in state["next"]

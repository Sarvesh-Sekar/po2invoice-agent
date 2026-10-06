"""Invoice orchestrator workflow: sale delivered -> invoice generated -> END.

There is no message-delivery stage any more; reaching END after the invoice
node is the whole contract.
"""

from __future__ import annotations

import uuid

import pytest

from app.exceptions.agent_exceptions import WorkflowExecutionError
from app.orchestrator_service.invoice_orchestrator import InvoiceOrchestrator


def _state() -> tuple[dict, str]:
    thread = f"invoice-{uuid.uuid4()}"
    return (
        {
            "run_id": str(uuid.uuid4()),
            "thread_id": thread,
            "workflow": "INVOICE",
            "sale_id": str(uuid.uuid4()),
            "status": "RUNNING",
            "current_step": "invoice",
        },
        thread,
    )


def test_graph_has_no_message_node(stub_invoice_agent):
    orch = InvoiceOrchestrator(invoice_agent=stub_invoice_agent, checkpointer=None)
    nodes = set(orch._build_graph().nodes)
    assert "invoice" in nodes
    assert "message" not in nodes
    assert "finalize" in nodes


async def test_invoice_flow_completes_without_messaging(checkpointer, stub_invoice_agent):
    orch = InvoiceOrchestrator(invoice_agent=stub_invoice_agent, checkpointer=checkpointer)
    await orch.compile()

    state, thread = _state()
    result = await orch.invoke(state, thread)

    assert result.get("invoice_id")
    assert result.get("invoice_status") == "GENERATED"
    assert result.get("status") == "COMPLETED"
    assert "__interrupt__" not in result
    # No messaging keys leak into invoice state any more.
    assert "message_status" not in result
    assert "gst_irn" not in result


async def test_invoice_agent_runs_exactly_once(checkpointer, stub_invoice_agent):
    """A second resume must not regenerate and double-charge an invoice."""
    calls = 0

    async def _counting(state):
        nonlocal calls
        calls += 1
        return await stub_invoice_agent.execute(state)

    stub_invoice_agent.run = _counting
    orch = InvoiceOrchestrator(invoice_agent=stub_invoice_agent, checkpointer=checkpointer)
    await orch.compile()

    state, thread = _state()
    await orch.invoke(state, thread)
    await orch.resume(thread, {})

    assert calls == 1


async def test_invoice_generation_failure_surfaces_and_never_completes(checkpointer, stub_invoice_agent):
    """A rendering failure must fail loudly rather than finalize as COMPLETED."""

    async def _fail(state):
        raise RuntimeError("pdf rendering failed")

    stub_invoice_agent.execute = _fail
    orch = InvoiceOrchestrator(invoice_agent=stub_invoice_agent, checkpointer=checkpointer)
    await orch.compile()

    state, thread = _state()
    with pytest.raises(WorkflowExecutionError):
        await orch.invoke(state, thread)

    snapshot = await orch.get_state(thread)
    assert snapshot["values"].get("invoice_id") is None
    assert snapshot["values"].get("status") != "COMPLETED"

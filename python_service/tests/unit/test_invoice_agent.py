"""InvoiceAgent unit tests (no database / no model required)."""

from __future__ import annotations

import json

import pytest

from app.agents.invoice_agent import InvoiceAgent
from app.exceptions.agent_exceptions import WorkflowExecutionError


class _ScriptedAgent:
    def __init__(self, output: str) -> None:
        self._output = output

    async def ainvoke(self, payload: dict) -> dict:
        return {"output": self._output}


def _build_agent(monkeypatch: pytest.MonkeyPatch, output: str) -> InvoiceAgent:
    agent = InvoiceAgent([], object())
    monkeypatch.setattr(InvoiceAgent, "_ensure_agent", lambda self: _ScriptedAgent(output))
    return agent


def _json(**fields) -> str:
    return json.dumps(fields)


async def test_invoice_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _json(
        invoice_id="inv-1",
        invoice_number="INV-20260923-ABC12345",
        invoice_status="GENERATED",
        s3_url="https://bucket/invoices/sale-1/INV.pdf",
    )
    agent = _build_agent(monkeypatch, output)
    update = await agent.invoke_agent({"sale_id": "sale-1"})
    assert update["invoice_id"] == "inv-1"
    assert update["invoice_status"] == "GENERATED"
    assert update["s3_url"].startswith("https://bucket/")
    assert update["current_step"] == "invoice"
    assert update["status"] == "RUNNING"


async def test_invoice_does_not_emit_gst_irn(monkeypatch: pytest.MonkeyPatch) -> None:
    """IRN generation is out of scope; a stray model value is dropped, not stored."""
    output = _json(invoice_id="inv-1", invoice_status="GENERATED", gst_irn="IRN123")
    agent = _build_agent(monkeypatch, output)
    update = await agent.invoke_agent({"sale_id": "sale-1"})
    assert "gst_irn" not in update


async def test_invoice_number_injected_when_model_echo_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _json(invoice_id="inv-1", invoice_status="GENERATED")
    agent = _build_agent(monkeypatch, output)
    update = await agent.invoke_agent({"sale_id": "sale-1"})
    assert update["invoice_number"].startswith("INV-")


async def test_invoice_missing_sale_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, _json(invoice_id="inv-1"))
    with pytest.raises(WorkflowExecutionError):
        await agent.invoke_agent({})


async def test_invoice_missing_invoice_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, _json(invoice_status="GENERATED"))
    with pytest.raises(WorkflowExecutionError):
        await agent.invoke_agent({"sale_id": "sale-1"})


async def test_invoice_unparsable_output_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, "no output")
    with pytest.raises(WorkflowExecutionError):
        await agent.invoke_agent({"sale_id": "sale-1"})

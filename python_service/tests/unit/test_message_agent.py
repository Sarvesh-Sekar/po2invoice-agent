"""MessageAgent unit tests (no database / no model required)."""

from __future__ import annotations

import json

import pytest

from app.agents.message_agent import MessageAgent
from app.exceptions.client_exceptions import WhatsAppError


class _ScriptedAgent:
    def __init__(self, output: str, raise_error: bool = False) -> None:
        self._output = output
        self._raise_error = raise_error

    async def ainvoke(self, payload: dict) -> dict:
        if self._raise_error:
            raise WhatsAppError(details={"reason": "down"})
        return {"output": self._output}


def _build_agent(monkeypatch: pytest.MonkeyPatch, output: str, raise_error: bool = False) -> MessageAgent:
    agent = MessageAgent([], object())
    monkeypatch.setattr(MessageAgent, "_ensure_agent", lambda self: _ScriptedAgent(output, raise_error))
    return agent


def _json(**fields) -> str:
    return json.dumps(fields)


def _state() -> dict:
    return {
        "sale_id": "sale-1",
        "invoice_id": "inv-1",
        "invoice_number": "INV-20260923-ABC12345",
        "invoice_status": "GENERATED",
        "s3_url": "https://bucket/invoices/sale-1/INV.pdf",
        "customer_phone": "+911234567890",
        "invoice_total": "200.00",
    }


async def test_message_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _json(message_status="SENT", invoice_status="SENT")
    agent = _build_agent(monkeypatch, output)
    update = await agent.invoke_agent(_state())
    assert update["message_status"] == "SENT"
    assert update["invoice_status"] == "SENT"
    assert update["current_step"] == "message"


async def test_message_delivery_failure_keeps_invoice_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, "", raise_error=True)
    update = await agent.invoke_agent(_state())
    assert update["message_status"] == "FAILED"
    assert update["invoice_status"] == "GENERATED"
    assert update["status"] == "COMPLETED"


async def test_message_skipped_without_invoice_document(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, "")
    state = _state()
    state.pop("s3_url")
    update = await agent.invoke_agent(state)
    assert update["message_status"] == "SKIPPED"
    assert update["invoice_status"] == "GENERATED"
    assert "message_note" in update


async def test_message_skipped_without_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, "")
    state = _state()
    state.pop("customer_phone")
    update = await agent.invoke_agent(state)
    assert update["message_status"] == "SKIPPED"
    assert "message_note" in update

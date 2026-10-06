"""SalesAgent unit tests (no database / no model required)."""

from __future__ import annotations

import json

import pytest

from app.agents.sales_agent import SalesAgent
from app.exceptions.agent_exceptions import POVerificationError


class _ScriptedAgent:
    def __init__(self, output: str) -> None:
        self._output = output

    async def ainvoke(self, payload: dict) -> dict:
        return {"output": self._output}


def _build_agent(monkeypatch: pytest.MonkeyPatch, output: str) -> SalesAgent:
    agent = SalesAgent([], object())
    monkeypatch.setattr(SalesAgent, "_ensure_agent", lambda self: _ScriptedAgent(output))
    return agent


def _json(**fields) -> str:
    return json.dumps(fields)


async def test_sales_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    output = _json(po_id="po-1", sale_id="sale-1", sale_status="CREATED")
    agent = _build_agent(monkeypatch, output)
    update = await agent.invoke_agent(
        {
            "extracted_po": {},
            "verification_result": {"customer_id": "cust-1"},
            "source_file_url": "https://bucket/po.pdf",
        }
    )
    assert update["po_id"] == "po-1"
    assert update["sale_id"] == "sale-1"
    assert update["sale_status"] == "CREATED"
    assert update["status"] == "COMPLETED"
    assert update["current_step"] == "sales"


async def test_sales_missing_customer_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, _json(po_id="po-1", sale_id="sale-1"))
    with pytest.raises(POVerificationError):
        await agent.invoke_agent({"extracted_po": {}})


async def test_sales_missing_sale_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(
        monkeypatch,
        _json(po_id="po-1"),
    )
    with pytest.raises(POVerificationError):
        await agent.invoke_agent({"extracted_po": {}, "verification_result": {"customer_id": "cust-1"}})


async def test_sales_missing_po_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, _json(sale_id="sale-1"))
    with pytest.raises(POVerificationError):
        await agent.invoke_agent({"extracted_po": {}, "verification_result": {"customer_id": "cust-1"}})


async def test_sales_unparsable_output_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, "no output")
    with pytest.raises(POVerificationError):
        await agent.invoke_agent({"extracted_po": {}, "verification_result": {"customer_id": "cust-1"}})

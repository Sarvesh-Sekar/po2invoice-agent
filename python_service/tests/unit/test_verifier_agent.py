"""VerifierAgent unit tests (no database / no model required).

Each branch is a scoped ``create_agent``; tests swap in a scripted agent via
monkeypatch so the fan-out/fan-in and the aggregation logic are exercised
deterministically without a model call.
"""

from __future__ import annotations

import json

import pytest

from app.agents.verifier_agent import VerifierAgent
from app.config.settings import Settings
from app.exceptions.agent_exceptions import POVerificationError
from app.models.domain import ValidationBranchResult
from app.orchestrator_service.verification_state import BRANCH_KEYS

_EXTRACTED = {
    "po_number": "PO-1001",
    "customer": "Acme Ltd.",
    "gst_no": "GST001",
    "line_items": [{"sku": "SKU-1", "product_name": "Widget", "quantity": 2, "unit_price": 100}],
}

_STATE = {"run_id": "run-1", "extracted_po": _EXTRACTED, "po_total_amount": 200.0, "customer_id": "cust-1"}


class _ScriptedAgent:
    """Stands in for one branch's compiled ``create_agent``."""

    def __init__(self, output: str | None = None, *, error: Exception | None = None) -> None:
        self._output = output
        self._error = error
        self.calls: list[dict] = []

    async def ainvoke(self, payload: dict) -> dict:
        self.calls.append(payload)
        if self._error is not None:
            raise self._error
        return {"output": self._output}


def _json(**fields) -> str:
    return json.dumps(fields)


def _passing(branch: str, **details) -> str:
    return _json(passed=True, issues=[], details=details)


def _failing(code: str = "PRICE_VALIDATION_FAILED") -> str:
    return _json(
        passed=False,
        issues=[{"code": code, "message": "price off catalogue", "severity": "error", "details": {}}],
        details={},
    )


def _build_agent(monkeypatch: pytest.MonkeyPatch, outputs: dict[str, str], **kwargs) -> VerifierAgent:
    """Wire a VerifierAgent whose branches return canned reports."""
    agent = VerifierAgent([], [], [], object(), **kwargs)
    scripted = {branch: _ScriptedAgent(output) for branch, output in outputs.items()}

    def _ensure_branch_agent(self, branch: str, _prompt_key: str, _tools_attr: str):
        return scripted.setdefault(branch, _ScriptedAgent(_passing(branch)))

    monkeypatch.setattr(VerifierAgent, "_ensure_branch_agent", _ensure_branch_agent)
    agent._scripted = scripted  # type: ignore[attr-defined]
    return agent


_ALL_PASSING = {
    "header": _passing("header", customer_id="cust-1", customer_verified=True),
    "line_item": _passing("line_item", products_verified=1, products_total=1),
    "commercial": _passing("commercial", policy_applied=["pricing"], customer_history_checked=True),
}


# ---- graph shape ------------------------------------------------------------


def test_graph_has_three_branches_fanning_into_aggregate():
    nodes = set(VerifierAgent([], [], [], object()).create_agent().get_graph().nodes)
    assert {"header_validation", "line_item_validation", "commercial_validation", "aggregate"} <= nodes
    assert set(BRANCH_KEYS.values()) == nodes - {"__start__", "__end__", "aggregate"}


def test_graph_is_compiled_once():
    agent = VerifierAgent([], [], [], object())
    assert agent.create_agent() is agent.create_agent()


# ---- happy path -------------------------------------------------------------


async def test_all_branches_passing_routes_to_sales(monkeypatch: pytest.MonkeyPatch):
    agent = _build_agent(monkeypatch, dict(_ALL_PASSING))
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is True
    assert update["hitl_required"] is False
    assert update["hitl_context"] is None
    assert update["current_step"] == "verification"
    result = update["verification_result"]
    assert result["has_blocking_issues"] is False
    assert result["customer_id"] == "cust-1"
    assert result["products_verified"] == 1
    assert result["policy_applied"] == ["pricing"]


async def test_all_three_branches_actually_execute(monkeypatch: pytest.MonkeyPatch):
    """The branches are independent; none may be skipped by the fan-out."""
    agent = _build_agent(monkeypatch, dict(_ALL_PASSING))
    await agent.invoke_agent(dict(_STATE))

    assert set(agent._scripted) == {"header", "line_item", "commercial"}
    for branch, scripted in agent._scripted.items():
        assert scripted.calls, f"branch {branch} did not run"


async def test_branches_execute_concurrently(monkeypatch: pytest.MonkeyPatch):
    """Fan-out is real parallelism, not a sequential loop."""

    class _Slow(_ScriptedAgent):
        async def ainvoke(self, payload: dict) -> dict:
            import asyncio

            await asyncio.sleep(0.05)
            return await super().ainvoke(payload)

    agent = VerifierAgent([], [], [], object())
    monkeypatch.setattr(
        VerifierAgent,
        "_ensure_branch_agent",
        lambda self, branch, _p, _t: _Slow(_passing(branch, customer_id="cust-1", customer_verified=True)),
    )

    import time

    started = time.perf_counter()
    update = await agent.invoke_agent(dict(_STATE))
    elapsed = time.perf_counter() - started

    assert update["criteria_met"] is True
    assert elapsed < 0.13, f"branches appear sequential (took {elapsed:.3f}s for 3x50ms)"


# ---- independent branch failures --------------------------------------------


@pytest.mark.parametrize("failing", ["header", "line_item", "commercial"])
async def test_single_failing_branch_blocks_and_reports_its_issue(monkeypatch: pytest.MonkeyPatch, failing: str):
    outputs = dict(_ALL_PASSING)
    outputs[failing] = _failing()
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is False
    assert update["hitl_required"] is True
    result = update["verification_result"]
    assert result["has_blocking_issues"] is True
    assert [issue["code"] for issue in result["blocking_issues"]] == ["PRICE_VALIDATION_FAILED"]
    assert result[f"{failing}_validation"]["passed"] is False
    # The other two branches still reported independently.
    assert result["checks"].keys() == {"header", "line_item", "commercial"}


async def test_multiple_failing_branches_all_surface(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["header"] = _failing("CUSTOMER_NOT_FOUND")
    outputs["commercial"] = _failing("POLICY_VIOLATION")
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    codes = {issue["code"] for issue in update["verification_result"]["blocking_issues"]}
    assert codes == {"CUSTOMER_NOT_FOUND", "POLICY_VIOLATION"}


async def test_warnings_alone_do_not_block(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["line_item"] = _json(
        passed=True,
        issues=[{"code": "IMPLAUSIBLE_QUANTITY", "message": "qty looks odd", "severity": "warning", "details": {}}],
        details={},
    )
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is True
    assert update["verification_result"]["blocking_issues"] == []
    assert [issue["code"] for issue in update["verification_result"]["warnings"]] == ["IMPLAUSIBLE_QUANTITY"]


async def test_error_severity_overrides_a_claiming_pass(monkeypatch: pytest.MonkeyPatch):
    """A model that says passed=true while reporting an error still blocks."""
    outputs = dict(_ALL_PASSING)
    outputs["commercial"] = _json(
        passed=True,
        issues=[{"code": "POLICY_VIOLATION", "message": "over limit", "severity": "error", "details": {}}],
        details={},
    )
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))
    assert update["criteria_met"] is False


# ---- branch failure isolation ----------------------------------------------


async def test_unparsable_branch_output_is_isolated(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["line_item"] = "I could not produce a report"
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is False
    codes = [issue["code"] for issue in update["verification_result"]["blocking_issues"]]
    assert "VALIDATION_BRANCH_FAILED" in codes


async def test_branch_raising_is_isolated(monkeypatch: pytest.MonkeyPatch):
    agent = VerifierAgent([], [], [], object())

    def _ensure_branch_agent(self, branch: str, _p: str, _t: str):
        if branch == "commercial":
            return _ScriptedAgent(error=RuntimeError("bedrock down"))
        return _ScriptedAgent(_passing(branch, customer_id="cust-1", customer_verified=True))

    monkeypatch.setattr(VerifierAgent, "_ensure_branch_agent", _ensure_branch_agent)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is False
    assert "VALIDATION_BRANCH_FAILED" in [issue["code"] for issue in update["verification_result"]["blocking_issues"]]


async def test_branch_failure_can_be_downgraded_to_warning(monkeypatch: pytest.MonkeyPatch):
    settings = Settings(verification_branch_failure_is_blocking=False)
    agent = VerifierAgent([], [], [], object(), settings=settings)

    def _ensure_branch_agent(self, branch: str, _p: str, _t: str):
        if branch == "commercial":
            return _ScriptedAgent(error=RuntimeError("bedrock down"))
        return _ScriptedAgent(_passing(branch, customer_id="cust-1", customer_verified=True))

    monkeypatch.setattr(VerifierAgent, "_ensure_branch_agent", _ensure_branch_agent)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is True
    assert [issue["code"] for issue in update["verification_result"]["warnings"]] == ["VALIDATION_BRANCH_FAILED"]


# ---- customer ownership -----------------------------------------------------


async def test_header_branch_owns_customer_identity(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["header"] = _passing("header", customer_id="cust-resolved", customer_verified=True)
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["verification_result"]["customer_id"] == "cust-resolved"
    assert update["verification_result"]["customer_verified"] is True


async def test_unresolved_customer_is_not_invented(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["header"] = _json(
        passed=False,
        issues=[{"code": "CUSTOMER_NOT_FOUND", "message": "no match", "severity": "error", "details": {}}],
        details={"customer_id": None, "customer_verified": False},
    )
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    assert update["criteria_met"] is False
    assert update["verification_result"]["customer_id"] is None


async def test_commercial_branch_receives_the_extraction_customer_hint(monkeypatch: pytest.MonkeyPatch):
    agent = _build_agent(monkeypatch, dict(_ALL_PASSING))
    await agent.invoke_agent(dict(_STATE))
    payload = agent._scripted["commercial"].calls[0]["messages"][0].content
    assert "Resolved customer_id: cust-1" in payload


# ---- aggregation unit behaviour --------------------------------------------


def test_aggregate_with_no_branch_results_blocks():
    result = VerifierAgent._aggregate({}, [])
    assert result.has_blocking_issues is True
    assert result.criteria_met is False


def test_aggregate_preserves_flat_compatibility_keys():
    branches = [
        ValidationBranchResult(branch="header", passed=True, details={"customer_id": "c1", "customer_verified": True}),
        ValidationBranchResult(branch="line_item", passed=True, details={"products_verified": 2, "products_total": 3}),
        ValidationBranchResult(branch="commercial", passed=True, details={"policy_applied": ["order"]}),
    ]
    result = VerifierAgent._aggregate({}, branches)
    assert result.customer_id == "c1"
    assert result.products_verified == 2
    assert result.products_total == 3
    assert result.policy_applied == ["order"]
    assert result.issues == []


# ---- guards -----------------------------------------------------------------


async def test_missing_extracted_po_raises():
    agent = VerifierAgent([], [], [], object())
    with pytest.raises(POVerificationError):
        await agent.invoke_agent({})


async def test_hitl_context_carries_blocking_issues_and_totals(monkeypatch: pytest.MonkeyPatch):
    outputs = dict(_ALL_PASSING)
    outputs["header"] = _failing("CUSTOMER_NOT_FOUND")
    agent = _build_agent(monkeypatch, outputs)
    update = await agent.invoke_agent(dict(_STATE))

    context = update["hitl_context"]
    assert context["po_number"] == "PO-1001"
    assert context["customer"] == "Acme Ltd."
    assert context["total_amount"] == 200.0
    assert [issue["code"] for issue in context["blocking_issues"]] == ["CUSTOMER_NOT_FOUND"]

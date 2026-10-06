"""Verifier Agent: the single owner of business-level PO validation.

Three independent branches fan out from the subgraph start and fan in at one
aggregation step:

    START ──▶ header_validation  ──┐
          ──▶ line_item_validation ├──▶ aggregate ──▶ END
          ──▶ commercial_validation┘

Each branch is a scoped ``create_agent`` (own prompt, own tool subset) that
returns the same small JSON contract, so aggregation merges results without
interpreting them. The subgraph is embedded in the PO graph and compiled
without a checkpointer, mirroring ``ExtractionAgent``.

Answering one question only: "is the extracted PO valid for the business
workflow?" It reports issues and never mutates business records.
"""

from __future__ import annotations

import time
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.config.settings import Settings
from app.exceptions.agent_exceptions import POVerificationError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt
from app.models.domain import ValidationBranchResult, VerificationIssue, VerificationResult
from app.orchestrator_service.verification_state import BRANCH_KEYS, VerificationState, init_verification_state

#: Tools each branch may call. Verification has no write access at all.
HEADER_TOOLS = "header_tools"
LINE_ITEM_TOOLS = "line_item_tools"
COMMERCIAL_TOOLS = "commercial_tools"

#: Branch key -> (prompt key, tools attribute).
_BRANCH_SPECS: tuple[tuple[str, str, str], ...] = (
    ("header", "header_validation", HEADER_TOOLS),
    ("line_item", "line_item_validation", LINE_ITEM_TOOLS),
    ("commercial", "commercial_validation", COMMERCIAL_TOOLS),
)


class VerifierAgent(BaseAgent):
    name = "verification"

    def __init__(
        self,
        header_tools: list[Any],
        line_item_tools: list[Any],
        commercial_tools: list[Any],
        chat_model: Any,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self._header_tools = list(header_tools)
        self._line_item_tools = list(line_item_tools)
        self._commercial_tools = list(commercial_tools)
        self._chat_model = chat_model
        self._settings = settings or Settings()
        self._agents: dict[str, Any] = {}
        self._graph: Any = None

    # -- graph ----------------------------------------------------------------

    def _ensure_graph(self) -> Any:
        if self._graph is not None:
            return self._graph
        graph = StateGraph(VerificationState)
        for branch, prompt_key, tools_attr in _BRANCH_SPECS:
            graph.add_node(BRANCH_KEYS[branch], self._branch_node(branch, prompt_key, tools_attr))
        graph.add_node("aggregate", self._node_aggregate)
        graph.add_edge(START, BRANCH_KEYS["header"])
        graph.add_edge(START, BRANCH_KEYS["line_item"])
        graph.add_edge(START, BRANCH_KEYS["commercial"])
        for branch, _prompt_key, _tools_attr in _BRANCH_SPECS:
            graph.add_edge(BRANCH_KEYS[branch], "aggregate")
        graph.add_edge("aggregate", END)
        self._graph = graph.compile()
        return self._graph

    # -- agents ---------------------------------------------------------------

    def _branch_tools(self, tools_attr: str) -> list[Any]:
        return {
            HEADER_TOOLS: self._header_tools,
            LINE_ITEM_TOOLS: self._line_item_tools,
            COMMERCIAL_TOOLS: self._commercial_tools,
        }[tools_attr]

    def _ensure_branch_agent(self, branch: str, prompt_key: str, tools_attr: str) -> Any:
        cached = self._agents.get(branch)
        if cached is not None:
            return cached
        contract = load_prompt("verification.yaml", "output_contract")
        body = load_prompt("verification.yaml", prompt_key).format(
            price_tolerance=self._settings.verification_price_tolerance
        )
        agent = create_agent(
            self._chat_model,
            tools=self._branch_tools(tools_attr),
            system_prompt=SystemMessage(f"{body}\n\n{contract}"),
            middleware=[TracingMiddleware(agent_name=f"{self.name}.{branch}")],
            name=f"{self.name}.{branch}",
        )
        self._agents[branch] = agent
        return agent

    def create_agent(self) -> Any:
        return self._ensure_graph()

    # -- branch nodes ---------------------------------------------------------

    def _branch_payload(self, branch: str, state: VerificationState) -> str:
        extracted = state.get("extracted_po") or {}
        if branch == "header":
            return (
                f"Extracted purchase order:\n{extracted}\n\n"
                "Run the header/PO validation procedure and return the JSON report."
            )
        if branch == "line_item":
            return (
                f"Extracted purchase order line items:\n{extracted.get('line_items') or []}\n\n"
                f"Purchase order total amount: {state.get('po_total_amount') or 0}\n"
                "Run the line item validation procedure and return the JSON report."
            )
        customer_id = state.get("customer_id")
        return (
            f"Purchase order total amount: {state.get('po_total_amount') or 0}\n"
            f"Extracted customer name: {extracted.get('customer')}\n"
            f"Resolved customer_id: {customer_id}\n"
            f"GST number: {extracted.get('gst_no')}\n"
            f"Catalogued line items: {len(extracted.get('line_items') or [])}\n"
            "Run the offer/commercial validation procedure and return the JSON report."
        )

    def _branch_node(self, branch: str, prompt_key: str, tools_attr: str) -> Any:
        async def _run(state: VerificationState) -> dict[str, Any]:
            started = time.perf_counter()
            agent = self._ensure_branch_agent(branch, prompt_key, tools_attr)
            self._logger.info("node_started: verification.%s | run_id=%s", branch, state.get("run_id"))
            try:
                payload = self._branch_payload(branch, state)
                response = await agent.ainvoke({"messages": [SystemMessage(content=payload)]})
                report = self._parse_branch_report(response)
            except Exception as exc:
                self._logger.exception(
                    "node_failed: verification.%s | run_id=%s | duration_ms=%.3f | error=%s: %s",
                    branch,
                    state.get("run_id"),
                    (time.perf_counter() - started) * 1000,
                    type(exc).__name__,
                    exc,
                )
                return {BRANCH_KEYS[branch]: self._branch_failure(branch, exc)}
            result = self._map_branch(branch, report)
            self._logger.info(
                "node_completed: verification.%s | run_id=%s | duration_ms=%.3f | passed=%s | issue_count=%d",
                branch,
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                result.passed,
                len(result.issues),
            )
            return {BRANCH_KEYS[branch]: result.model_dump()}

        return _run

    def _branch_failure(self, branch: str, exc: Exception) -> dict[str, Any]:
        """Isolate a broken branch instead of failing the whole verification.

        With ``verification_branch_failure_is_blocking`` the run continues to
        HITL so a human decides; otherwise the branch is treated as a warning
        and the remaining branches still gate the PO.
        """
        severity = "error" if self._settings.verification_branch_failure_is_blocking else "warning"
        return {
            "branch": branch,
            "passed": not self._settings.verification_branch_failure_is_blocking,
            "issues": [
                {
                    "code": "VALIDATION_BRANCH_FAILED",
                    "message": f"{branch} validation could not be completed: {type(exc).__name__}",
                    "severity": severity,
                    "details": {"branch": branch},
                }
            ],
            "details": {},
        }

    @staticmethod
    def _map_branch(branch: str, report: dict[str, Any]) -> ValidationBranchResult:
        issues = [
            VerificationIssue(
                code=str(issue.get("code", "UNKNOWN")),
                message=str(issue.get("message", "")),
                severity=str(issue.get("severity", "warning")),  # type: ignore[arg-type]
                details=issue.get("details") if isinstance(issue.get("details"), dict) else {},
            )
            for issue in (report.get("issues") or [])
            if isinstance(issue, dict)
        ]
        # The model's `passed` is advisory: an "error" issue always blocks.
        passed = not any(issue.severity == "error" for issue in issues) and bool(report.get("passed", True))
        return ValidationBranchResult(
            branch=branch,
            passed=passed,
            issues=issues,
            details=report.get("details") if isinstance(report.get("details"), dict) else {},
        )

    @staticmethod
    def _parse_branch_report(response: Any) -> dict[str, Any]:
        text = response.get("output") if isinstance(response, dict) else None
        if not isinstance(text, str):
            text = None
        if text is None:
            messages = response.get("messages") if isinstance(response, dict) else None
            for message in reversed(messages or []):
                content = getattr(message, "content", None)
                if isinstance(content, str) and content.startswith("{"):
                    text = content
                    break
        report = first_json_object(text or "")
        if not isinstance(report, dict):
            raise POVerificationError(details={"reason": "verifier branch returned no parseable JSON report"})
        return report

    # -- aggregation ----------------------------------------------------------

    async def _node_aggregate(self, state: VerificationState) -> dict[str, Any]:
        started = time.perf_counter()
        branches = [
            ValidationBranchResult.model_validate(state[key])
            for key in (BRANCH_KEYS["header"], BRANCH_KEYS["line_item"], BRANCH_KEYS["commercial"])
            if state.get(key)
        ]
        result = self._aggregate(state, branches)
        blocking = result.blocking_issues
        warnings = result.warnings
        self._logger.info(
            "node_completed: verification.aggregate | run_id=%s | duration_ms=%.3f | passed=%s | "
            "branch_count=%d | blocking_issue_count=%d | warning_count=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            result.criteria_met,
            len(branches),
            len(blocking),
            len(warnings),
        )
        if not result.criteria_met:
            self._logger.warning(
                "verification_blocked: run_id=%s | blocking_codes=%s | warning_codes=%s",
                state.get("run_id"),
                sorted({issue.code for issue in blocking}),
                sorted({issue.code for issue in warnings}),
            )
        payload = result.model_dump()
        return {
            "verification_result": payload,
            "criteria_met": result.criteria_met,
            "hitl_required": not result.criteria_met,
            "hitl_context": self._hitl_context(state, blocking, warnings) if not result.criteria_met else None,
            "current_step": "verification",
            "status": "RUNNING",
        }

    @staticmethod
    def _aggregate(state: VerificationState, branches: list[ValidationBranchResult]) -> VerificationResult:
        by_branch = {branch.branch: branch for branch in branches}
        issues: list[VerificationIssue] = []
        blocking: list[VerificationIssue] = []
        warnings: list[VerificationIssue] = []
        for branch in branches:
            issues.extend(branch.issues)
            blocking.extend(branch.blocking_issues)
            warnings.extend(branch.warnings)

        header = by_branch.get("header")
        header_details = header.details if header else {}
        line_item = by_branch.get("line_item")
        line_item_details = line_item.details if line_item else {}
        commercial = by_branch.get("commercial")
        commercial_details = commercial.details if commercial else {}

        # The header branch is the authoritative owner of the customer identity.
        customer_id = header_details.get("customer_id")
        customer_verified = bool(header_details.get("customer_verified", bool(customer_id)))

        checks: dict[str, Any] = {}
        for name, branch in by_branch.items():
            checks[name] = {"passed": branch.passed, "issue_count": len(branch.issues)}

        result = VerificationResult(
            # No branch result at all is itself a verification failure, never a silent pass.
            has_blocking_issues=not branches or any(not branch.passed for branch in branches),
            issues=issues,
            blocking_issues=blocking,
            warnings=warnings,
            customer_verified=customer_verified,
            customer_id=str(customer_id) if customer_id else None,
            products_verified=int(line_item_details.get("products_verified") or 0),
            products_total=int(line_item_details.get("products_total") or 0),
            policy_applied=list(commercial_details.get("policy_applied") or []),
            checks=checks,
            header_validation=header,
            line_item_validation=line_item,
            commercial_validation=commercial,
        )
        return result

    @staticmethod
    def _hitl_context(
        state: VerificationState,
        blocking: list[VerificationIssue],
        warnings: list[VerificationIssue],
    ) -> dict[str, Any]:
        extracted = state.get("extracted_po") or {}
        return {
            "run_id": state.get("run_id"),
            "po_number": extracted.get("po_number"),
            "customer": extracted.get("customer"),
            "blocking_issues": [issue.model_dump() for issue in blocking],
            "warnings": [issue.model_dump() for issue in warnings],
            "issues": [issue.model_dump() for issue in [*blocking, *warnings]],
            "total_amount": round(float(state.get("po_total_amount") or 0), 2),
        }

    # -- agent API ------------------------------------------------------------

    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        extracted = state.get("extracted_po")
        if not extracted:
            self._logger.warning("verifier_skipped: run_id=%s | reason=no_extracted_po", state.get("run_id"))
            raise POVerificationError(details={"reason": "no extracted PO in state"})

        line_items = extracted.get("line_items") or []
        self._logger.info(
            "verification_started: run_id=%s | po_total_amount=%s | line_item_count=%s",
            state.get("run_id"),
            state.get("po_total_amount"),
            len(line_items),
        )
        graph = self._ensure_graph()
        result = await graph.ainvoke(init_verification_state(**state), **kwargs)
        return {
            "verification_result": result.get("verification_result"),
            "criteria_met": bool(result.get("criteria_met")),
            "hitl_required": bool(result.get("hitl_required")),
            "hitl_context": result.get("hitl_context"),
            "current_step": "verification",
            "status": "RUNNING",
        }

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_agent(state)

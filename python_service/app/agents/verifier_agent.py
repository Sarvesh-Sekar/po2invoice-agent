"""Verifier Agent: the single owner of business-level PO validation.

Two independent branches fan out from the subgraph start and fan in at one
aggregation step:

    START ──▶ header_field_verifier   ──┐
          ──▶ line_item_field_verifier ──┴──▶ aggregator_node ──▶ END

The commercial verifier is DISABLED (commented out below) for now and is
re-introduced by uncommenting its entries.

Each branch is a scoped ``create_agent`` (own prompt, own tool subset) that
returns the same small JSON contract, so aggregation merges results without
interpreting them. The branch system prompts carry only the procedure; the
evaluation criteria live in ``verification.yaml`` and are loaded at runtime
into the branch's user message, never into the system prompt. The subgraph is
embedded in the PO graph and compiled without a checkpointer, mirroring
``ExtractionAgent``.

Answering one question only: "is the extracted PO valid for the business
workflow?" It reports issues and never mutates business records.
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.config.settings import Settings
from app.exceptions.agent_exceptions import POVerificationError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt, load_prompt_messages
from app.models.domain import ValidationBranchResult, VerificationIssue, VerificationResult
from app.orchestrator_service.verification_state import (
    BRANCH_KEYS,
    NODE_KEYS,
    VerificationState,
    init_verification_state,
)

#: Tools each branch may call. Verification has no write access at all.
HEADER_TOOLS = "header_tools"
LINE_ITEM_TOOLS = "line_item_tools"
COMMERCIAL_TOOLS = "commercial_tools"

#: Branch key -> (prompt key, tools attribute).
_BRANCH_SPECS: tuple[tuple[str, str, str], ...] = (
    ("header", "header_validation", HEADER_TOOLS),
    ("line_item", "line_item_validation", LINE_ITEM_TOOLS),
    # DISABLED: commercial verifier (commented out of the graph for now).
    # ("commercial", "commercial_validation", COMMERCIAL_TOOLS),
)

#: Fan-in node name.
AGGREGATOR_NODE = "aggregator_node"


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
            graph.add_node(NODE_KEYS[branch], self._branch_node(branch, prompt_key, tools_attr))
        graph.add_node(AGGREGATOR_NODE, self._node_aggregate)
        # Both active verifiers fan out from START and run concurrently.
        for branch, _prompt_key, _tools_attr in _BRANCH_SPECS:
            graph.add_edge(START, NODE_KEYS[branch])
            graph.add_edge(NODE_KEYS[branch], AGGREGATOR_NODE)
        # DISABLED: commercial verifier fan-out.
        # graph.add_edge(START, NODE_KEYS["commercial"])
        # graph.add_edge(NODE_KEYS["commercial"], AGGREGATOR_NODE)
        graph.add_edge(AGGREGATOR_NODE, END)
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
        # The system prompt carries only the procedure + output contract.
        # Evaluation criteria are runtime input, rendered into the user
        # message per invocation (see ``_branch_user_prompt``).
        prompt = load_prompt_messages("verification.yaml", prompt_key)
        contract = load_prompt("verification.yaml", "output_contract")
        body = str(prompt.get("system_prompt") or "").strip()
        middleware: list[Any] = [TracingMiddleware(agent_name=f"{self.name}.{branch}")]
        if branch == "header":
            # The prompt says "call find_customer once", but a weaker model will
            # not self-terminate its tool loop. Enforce the limit in code: the
            # first call runs, any retry is blocked with a ToolMessage telling
            # the model to stop calling, and it proceeds to the final report.
            middleware.append(
                ToolCallLimitMiddleware(
                    tool_name="find_customer",
                    run_limit=1,
                    exit_behavior="continue",
                )
            )

        print("agent:",branch,'tools:',self._branch_tools(tools_attr))



        print(self.name , branch ,'branch')
        agent = create_agent(
            self._chat_model,
            tools=self._branch_tools(tools_attr),
            system_prompt=SystemMessage(f"{body}\n\n{contract}"),
            middleware=middleware,
            name=f"{self.name}.{branch}",
        )
        self._agents[branch] = agent
        return agent

    def create_agent(self) -> Any:
        return self._ensure_graph()

    # -- branch nodes ---------------------------------------------------------

    @staticmethod
    def _criteria(prompt_key: str) -> dict[str, Any]:
        """Load evaluation criteria from ``verification.yaml`` at runtime."""
        return load_prompt_messages("verification.yaml", prompt_key)

    @staticmethod
    def _dumps(value: Any) -> str:
        return json.dumps(value, indent=2, default=str)

    def _branch_user_prompt(self, branch: str, prompt_key: str, state: VerificationState) -> str:
        """Render the branch's runtime user message from its yaml template.

        Evaluation criteria are read from ``verification.yaml`` here and
        substituted into the user message only; they never reach the system
        prompt.
        """
        template = str(load_prompt_messages("verification.yaml", prompt_key).get("user_prompt") or "")
        extracted = state.get("extracted_po") or {}
        if branch == "header":

            replacements = {
                "extracted_header_fields": self._dumps(state.get("extracted_header_fields") or extracted),
                "evaluation_criteria_header": self._dumps(self._criteria("evaluation_criteria_header")),
                "header_document_evidence": str(state.get("header_section") or ""),
                "customer_context": self._dumps(
                    {
                        "customer_id": state.get("customer_id"),
                        "customer": extracted.get("customer"),
                        "gst_no": extracted.get("gst_no"),
                    }
                ),
            }

            print('replacements',replacements)
        elif branch == "line_item":
            replacements = {
                "extracted_line_items": self._dumps(extracted.get("line_items") or []),
                "evaluation_criteria_line_item": self._dumps(self._criteria("evaluation_criteria_line_item")),
                "line_item_document_evidence": str(state.get("line_item_section") or ""),
            }
        # DISABLED: commercial verifier runtime payload.
        # else:
        #     customer_id = state.get("customer_id")
        #     replacements = {
        #         "po_total_amount": str(state.get("po_total_amount") or 0),
        #         "customer": str(extracted.get("customer")),
        #         "customer_id": str(customer_id),
        #         "gst_no": str(extracted.get("gst_no")),
        #     }
        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace("{{" + placeholder + "}}", value)
        return rendered

    def _branch_node(self, branch: str, prompt_key: str, tools_attr: str) -> Any:
        async def _run(state: VerificationState) -> dict[str, Any]:
            started = time.perf_counter()
            agent = self._ensure_branch_agent(branch, prompt_key, tools_attr)
            self._logger.info("node_started: verification.%s | run_id=%s", branch, state.get("run_id"))
            try:
                payload = self._branch_user_prompt(branch, prompt_key, state)
                response = await agent.ainvoke({"messages": [HumanMessage(content=payload)]})
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
            for key in (
                BRANCH_KEYS["header"],
                BRANCH_KEYS["line_item"],
                # DISABLED: commercial verifier; its state key stays None.
                # BRANCH_KEYS["commercial"],
            )
            if state.get(key)
        ]
        result = self._aggregate(state, branches)
        blocking = result.blocking_issues
        warnings = result.warnings
        self._logger.info(
            "node_completed: verification.%s | run_id=%s | duration_ms=%.3f | passed=%s | "
            "branch_count=%d | blocking_issue_count=%d | warning_count=%d",
            AGGREGATOR_NODE,
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
            # "customer_id" : state.get('customer_id')
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

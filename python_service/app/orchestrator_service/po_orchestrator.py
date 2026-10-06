"""Purchase Order orchestrator: builds and compiles the PO LangGraph.

Flow: extract -> verify -> (PASS: sales | FAIL: hitl -> approve/reject/edit)
A human EDIT returns to the verifier with the corrected structure; the source
document is never re-extracted.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.base_agent import BaseAgent
from app.config.logging import get_logger
from app.exceptions.agent_exceptions import (
    CustomerIdentificationError,
    DocumentProcessingError,
    ExtractionPersistenceError,
    ExtractionValidationError,
    RecoveryExhaustedError,
)
from app.orchestrator_service.base_orchestrator import BaseOrchestrator
from app.orchestrator_service.graph import POWorkflowState

logger = get_logger(__name__)

MAX_EDIT_ROUNDS = 3

_EDITABLE_FIELDS = {
    "po_number",
    "customer",
    "gst_no",
    "ship_to",
    "address_1",
    "address_2",
    "city",
    "state",
    "country",
    "zip",
}

_EXTRACTION_ERRORS: dict[str, type[Exception]] = {
    "DOCUMENT_PROCESSING_FAILED": DocumentProcessingError,
    "CUSTOMER_IDENTIFICATION_FAILED": CustomerIdentificationError,
    "EXTRACTION_VALIDATION_FAILED": ExtractionValidationError,
    "RECOVERY_EXHAUSTED": RecoveryExhaustedError,
    "EXTRACTION_PERSISTENCE_FAILED": ExtractionPersistenceError,
    "EXTRACTION_WORKFLOW_FAILED": ExtractionValidationError,
}

#: Extraction error codes that carry no dedicated exception class.
_DEFAULT_EXTRACTION_ERROR: type[Exception] = ExtractionValidationError


class POOrchestrator(BaseOrchestrator):
    name = "purchase_order"

    def __init__(
        self,
        extraction_agent: BaseAgent,
        verifier_agent: BaseAgent,
        sales_agent: BaseAgent,
        checkpointer: Any,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(checkpointer, logger=logger)
        self.extraction_agent = extraction_agent
        self.verifier_agent = verifier_agent
        self.sales_agent = sales_agent

    # ---- pure node functions ----

    async def _extraction_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Runs the extraction subgraph as the parent graph's extraction node.

        A failed extraction is a terminal outcome for the run, not a raised
        exception: the workflow ends with ``status=FAILED`` and a populated
        ``workflow_error`` so the API reports a completed-with-failure run
        instead of an opaque 502.
        """
        started = time.perf_counter()
        logger.info("node_started: extraction | run_id=%s | thread_id=%s", state.get("run_id"), state.get("thread_id"))
        update = await self.extraction_agent.execute(state)
        if update.get("status") == "FAILED":
            error_code = update.get("extraction_error_code") or "EXTRACTION_WORKFLOW_FAILED"
            error_type = _EXTRACTION_ERRORS.get(error_code, _DEFAULT_EXTRACTION_ERROR)
            error = error_type(details={"reason": error_code})
            logger.error(
                "node_failed: extraction | run_id=%s | duration_ms=%.3f | step=%s | error_code=%s | error=%s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                update.get("current_step"),
                error_code,
                error.message,
            )
            return {
                **update,
                "workflow_error": {
                    "code": getattr(error, "code", error_code),
                    "message": getattr(error, "message", str(error)),
                },
                "current_step": update.get("current_step") or "extraction",
                "status": "FAILED",
            }
        logger.info(
            "node_completed: extraction | run_id=%s | duration_ms=%.3f | step=%s | status=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            update.get("current_step"),
            update.get("status"),
        )
        return update

    def _route_after_extraction(self, state: dict[str, Any]) -> str:
        """Never send a failed extraction to business verification."""
        if state.get("status") == "FAILED" or not state.get("extracted_po"):
            logger.info("route: extraction -> end | run_id=%s | reason=extraction_failed", state.get("run_id"))
            return "failed"
        logger.info("route: extraction -> verification | run_id=%s", state.get("run_id"))
        return "verify"

    def _route_from_verification(self, state: dict[str, Any]) -> str:
        """Route straight off the verifier decision; it owns the outcome."""
        verification = state.get("verification_result") or {}
        criteria_met = bool(state.get("criteria_met", verification.get("has_blocking_issues", True) is False))
        route = "sales" if criteria_met else "hitl"
        blocking_issues = verification.get("blocking_issues") or []
        logger.info(
            "route: verification -> %s | run_id=%s | criteria_met=%s | blocking_issue_count=%d",
            route,
            state.get("run_id"),
            criteria_met,
            len(blocking_issues),
        )
        return route

    async def _hitl_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """Pauses the graph until a human decision is submitted."""
        logger.info(
            "node_started: hitl | run_id=%s | thread_id=%s | question=purchase_order_review",
            state.get("run_id"),
            state.get("thread_id"),
        )
        decision = interrupt(
            {
                "question": "purchase_order_review",
                "run_id": state.get("run_id"),
                "context": state.get("hitl_context") or {},
            }
        )
        logger.info(
            "node_completed: hitl | run_id=%s | decision=%s | changed_field_count=%d",
            state.get("run_id"),
            (decision or {}).get("decision") if isinstance(decision, dict) else None,
            len((decision or {}).get("changes") or {}) if isinstance(decision, dict) else 0,
        )
        return {
            "hitl_decision": decision,
            "current_step": "hitl",
            "status": "WAITING_FOR_HUMAN",
        }

    async def _apply_edits(self, state: dict[str, Any]) -> dict[str, Any]:
        """Apply human edits to the extracted PO and re-verify."""
        started = time.perf_counter()
        decision = state.get("hitl_decision") or {}
        changes = decision.get("changes") or {}
        extracted = dict(state.get("extracted_po") or {})
        applied: list[str] = []
        rejected: list[str] = []
        for key, value in changes.items():
            if key in _EDITABLE_FIELDS:
                extracted[key] = value
                applied.append(key)
            else:
                rejected.append(key)
        if isinstance(changes.get("line_items"), list):
            extracted["line_items"] = changes["line_items"]
            applied.append("line_items")

        total = round(
            sum(
                float(item.get("unit_price", 0)) * float(item.get("quantity", 0))
                for item in (extracted.get("line_items") or [])
            ),
            2,
        )
        edit_rounds = int(state.get("edit_rounds") or 0) + 1
        if rejected:
            logger.warning(
                "node_completed: apply_edits | run_id=%s | duration_ms=%.3f | applied=%s | ignored_fields=%s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                applied,
                rejected,
            )
        else:
            logger.info(
                "node_completed: apply_edits | run_id=%s | duration_ms=%.3f | edit_round=%s/%s | applied=%s | total=%s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                edit_rounds,
                MAX_EDIT_ROUNDS,
                applied,
                total,
            )
        return {
            "extracted_po": extracted,
            "po_total_amount": total,
            "edits_applied": True,
            "edit_rounds": edit_rounds,
            "criteria_met": False,
            "hitl_required": False,
            "verification_result": None,
            "current_step": "apply_edits",
            "status": "RUNNING",
        }

    def _route_from_hitl(self, state: dict[str, Any]) -> str:
        decision = (state.get("hitl_decision") or {}).get("decision")
        if decision == "EDIT":
            if int(state.get("edit_rounds") or 0) >= MAX_EDIT_ROUNDS:
                route = "approve"
            else:
                route = "edit"
        elif decision == "REJECT":
            route = "reject"
        else:
            route = "approve"
        logger.info(
            "route: hitl -> %s | run_id=%s | decision=%s | edit_rounds=%s/%s",
            route,
            state.get("run_id"),
            decision,
            state.get("edit_rounds") or 0,
            MAX_EDIT_ROUNDS,
        )
        return route

    # ---- graph construction ----

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(POWorkflowState)

        graph.add_node("extraction", self._extraction_node)
        graph.add_node("verification", self.verifier_agent.run)
        graph.add_node("hitl", self._hitl_node)
        graph.add_node("apply_edits", self._apply_edits)
        graph.add_node("sales", self.sales_agent.run)

        graph.add_edge(START, "extraction")
        graph.add_conditional_edges(
            "extraction",
            self._route_after_extraction,
            {"verify": "verification", "failed": END},
        )
        graph.add_conditional_edges(
            "verification",
            self._route_from_verification,
            {"sales": "sales", "hitl": "hitl"},
        )
        graph.add_conditional_edges(
            "hitl",
            self._route_from_hitl,
            {
                "approve": "sales",
                "reject": END,
                "edit": "apply_edits",
            },
        )
        # A corrected value needs re-verification, never re-extraction.
        graph.add_edge("apply_edits", "verification")
        graph.add_edge("sales", END)
        return graph

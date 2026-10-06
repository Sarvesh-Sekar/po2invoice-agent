"""Extraction Agent: LangGraph subgraph for field extraction + validation.

Implements BaseAgent.create_agent/invoke_agent. The subgraph runs through
document processing → customer identification → load memories → semantic
extraction → candidate evaluation → quality gate → persistence → episodic
memory update, with bounded recovery when validation fails.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.clients.base import BaseBedrockClient, BaseS3Client
from app.config.logging import get_logger
from app.config.settings import Settings
from app.exceptions.client_exceptions import BedrockError
from app.helpers.yaml_loader import load_memory, load_prompt
from app.orchestrator_service.extraction_state import ExtractionState, init_extraction_state
from app.tools.extraction_tools import build_extraction_tools

logger = get_logger(__name__)

# Bedrock retryable exceptions
_RETRYABLE_BEDROCK_CODES = (
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "ServiceUnavailable",
    "ModelTimeoutException",
    "InternalServerException",
    "RequestLimitExceeded",
    "TooManyRequestsException",
)


def _is_retryable_bedrock_exception(exc: BaseException) -> bool:
    if isinstance(exc, BedrockError):
        details = exc.details or {}
        code = details.get("code") or details.get("errorCode") or details.get("ErrorCode")
        if code and str(code) in _RETRYABLE_BEDROCK_CODES:
            return True
    try:
        from botocore.exceptions import ClientError

        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {}) if hasattr(exc, "response") else {}
            code = error.get("Code") or error.get("code")
            if code and str(code) in _RETRYABLE_BEDROCK_CODES:
                return True
    except Exception:
        pass
    return False

# Mapping from canonical FIELD_DEFINITIONS names → ExtractedPO keys
_EXT_HEADER_MAP: dict[str, str] = {
    "po_number": "po_number",
    "customer": "customer",
    "gst_no": "gst_no",
    "ship_to": "ship_to",
    "address_1": "address_1",
    "address_2": "address_2",
    "city": "city",
    "state": "state",
    "country": "country",
    "zip": "zip",
    "total_amount": "total_amount",
}

_EXT_LINE_ITEM_FIELDS = {"product_name", "sku", "quantity", "unit_price"}

_LINE_ITEM_FIELD_NAMES: list[str] = ["product_name", "sku", "quantity", "unit_price", "total_price"]

_ROW_GROUP_FIELD = "__LINE_ITEMS__"

_FAILURE_ERROR_CODES: dict[str, str] = {
    "document_processing": "DOCUMENT_PROCESSING_FAILED",
    "customer_identification": "CUSTOMER_IDENTIFICATION_FAILED",
    "quality_gate_exhausted": "EXTRACTION_VALIDATION_FAILED",
    "persist": "EXTRACTION_PERSISTENCE_FAILED",
}


def _first_json_object(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, TypeError):
                    return None
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).replace(",", "").replace("Rs", "").replace("$", "").strip() or default)
    except (TypeError, ValueError):
        return default


def _parse_candidate_response(text: str) -> dict:
    parsed = _first_json_object(text) or {}
    field_name = parsed.get("field_name")
    candidates_raw = parsed.get("candidates") or []
    candidates = []
    for c in candidates_raw:
        if not isinstance(c, dict):
            continue
        candidates.append(
            {
                "value": str(c.get("value", "")),
                "source": c.get("source") or "semantic",
                "source_label": c.get("source_label"),
                "location": c.get("location"),
                "surrounding_text": c.get("surrounding_text"),
            }
        )
    return {"field_name": field_name, "candidates": candidates}


def _parse_evaluation_response(text: str) -> dict:
    parsed = _first_json_object(text) or {}
    return {
        "field_name": parsed.get("field_name"),
        "score": float(parsed.get("score", 0)),
        "accepted": bool(parsed.get("accepted", False)),
        "reasons": parsed.get("reasons") or [],
    }


def _reconstruct_extracted_po(
    header_fields: list[dict[str, Any]],
    line_item_fields: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build an ExtractedPO-shaped dict for the parent graph / verifier."""
    header: dict[str, Any] = {key: None for key in _EXT_HEADER_MAP.values()}
    header["line_items"] = []
    field_by_name = {f["field_name"]: f.get("value") for f in header_fields}
    for field_name, target_key in _EXT_HEADER_MAP.items():
        header[target_key] = field_by_name.get(field_name)
    for row_fields in line_item_fields:
        by_name = {f["field_name"]: f.get("value") for f in row_fields}
        header["line_items"].append(
            {
                "product_name": by_name.get("product_name"),
                "sku": by_name.get("sku"),
                "quantity": int(float(by_name.get("quantity", 0) or 0)),
                "unit_price": float(by_name.get("unit_price", 0) or 0),
            }
        )
    return header


def _line_items_total(extracted_po: dict[str, Any]) -> float:
    total = 0.0
    for item in extracted_po.get("line_items") or []:
        total += float(item.get("unit_price", 0) or 0) * float(item.get("quantity", 0) or 0)
    return round(total, 2)


def _split_rows_from_text(line_items_section: str) -> list[str]:
    if not line_items_section:
        return []
    rows = [row.strip() for row in line_items_section.splitlines() if row.strip()]
    return rows


def _error_reason(exc: Exception) -> str:
    """Render a failure reason, preferring structured ``details`` over the bare message.

    ``BaseAppError.__str__`` only returns its message, so the underlying reason
    (e.g. the AWS ValidationException text) is dropped unless ``details`` is read.
    """
    parts: list[str] = []
    for key, value in (getattr(exc, "details", None) or {}).items():
        parts.append(f"{key}={value}")
    reason = "; ".join(parts) or str(exc)
    return reason[:400]


class ExtractionAgent(BaseAgent):
    name = "extraction"

    def __init__(
        self,
        bedrock_client: BaseBedrockClient | None,
        s3_client: BaseS3Client | None = None,
        chat_model: Any | None = None,
        settings: Settings | None = None,
        *,
        customer_repository: Any | None = None,
        field_definition_repository: Any | None = None,
        po_header_field_repository: Any | None = None,
        po_line_item_repository: Any | None = None,
        product_repository: Any | None = None,
        episodic_memory_repository: Any | None = None,
    ) -> None:
        super().__init__()
        if bedrock_client is None:
            raise TypeError("ExtractionAgent requires a bedrock_client")
        self._bedrock = bedrock_client
        self._s3 = s3_client
        self._chat_model = chat_model
        self._settings = settings
        self._repo = {
            "customer": customer_repository,
            "field_definition": field_definition_repository,
            "po_header_field": po_header_field_repository,
            "po_line_item": po_line_item_repository,
            "product": product_repository,
            "episodic_memory": episodic_memory_repository,
        }
        self._tools: list[Any] | None = None
        self._tool_map: dict[str, Any] = {}
        self._graph: Any | None = None
        self._candidate_agent: Any | None = None
        self._validation_agent: Any | None = None

    # -- helpers ---------------------------------------------------------------

    def _max_retries(self) -> int:
        if self._settings is None:
            return 3
        return int(getattr(self._settings, "extraction_max_retries", 3))

    def _min_score(self) -> float:
        if self._settings is None:
            return 0.75
        return float(getattr(self._settings, "extraction_min_evidence_score", 0.75))

    def _min_sources(self) -> int:
        if self._settings is None:
            return 2
        return int(getattr(self._settings, "extraction_min_evidence_sources", 2))

    def _min_separation(self) -> float:
        if self._settings is None:
            return 0.15
        return float(getattr(self._settings, "extraction_candidate_separation", 0.15))

    def _validated_confidence(self) -> float:
        if self._settings is None:
            return 0.8
        return float(getattr(self._settings, "extraction_validated_confidence", 0.8))

    def _eval_concurrency(self) -> int:
        if self._settings is None:
            return 2
        return int(getattr(self._settings, "extraction_evaluation_concurrency", 2))

    def _eval_batch_size(self) -> int:
        if self._settings is None:
            return 2
        return int(getattr(self._settings, "extraction_evaluation_batch_size", 2))

    def _max_candidates_per_field(self) -> int:
        if self._settings is None:
            return 3
        return int(getattr(self._settings, "extraction_max_candidates_per_field", 3))

    def _max_evaluations_total(self) -> int:
        if self._settings is None:
            return 24
        return int(getattr(self._settings, "extraction_max_evaluations_total", 24))

    def _eval_max_retries(self) -> int:
        if self._settings is None:
            return 3
        return int(getattr(self._settings, "extraction_evaluation_max_retries", 3))

    def _eval_backoff_base(self) -> float:
        if self._settings is None:
            return 0.5
        return float(getattr(self._settings, "extraction_evaluation_backoff_base", 0.5))

    def _eval_backoff_mult(self) -> float:
        if self._settings is None:
            return 1.5
        return float(getattr(self._settings, "extraction_evaluation_backoff_mult", 1.5))

    def _eval_backoff_max(self) -> float:
        if self._settings is None:
            return 8.0
        return float(getattr(self._settings, "extraction_evaluation_backoff_max", 8.0))

    def _no_progress_threshold_retries(self) -> int:
        if self._settings is None:
            return 1
        return int(getattr(self._settings, "extraction_no_progress_threshold_retries", 1))

    async def _ensure_tools(self) -> list[Any]:
        if self._tools is not None:
            return self._tools
        missing = [k for k, v in self._repo.items() if v is None]
        if missing:
            raise RuntimeError(f"Missing repositories for extraction tools: {missing}")
        self._tools = build_extraction_tools(
            self._repo["customer"],
            self._repo["field_definition"],
            self._repo["po_header_field"],
            self._repo["po_line_item"],
            self._repo["product"],
            self._repo["episodic_memory"],
        )
        self._tool_map = {tool.name: tool for tool in self._tools}
        return self._tools

    def _build_inner_agent(self, system_prompt: str, agent_key: str) -> Any:
        if self._chat_model is None:
            return None
        # No tools are bound: the candidate/validation agents are single-shot text -> JSON
        # generators. Binding the repository tools made the model answer with tool calls
        # instead of the requested candidate/verdict JSON.
        bound = create_agent(
            self._chat_model,
            tools=[],
            system_prompt=system_prompt,
            middleware=[TracingMiddleware(agent_name=self.name)],
            name=agent_key,
        )
        return bound

    def _ensure_graph(self) -> Any:
        if self._graph is not None:
            return self._graph

        candidate_prompt = SystemMessage(load_prompt("extraction.yaml", "candidate_generation"))
        validation_prompt = SystemMessage(load_prompt("extraction.yaml", "candidate_evaluation"))

        self._candidate_agent = self._build_inner_agent(candidate_prompt, "candidate_generator")
        self._validation_agent = self._build_inner_agent(validation_prompt, "validation_agent")

        graph = StateGraph(ExtractionState)
        graph.add_node("document_processing", self._node_document_processing)
        graph.add_node("customer_identification", self._node_customer_identification)
        graph.add_node("load_memories", self._node_load_memories)
        graph.add_node("field_extraction", self._node_field_extraction)
        graph.add_node("candidate_generation", self._node_candidate_generation)
        graph.add_node("candidate_evaluation", self._node_candidate_evaluation)
        graph.add_node("evidence_aggregation", self._node_evidence_aggregation)
        graph.add_node("quality_gate", self._node_quality_gate)
        graph.add_node("recovery", self._node_recovery)
        graph.add_node("persist", self._node_persist)
        graph.add_node("update_episodic_memory", self._node_update_episodic_memory)

        graph.add_edge(START, "document_processing")
        graph.add_conditional_edges(
            "document_processing",
            self._after_document_processing,
            {
                "ok": "customer_identification",
                "failed": END,
            },
        )
        graph.add_conditional_edges(
            "customer_identification",
            self._after_customer_identification,
            {
                "ok": "load_memories",
                "failed": END,
            },
        )
        graph.add_edge("load_memories", "field_extraction")
        graph.add_edge("field_extraction", "candidate_generation")
        graph.add_edge("candidate_generation", "candidate_evaluation")
        graph.add_edge("candidate_evaluation", "evidence_aggregation")
        graph.add_edge("evidence_aggregation", "quality_gate")
        graph.add_conditional_edges(
            "quality_gate",
            self._after_quality_gate,
            {
                "ok": "persist",
                "retry": "recovery",
            },
        )
        graph.add_conditional_edges(
            "recovery",
            self._after_recovery,
            {
                "ok": "candidate_generation",
                "failed": END,
            },
        )
        graph.add_edge("persist", "update_episodic_memory")
        graph.add_edge("update_episodic_memory", END)
        self._graph = graph.compile()
        logger.info(
            "extraction_graph_built: nodes=%s",
            [
                "document_processing",
                "customer_identification",
                "load_memories",
                "field_extraction",
                "candidate_generation",
                "candidate_evaluation",
                "evidence_aggregation",
                "quality_gate",
                "recovery",
                "persist",
                "update_episodic_memory",
            ],
        )
        return self._graph

    # -- agent API -------------------------------------------------------------

    def create_agent(self) -> Any:
        return self._ensure_graph()

    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        await self._ensure_tools()
        merged: ExtractionState = init_extraction_state(**state)
        graph = self._ensure_graph()
        result = await graph.ainvoke(merged, **{**kwargs, "recursion_limit": 50})
        update = self._map_update(result)
        if "__interrupt__" in result:
            update["__interrupt__"] = result["__interrupt__"]
            update["status"] = "RUNNING"
        return update

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_agent(state)

    # -- mapping ---------------------------------------------------------------

    @staticmethod
    def _map_update(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "extraction_result": result.get("extraction_result", {}),
            "extracted_header_fields": result.get("extracted_header_fields", []),
            "extracted_line_item_fields": result.get("extracted_line_item_fields", []),
            "extracted_po": result.get("extracted_po"),
            "po_total_amount": result.get("po_total_amount"),
            "customer_id": result.get("customer_id"),
            "current_step": result.get("current_step", "extraction"),
            "status": result.get("status", "FAILED"),
            "extraction_error": result.get("extraction_error"),
            "extraction_error_code": result.get("extraction_error_code"),
            "file_bytes": None,
        }

    # -- conditional edges -----------------------------------------------------

    @staticmethod
    def _after_document_processing(state: ExtractionState) -> Literal["ok", "failed"]:
        return "ok" if state.get("status") == "RUNNING" else "failed"

    @staticmethod
    def _after_customer_identification(state: ExtractionState) -> Literal["ok", "failed"]:
        status = state.get("status")
        logger.info(
            "route: customer_identification -> %s | run_id=%s",
            "ok" if status == "RUNNING" else "failed",
            state.get("run_id"),
        )
        return "ok" if status == "RUNNING" else "failed"

    def _after_quality_gate(self, state: ExtractionState) -> Literal["ok", "retry"]:
        if state.get("extraction_result", {}).get("passed"):
            return "ok"
        return "retry"

    def _after_recovery(self, state: ExtractionState) -> Literal["ok", "failed"]:
        retry = int(state.get("retry_count", 0))
        if retry <= self._max_retries():
            return "ok"
        return "failed"

    # -- node implementations --------------------------------------------------

    async def _node_document_processing(self, state: ExtractionState) -> dict[str, Any]:
        document = state.get("document") or state.get("file_bytes")
        started = time.perf_counter()
        logger.info(
            "node_started: document_processing | run_id=%s | mime_type=%s | has_document=%s",
            state.get("run_id"),
            state.get("mime_type"),
            bool(document),
        )
        # if not document and self._s3 and state.get("source_file_url"):
        #     from urllib.parse import urlparse

        #     path = urlparse(str(state["source_file_url"])).path
        #     if path:
        #         document = await self._s3.download(path.lstrip("/"))

        if not document:
            logger.error(
                "node_failed: document_processing | run_id=%s | duration_ms=%.3f | reason=no_document",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
            )
            return {
                "status": "FAILED",
                "current_step": "document_processing",
                "extraction_error": "No document available for extraction",
                "extraction_error_code": "DOCUMENT_PROCESSING_FAILED",
            }
        mime_type = state.get("mime_type") or "application/pdf"
        prompt = load_prompt("extraction.yaml", "extraction")
        try:
            raw = await self._bedrock.extract_document(document, prompt, content_type=mime_type)
        except Exception as exc:
            logger.exception(
                "node_failed: document_processing | run_id=%s | duration_ms=%.3f | error=%s: %s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            return {
                "status": "FAILED",
                "current_step": "document_processing",
                "extraction_error": f"Document extraction failed: {_error_reason(exc)}",
                "extraction_error_code": "DOCUMENT_PROCESSING_FAILED",
            }
        document_text = raw.get("fullText") or raw.get("headerSection") or json.dumps(raw, default=str)
        document_lines = raw.get("headerLines") or []
        document_lines.extend(raw.get("lineItemLines") or [])
        logger.info(
            "node_completed: document_processing | run_id=%s | duration_ms=%.3f | line_count=%d | text_chars=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(document_lines),
            len(document_text),
        )
        return {
            "document_text": document_text,
            "document_lines": document_lines,
            "current_step": "document_processing",
            "file_bytes": None,
        }

    async def _node_customer_identification(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        logger.info("node_started: customer_identification | run_id=%s", state.get("run_id"))
        document_text = state.get("document_text") or ""
        tools = list(self._tools or [])
        result = await self._run_candidate_agent(tools, document_text, "customer")
        gst_result = await self._run_candidate_agent(tools, document_text, "gst_no")
        candidate_value = self._best_value(result)
        gst_value = self._best_value(gst_result)
        candidates = list(state.get("candidates") or [])
        candidates.extend(
            [
                {"field_name": "customer", "candidates": result.get("candidates", [])},
                {"field_name": "gst_no", "candidates": gst_result.get("candidates", [])},
            ]
        )
        lookup = self._tool_map["lookup_customer"]
        lookup_result: dict = await lookup.ainvoke({"name": candidate_value})
        if not lookup_result.get("found"):
            logger.warning(
                "node_paused: customer_identification | run_id=%s | duration_ms=%.3f | reason=customer_not_found",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
            )
            return await self._resolve_customer_not_found(state, candidate_value, gst_value, candidates)
        customer = lookup_result.get("customer") or {}
        logger.info(
            "node_completed: customer_identification | run_id=%s | duration_ms=%.3f | customer_id=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            customer.get("customer_id"),
        )
        return {
            "customer_id": customer.get("customer_id"),
            "customer_name": customer.get("name"),
            "customer_gst_no": gst_value,
            "current_step": "customer_identification",
            "candidates": candidates,
        }

    async def _resolve_customer_not_found(
        self,
        state: ExtractionState,
        candidate_value: str | None,
        gst_value: str | None,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Ask a human to approve creating a new customer when the lookup misses.

        Pauses the graph with an interrupt; the resume decision carries the
        human's choice (approve / edit args / reject).
        """
        if not candidate_value:
            return {
                "status": "FAILED",
                "current_step": "customer_identification",
                "extraction_error": "Customer not identified (no name found in the document)",
                "extraction_error_code": "CUSTOMER_IDENTIFICATION_FAILED",
                "candidates": candidates,
            }
        decision = interrupt(
            {
                "question": "create_customer",
                "run_id": state.get("run_id"),
                "context": {
                    "message": f"Customer '{candidate_value}' not found. Create a new customer?",
                    "customer_name": candidate_value,
                    "customer_gst_no": gst_value,
                    "customer_code": None,
                    "candidates": candidates,
                },
            }
        )
        resume = decision if isinstance(decision, dict) else {}
        action = str(resume.get("decision") or "APPROVE").upper()
        if action == "REJECT":
            return {
                "status": "FAILED",
                "current_step": "customer_identification",
                "extraction_error": f"Customer creation rejected by user (name={candidate_value})",
                "extraction_error_code": "CUSTOMER_IDENTIFICATION_FAILED",
                "candidates": candidates,
            }
        changes = resume.get("changes") or {}
        name = str(changes.get("customer_name") or changes.get("name") or candidate_value or "").strip()
        customer_code = changes.get("customer_code")
        logger.info(
            "hitl_decision_received: create_customer | run_id=%s | decision=%s | has_customer_code=%s",
            state.get("run_id"),
            action,
            bool(customer_code),
        )
        if not name:
            return {
                "status": "FAILED",
                "current_step": "customer_identification",
                "extraction_error": "Customer creation failed: no customer name after edit",
                "extraction_error_code": "CUSTOMER_IDENTIFICATION_FAILED",
                "candidates": candidates,
            }
        create = self._tool_map["create_customer"]
        created_result: dict = await create.ainvoke({"name": name, "customer_code": customer_code})
        customer = created_result.get("customer") or {}
        if not created_result.get("created") or not customer:
            reason = created_result.get("reason") or "could not create customer"
            return {
                "status": "FAILED",
                "current_step": "customer_identification",
                "extraction_error": f"Customer creation failed: {reason}",
                "extraction_error_code": "CUSTOMER_IDENTIFICATION_FAILED",
                "candidates": candidates,
            }
        return {
            "customer_id": customer.get("customer_id"),
            "customer_name": customer.get("name"),
            "customer_gst_no": gst_value,
            "current_step": "customer_identification",
            "candidates": candidates,
        }

    @staticmethod
    def _static_memory_map(field_definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Build the procedural/semantic baseline from memory.yaml for catalogue fields."""
        data = load_memory()
        procedural: dict = data.get("procedural") or {}
        semantic: dict = data.get("semantic") or {}
        names = {fd["field_name"] for fd in field_definitions}
        result: dict[str, dict[str, Any]] = {}
        for field_name in names:
            steps = procedural.get(field_name)
            if isinstance(steps, str):
                steps = [steps]
            if not isinstance(steps, list):
                steps = []
            steps = [str(step) for step in steps if str(step).strip()]
            labels = (semantic.get(field_name) or {}).get("labels") or []
            if not isinstance(labels, list):
                labels = []
            result[field_name] = {
                "steps": steps,
                "labels": ", ".join(str(label) for label in labels),
            }
        return result

    async def _node_load_memories(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        logger.info("node_started: load_memories | run_id=%s", state.get("run_id"))
        lookup_field_defs = self._tool_map["lookup_field_definitions"]
        get_memory = self._tool_map["get_episodic_memory"]
        defs_result: dict = await lookup_field_defs.ainvoke({"scope": "all"})
        field_definitions = defs_result.get("fields") or []
        static = self._static_memory_map(field_definitions)
        memories: list[dict] = []
        episodic_hits = 0
        customer_id = state.get("customer_id")
        for field_def in field_definitions:
            field_name = field_def["field_name"]
            baseline = static.get(field_name) or {"steps": [], "labels": ""}
            instruction = list(baseline["steps"])
            location_hint = baseline["labels"]
            if customer_id:
                try:
                    mem = await get_memory.ainvoke({"customer_id": customer_id, "field_name": field_name})
                    if mem.get("found"):
                        episodic = mem.get("memory", {}) or {}
                        episodic_instruction = str(episodic.get("instruction") or "").strip()
                        if episodic_instruction:
                            instruction.append(episodic_instruction)
                            episodic_hits += 1
                        episodic_hint = str(episodic.get("location_hint") or "").strip()
                        if episodic_hint:
                            location_hint = episodic_hint
                except Exception:
                    pass  # keep the static baseline on episodic lookup failure
            memories.append(
                {
                    "field": field_name,
                    "memory": {
                        "instruction": "\n".join(instruction) or "Identify the value from the document text.",
                        "location_hint": location_hint,
                    },
                }
            )
        logger.info(
            "node_completed: load_memories | run_id=%s | duration_ms=%.3f | field_count=%d | episodic_hits=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(field_definitions),
            episodic_hits,
        )
        return {
            "field_definitions": field_definitions,
            "memories": memories,
            "current_step": "load_memories",
        }

    async def _node_field_extraction(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        document_text = state.get("document_text") or ""
        field_definitions = state.get("field_definitions") or []
        memories = state.get("memories") or []
        memory_by_field: dict[str, dict] = {m["field"]: m["memory"] for m in memories}
        candidates = list(state.get("candidates") or [])
        line_item_fields = [fd["field_name"] for fd in field_definitions if fd["field_name"] in _EXT_LINE_ITEM_FIELDS]
        logger.info(
            "node_started: field_extraction | run_id=%s | field_count=%d | already_extracted=%d",
            state.get("run_id"),
            len(field_definitions),
            len(candidates),
        )
        for field_def in field_definitions:
            field_name = field_def["field_name"]
            if field_name in _LINE_ITEM_FIELD_NAMES:
                continue  # resolved row-by-row through the __LINE_ITEMS__ group
            already = next((c for c in candidates if c.get("field_name") == field_name), None)
            if already and already.get("candidates"):
                continue
            memory = memory_by_field.get(field_name, {})
            result = await self._run_candidate_agent(
                list(self._tools or []),
                document_text,
                field_name,
                memory_override=memory,
            )
            candidates.append(result)

        if line_item_fields:
            rows_section = state.get("document_text") or ""
            result = await self._run_line_item_candidate_agent(list(self._tools or []), rows_section)
            candidates.append(result)

        empty_fields = [c.get("field_name") for c in candidates if not c.get("candidates")]
        logger.info(
            "node_completed: field_extraction | run_id=%s | duration_ms=%.3f | group_count=%d | empty_fields=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(candidates),
            empty_fields,
        )
        return {"candidates": candidates, "current_step": "field_extraction"}

    async def _node_candidate_generation(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        document_text = state.get("document_text") or ""
        candidates = list(state.get("candidates") or [])
        low_confidence: list[str] = []
        field_definitions = state.get("field_definitions") or []
        all_field_names = {fd["field_name"] for fd in field_definitions}
        candidate_field_names = {c["field_name"] for c in candidates if c.get("candidates")}
        for field_name in all_field_names:
            if field_name in candidate_field_names or field_name in _LINE_ITEM_FIELD_NAMES:
                continue
            if field_name not in low_confidence:
                low_confidence.append(field_name)
        logger.info(
            "node_started: candidate_generation | run_id=%s | low_confidence_fields=%s",
            state.get("run_id"),
            low_confidence,
        )
        if not low_confidence:
            logger.info(
                "node_completed: candidate_generation | run_id=%s | duration_ms=%.3f | regenerated=0",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
            )

            return {"candidates": candidates, "current_step": "candidate_generation"}
        memory_by_field: dict[str, dict] = {m["field"]: m["memory"] for m in (state.get("memories") or [])}
        for field_name in low_confidence:
            result = await self._run_candidate_agent(
                list(self._tools or []),
                document_text,
                field_name,
                memory_override=memory_by_field.get(field_name, {}),
            )
            candidates.append(result)
        logger.info(
            "node_completed: candidate_generation | run_id=%s | duration_ms=%.3f | regenerated=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(low_confidence),
        )

        return {"candidates": candidates, "current_step": "candidate_generation"}

    async def _node_candidate_evaluation(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        document_text = state.get("document_text") or ""
        candidate_groups = state.get("candidates") or []
        verdicts: list[dict] = []
        logger.info(
            "node_started: candidate_evaluation | run_id=%s | candidate_groups=%d",
            state.get("run_id"),
            len(candidate_groups),
        )

        # Build work items (dedup + cap per field)
        field_candidates: dict[str, list[dict]] = {}
        total_candidates = 0
        for group in candidate_groups:
            field_name = group.get("field_name")
            if not field_name:
                continue
            items: list[dict] = []
            seen = set()
            for candidate in (group.get("candidates") or []):
                if not candidate.get("value"):
                    continue
                norm = self._normalize_value(candidate.get("value"))
                sig = f"{field_name}|{norm}"
                if sig in seen:
                    continue
                seen.add(sig)
                items.append({**candidate, "_sig": sig})
            if not items:
                continue
            items.sort(key=lambda x: (0 if x.get("location") else 1, 0 if x.get("surrounding_text") else 1))
            items = items[: self._max_candidates_per_field()]
            field_candidates[field_name] = items
            total_candidates += len(items)

        evals_done = 0
        max_evals = self._max_evaluations_total()
        semaphore = asyncio.Semaphore(self._eval_concurrency())

        async def eval_batch(field_name: str, batch: list[dict]):
            nonlocal evals_done
            async with semaphore:
                if evals_done >= max_evals:
                    return []
                evals_done += 1
                # Strip internal keys
                batch_clean = [{k: v for k, v in c.items() if not k.startswith("_")} for c in batch]
                return await self._run_validation_agent_batch(document_text, field_name, batch_clean)

        tasks = []
        for field_name, items in field_candidates.items():
            batch_size = self._eval_batch_size()
            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]
                tasks.append(eval_batch(field_name, batch))
        if tasks:
            results_lists = await asyncio.gather(*tasks)
            for rlist in results_lists:
                for v in rlist:
                    v.setdefault("field_name", None)
                    verdicts.append(v)

        verdicts = [v for v in verdicts if v.get("field_name") or any(k in v for k in ("value", "score"))]

        logger.info(
            "node_completed: candidate_evaluation | run_id=%s | duration_ms=%.3f | candidate_groups=%d | total_candidates=%d | verdict_count=%d | evals_done=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(candidate_groups),
            total_candidates,
            len(verdicts),
            evals_done,
        )

        return {"verdicts": verdicts, "current_step": "candidate_evaluation"}

    def _node_evidence_aggregation(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        logger.info(
            "node_started: evidence_aggregation | run_id=%s | candidate_groups=%d",
            state.get("run_id"),
            len(state.get("candidates") or []),
        )
        candidates_groups = state.get("candidates") or []
        verdicts = state.get("verdicts") or []
        verdict_scores: dict[str, list[float]] = {}
        for v in verdicts:
            fn = v.get("field_name")
            if fn:
                verdict_scores.setdefault(fn, []).append(v.get("score", 0))
        field_verdicts: list[dict] = []
        for group in candidates_groups:
            field_name = group.get("field_name")
            raw_candidates = group.get("candidates") or []
            if not raw_candidates:
                field_verdicts.append(
                    {
                        "field_name": field_name,
                        "passed": False,
                        "score": 0,
                        "sources": 0,
                        "resolved_value": None,
                        "reason": "no candidates",
                    }
                )
                continue
            scored: list[dict] = []
            for candidate in raw_candidates:
                base_score = 0.6 if candidate.get("source") == "semantic" else 0.5
                sources = 1  # semantic/episodic source
                if candidate.get("location"):
                    base_score += 0.15
                    sources += 1
                if candidate.get("surrounding_text"):
                    base_score += 0.1
                    sources += 1
                verdict_score = 0.0
                v_scores = verdict_scores.get(field_name, [])
                if v_scores:
                    verdict_score = max(v_scores)
                    sources += 1
                final_score = round(0.5 * base_score + 0.5 * verdict_score, 4)
                scored.append(
                    {
                        "field_name": field_name,
                        "value": candidate.get("value"),
                        "score": final_score,
                        "sources": sources,
                        "location": candidate.get("location"),
                    }
                )
            scored.sort(key=lambda item: item["score"], reverse=True)
            top = scored[0]
            separation = round(top["score"] - (scored[1]["score"] if len(scored) > 1 else 0), 4)
            field_verdicts.append(
                {
                    "field_name": field_name,
                    "passed": False,
                    "score": top["score"],
                    "sources": top["sources"],
                    "separation": separation,
                    "resolved_value": top.get("value"),
                }
            )
        logger.info(
            "node_completed: evidence_aggregation | run_id=%s | duration_ms=%.3f | aggregated_fields=%d",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(field_verdicts),
        )
        return {"verdicts": field_verdicts, "current_step": "evidence_aggregation"}

    def _node_quality_gate(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        verdicts = state.get("verdicts") or []
        min_score = self._min_score()
        min_sources = self._min_sources()
        min_separation = self._min_separation()
        all_passed = True
        failures: list[str] = []
        failure_reasons: list[str] = []
        logger.info(
            "node_started: quality_gate | run_id=%s | retry=%s/%s | verdict_count=%d | min_score=%s "
            "min_sources=%s min_separation=%s",
            state.get("run_id"),
            state.get("retry_count", 0),
            self._max_retries(),
            len(verdicts),
            min_score,
            min_sources,
            min_separation,
        )
        for field_verdict in verdicts:
            if (
                field_verdict.get("field_name") in _LINE_ITEM_FIELD_NAMES
                or field_verdict.get("field_name") == _ROW_GROUP_FIELD
            ):
                continue  # row fields are evaluated as part of the __LINE_ITEMS__ group
            score = float(field_verdict.get("score", 0))
            sources = int(field_verdict.get("sources", 0))
            separation = float(field_verdict.get("separation", 0))
            value = field_verdict.get("resolved_value")
            resolved_ok = separation >= min_separation or value is None
            passed = bool(score >= min_score and sources >= min_sources and resolved_ok)
            field_verdict["passed"] = passed
            if not passed:
                all_passed = False
                field_name = field_verdict.get("field_name")
                failures.append(field_name)
                breached: list[str] = []
                if score < min_score:
                    breached.append(f"score={score}<{min_score}")
                if sources < min_sources:
                    breached.append(f"sources={sources}<{min_sources}")
                if not resolved_ok:
                    breached.append(f"separation={separation}<{min_separation}")
                failure_reasons.append(f"{field_name}({','.join(breached)})")
        extracted_header = [
            {"field_name": v["field_name"], "value": v["resolved_value"]}
            for v in verdicts
            if v.get("passed")
            and v.get("field_name") not in _EXT_LINE_ITEM_FIELDS
            and v.get("field_name") != _ROW_GROUP_FIELD
        ]
        extracted_line_items: list[list[dict]] = []
        line_items_candidate = next(
            (g for g in state.get("candidates") or [] if g.get("field_name") == _ROW_GROUP_FIELD),
            None,
        )
        if line_items_candidate:
            raw_value = (
                line_items_candidate.get("candidates", [{}])[0].get("value")
                if line_items_candidate.get("candidates")
                else None
            )
            if isinstance(raw_value, str):
                try:
                    raw_value = json.loads(raw_value)
                except (json.JSONDecodeError, TypeError):
                    raw_value = None
            if isinstance(raw_value, list):
                for row in raw_value:
                    extracted_line_items.append(
                        [
                            {"field_name": k.lower(), "value": str(v)}
                            for k, v in (row.items() if isinstance(row, dict) else [])
                            if k.lower() in _EXT_LINE_ITEM_FIELDS
                        ]
                    )
        # Compute candidate signature for no-progress detection
        candidates_groups = state.get("candidates") or []
        candidate_sigs = []
        for group in candidates_groups:
            fn = group.get("field_name")
            for cand in (group.get("candidates") or []):
                val = cand.get("value")
                if val:
                    candidate_sigs.append(self._candidate_signature(fn or "", val, cand.get("source")))
        candidate_sig = "|".join(sorted(set(candidate_sigs)))
        last_sig = state.get("candidate_signature")
        no_progress = candidate_sig and last_sig and candidate_sig == last_sig
        retry_count_state = int(state.get("retry_count", 0))
        if no_progress:
            no_progress_retries = int(state.get("no_progress_retries", 0)) + 1
        else:
            no_progress_retries = 0

        if all_passed:
            extracted_po = _reconstruct_extracted_po(extracted_header, extracted_line_items)
            total_amount = float(state.get("po_total_amount") or _line_items_total(extracted_po))
            logger.info(
                "quality_gate: passed=true | run_id=%s | duration_ms=%.3f | header_fields=%d | "
                "line_items=%d | total=%s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                len(extracted_header),
                len(extracted_line_items),
                total_amount,
            )
            return {
                "extracted_header_fields": extracted_header,
                "extracted_line_item_fields": extracted_line_items,
                "extracted_po": extracted_po,
                "po_total_amount": total_amount,
                "extraction_result": {
                    "passed": True,
                    "verdicts": verdicts,
                    "header_fields": extracted_header,
                    "line_items": extracted_line_items,
                },
                "current_step": "quality_gate",
                "candidate_signature": candidate_sig,
            }

        # Check no-progress
        if no_progress and no_progress_retries > self._no_progress_threshold_retries():
            logger.warning(
                "quality_gate: no_progress | run_id=%s | duration_ms=%.3f | sig=%s",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                candidate_sig,
            )
            return {
                "status": "FAILED",
                "current_step": "quality_gate",
                "extraction_error": "Extraction failed to make progress",
                "extraction_error_code": "EVALUATION_NO_PROGRESS",
                "candidate_signature": candidate_sig,
                "no_progress_retries": no_progress_retries,
            }

        retry_count = retry_count_state + 1
        logger.warning(
            "quality_gate: passed=false | run_id=%s | duration_ms=%.3f | retry=%s/%s | failed_fields=%s | breached=%s | no_progress=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            retry_count,
            self._max_retries(),
            failures,
            failure_reasons,
            no_progress,
        )
        return {
            "retry_count": retry_count,
            "candidates": [],
            "verdicts": [],
            "current_step": "quality_gate",
            "status": "RUNNING",
            "extraction_error": None,
            "candidate_signature": candidate_sig,
            "no_progress_retries": no_progress_retries if no_progress else 0,
        }

    def _node_recovery(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        retry_count = int(state.get("retry_count", 0))
        max_retries = self._max_retries()
        logger.info(
            "node_started: recovery | run_id=%s | retry=%s/%s",
            state.get("run_id"),
            retry_count,
            max_retries,
        )
        if retry_count > max_retries:
            logger.error(
                "node_failed: recovery | run_id=%s | duration_ms=%.3f | retry=%s/%s | error_code=RECOVERY_EXHAUSTED",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                retry_count,
                max_retries,
            )
            return {
                "status": "FAILED",
                "current_step": "recovery",
                "extraction_error": "Extraction recovery exhausted",
                "extraction_error_code": "RECOVERY_EXHAUSTED",
            }
        logger.info(
            "node_completed: recovery | run_id=%s | duration_ms=%.3f | retry=%s/%s | action=retry",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            retry_count,
            max_retries,
        )
        return {"current_step": "recovery", "retry_count": retry_count}

    async def _node_persist(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        po_id = state.get("po_id")
        extracted_header = state.get("extracted_header_fields") or []
        extracted_line_items = state.get("extracted_line_item_fields") or []
        logger.info(
            "node_started: persist | run_id=%s | po_id=%s | header_fields=%d | line_items=%d",
            state.get("run_id"),
            po_id,
            len(extracted_header),
            len(extracted_line_items),
        )
        if not po_id:
            logger.warning(
                "node_skipped: persist | run_id=%s | duration_ms=%.3f | reason=no_po_id",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
            )
            return {"current_step": "persist", "extraction_result": state.get("extraction_result", {})}
        persist_header = self._tool_map["persist_header_field"]
        persist_line_items = self._tool_map["persist_line_item"]
        persisted_header: list[dict] = []
        persist_failures: list[str] = []
        for field in extracted_header:
            try:
                await persist_header.ainvoke(
                    {"po_id": po_id, "field_name": field["field_name"], "value": str(field.get("value", ""))}
                )
                persisted_header.append(field)
            except Exception as exc:
                persist_failures.append(f"{field['field_name']}:{type(exc).__name__}")
                continue
        persisted_line_items: list[list[dict]] = []
        line_item_failures = 0
        for row_fields in extracted_line_items:
            try:
                await persist_line_items.ainvoke({"po_id": po_id, "fields": row_fields})
                persisted_line_items.append(row_fields)
            except Exception:
                line_item_failures += 1
                continue
        log = logger.warning if persist_failures or line_item_failures else logger.info
        log(
            "node_completed: persist | run_id=%s | duration_ms=%.3f | header_persisted=%s/%s | "
            "line_items_persisted=%s/%s | failed_fields=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(persisted_header),
            len(extracted_header),
            len(persisted_line_items),
            len(extracted_line_items),
            persist_failures,
        )
        extracted_po = state.get("extracted_po") or _reconstruct_extracted_po(persisted_header, persisted_line_items)
        return {
            "extracted_header_fields": persisted_header,
            "extracted_line_item_fields": persisted_line_items,
            "extracted_po": extracted_po,
            "extraction_result": {
                **(state.get("extraction_result") or {}),
                "persisted": True,
            },
            "current_step": "persist",
        }

    async def _node_update_episodic_memory(self, state: ExtractionState) -> dict[str, Any]:
        started = time.perf_counter()
        customer_id = state.get("customer_id")
        extraction_result = state.get("extraction_result") or {}
        header_fields = state.get("extracted_header_fields") or []
        logger.info(
            "node_started: update_episodic_memory | run_id=%s | customer_id=%s | persisted=%s | field_count=%d",
            state.get("run_id"),
            customer_id,
            bool(extraction_result.get("persisted")),
            len(header_fields),
        )
        if not customer_id or not extraction_result.get("persisted"):
            logger.info(
                "node_skipped: update_episodic_memory | run_id=%s | duration_ms=%.3f | "
                "reason=no_customer_or_not_persisted",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
            )
            return {"current_step": "update_episodic_memory", "status": "RUNNING"}
        update_memory = self._tool_map["update_episodic_memory"]
        updated = 0
        for field in header_fields:
            try:
                await update_memory.ainvoke(
                    {
                        "customer_id": customer_id,
                        "field_name": field["field_name"],
                        "location_hint": "document_header",
                        "document_pattern": "customer_pattern_observed",
                        "instruction": "Pattern extracted successfully",
                        "confidence": self._validated_confidence(),
                    }
                )
                updated += 1
            except Exception:
                continue
        logger.info(
            "node_completed: update_episodic_memory | run_id=%s | duration_ms=%.3f | updated=%s/%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            updated,
            len(header_fields),
        )
        return {"current_step": "update_episodic_memory", "status": "RUNNING"}

    # -- inner agent helpers ---------------------------------------------------

    @staticmethod
    def _normalize_value(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text

    @staticmethod
    def _candidate_signature(field_name: str, value: Any, source: Any = None) -> str:
        norm = ExtractionAgent._normalize_value(value)
        source_str = str(source) if source else ""
        sig = f"{field_name}|{norm}|{source_str}"
        return hashlib.md5(sig.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _best_value(candidate_group: dict) -> str | None:
        candidates = candidate_group.get("candidates") or []
        if not candidates:
            return None
        best = candidates[0]
        return str(best.get("value")) if best.get("value") else None

    @staticmethod
    def _last_message_text(response: Any) -> str:
        """Read the model's final text from a create_agent() result.

        langchain returns {"messages": [...]} with no "output" key, so the last
        message carrying text is the only reliable source. Legacy string/dict
        results (and the "output" key) are still honoured.
        """
        if isinstance(response, str):
            return response
        if not isinstance(response, dict):
            return ""
        direct = response.get("output")
        if isinstance(direct, str) and direct.strip():
            return direct
        for message in reversed(response.get("messages") or []):
            content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("text")]
                if texts:
                    return "\n".join(str(t) for t in texts)
        return ""

    async def _run_candidate_agent(
        self,
        tools: list[Any],
        document_text: str,
        field_name: str,
        *,
        memory_override: dict | None = None,
    ) -> dict:
        if self._candidate_agent is None:
            return {"field_name": field_name, "candidates": []}
        memory = memory_override or {}
        procedure = "\n".join(
            memory.get("instruction", "").splitlines() or ["Identify the value from the document text."]
        )
        prompt_payload = (
            f"Document:\n{document_text}\n\nField: {field_name}\n"
            f"Procedure:\n{procedure}\n"
            f"Possible labels: {memory.get('location_hint') or ''}\nReturn JSON with candidates."
        )
        try:
            response = await self._candidate_agent.ainvoke({"messages": [HumanMessage(content=prompt_payload)]})
            return _parse_candidate_response(self._last_message_text(response))
        except Exception:
            return {"field_name": field_name, "candidates": []}

    async def _run_line_item_candidate_agent(self, tools: list[Any], document_text: str) -> dict:
        if self._candidate_agent is None:
            return {"field_name": "__LINE_ITEMS__", "candidates": []}
        data = load_memory()
        procedure = (data.get("line_item") or {}).get(
            "procedure"
        ) or "Extract every product row from the line items section."
        semantic: dict = data.get("semantic") or {}
        labels: list[str] = []
        for field_name in _LINE_ITEM_FIELD_NAMES:
            field_labels = (semantic.get(field_name) or {}).get("labels") or []
            if isinstance(field_labels, list):
                labels.extend(str(label) for label in field_labels)
        prompt_payload = (
            "Document:\n"
            f"{document_text}\n\n"
            "Extract ALL line-item rows from the LINE ITEMS SECTION.\n"
            f"Procedure:\n{procedure}\n"
            f"Possible line-item columns: {', '.join(labels)}\n"
            "Return a single JSON object:\n"
            '{"field_name":"__LINE_ITEMS__","candidates":[{"value":"[{product_name:...,product_name...}]","source":"semantic","location":"line_items"}]}\n'
        )
        try:
            response = await self._candidate_agent.ainvoke({"messages": [HumanMessage(content=prompt_payload)]})
            return _parse_candidate_response(self._last_message_text(response))
        except Exception:
            return {"field_name": "__LINE_ITEMS__", "candidates": []}

    async def _run_validation_agent_batch(self, document_text: str, field_name: str | None, candidates: list[dict]) -> list[dict]:
        if self._validation_agent is None or not field_name or not candidates:
            return [
                {
                    "field_name": field_name,
                    "score": 0,
                    "accepted": False,
                    "reasons": ["validation agent not available"],
                }
                for _ in candidates
            ]

        candidates_payload = []
        for c in candidates:
            candidates_payload.append(
                {
                    "value": c.get("value"),
                    "location": c.get("location"),
                    "surrounding_text": c.get("surrounding_text"),
                    "source": c.get("source"),
                }
            )

        prompt_payload = (
            "Document:\n"
            f"{document_text}\n\n"
            f"Field: {field_name}\n"
            f"Candidates: {json.dumps(candidates_payload, ensure_ascii=False)}\n"
            "Return a JSON object with verdicts for all candidates."
        )

        async def _call():
            response = await self._validation_agent.ainvoke({"messages": [HumanMessage(content=prompt_payload)]})
            return self._last_message_text(response)

        @retry(
            retry=retry_if_exception_type(Exception),
            wait=wait_random_exponential(multiplier=self._eval_backoff_mult(), min=self._eval_backoff_base(), max=self._eval_backoff_max()),
            stop=stop_after_attempt(self._eval_max_retries()),
            reraise=True,
        )
        async def _call_with_retry():
            return await _call()

        try:
            text = await _call_with_retry()
            parsed = _first_json_object(text) or {}
            verdicts_raw = parsed.get("verdicts") or parsed.get("results") or []
            # If it's a single verdict dict (old format), wrap it
            if verdicts_raw and not isinstance(verdicts_raw, list):
                verdicts_raw = [verdicts_raw]
            # If still empty but parsed looks like single old verdict
            if not verdicts_raw and any(k in parsed for k in ("score", "accepted")):
                verdicts_raw = [parsed]
            results: list[dict] = []
            for v in verdicts_raw:
                if not isinstance(v, dict):
                    continue
                val = v.get("value")
                results.append(
                    {
                        "field_name": field_name or v.get("field_name"),
                        "value": val,
                        "score": float(v.get("score", 0)),
                        "accepted": bool(v.get("accepted", False)),
                        "reasons": v.get("reasons") or [],
                        "negative_evidence": v.get("negative_evidence") or [],
                    }
                )
            # Try to match by value if model didn't echo values
            if len(results) != len(candidates):
                matched = []
                # If we got exactly 1 verdict and it has no value-specific match info, apply to all
                if len(results) == 1:
                    single = results[0]
                    for c in candidates:
                        matched.append(
                            {
                                "field_name": field_name or single.get("field_name"),
                                "value": c.get("value"),
                                "score": float(single.get("score", 0)),
                                "accepted": bool(single.get("accepted", False)),
                                "reasons": single.get("reasons") or [],
                                "negative_evidence": single.get("negative_evidence") or [],
                            }
                        )
                    return matched[: len(candidates)]
                for c in candidates:
                    c_norm = self._normalize_value(c.get("value"))
                    found = None
                    for r in results:
                        r_norm = self._normalize_value(r.get("value"))
                        if r_norm and r_norm == c_norm:
                            found = r
                            break
                    if found:
                        matched.append({**found, "value": c.get("value"), "field_name": field_name})
                    else:
                        # fallback to first result if generic
                        fallback = results[0] if results else None
                        if fallback:
                            matched.append(
                                {
                                    "field_name": field_name or fallback.get("field_name"),
                                    "value": c.get("value"),
                                    "score": float(fallback.get("score", 0)),
                                    "accepted": bool(fallback.get("accepted", False)),
                                    "reasons": fallback.get("reasons") or [],
                                }
                            )
                        else:
                            matched.append(
                                {
                                    "field_name": field_name,
                                    "value": c.get("value"),
                                    "score": 0.0,
                                    "accepted": False,
                                    "reasons": ["no verdict returned"],
                                }
                            )
                return matched[: len(candidates)]
            return results[: len(candidates)]
        except Exception:
            return [
                {
                    "field_name": field_name,
                    "value": c.get("value"),
                    "score": 0.0,
                    "accepted": False,
                    "reasons": ["validation failed"],
                }
                for c in candidates
            ]

    async def _run_validation_agent(self, document_text: str, field_name: str | None, candidate: dict) -> dict:
        results = await self._run_validation_agent_batch(document_text, field_name, [candidate])
        return results[0] if results else {
            "field_name": field_name,
            "score": 0,
            "accepted": False,
            "reasons": ["validation failed"],
        }

"""Extraction Agent: LangGraph subgraph that answers "what is in the document?".

Implements BaseAgent.create_agent/invoke_agent. The subgraph runs through
document processing → customer identification → load memories → header field
extraction → line item field extraction. Document processing splits the OCR
result into header/line-item sections and page numbers; each extraction node
only inspects its own section and pages, using a ToolStrategy structured-output
agent built from the extraction.yaml prompts. The line item node is the final
node: it resolves the structured PO (header fields + line items), persists it,
and records episodic memory. Business-level PO validation belongs to the
VerifierAgent in the PO orchestrator, not here.
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.clients.base import BaseBedrockClient, BaseS3Client
from app.config.logging import get_logger
from app.config.settings import Settings
from app.exceptions.client_exceptions import BedrockError
from app.helpers.yaml_loader import load_memory, load_prompt
from app.models.domain import HeaderExtractionResult, LineItemExtractionResult
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

#: Line-item fields kept when converting a validated ExtractedLineItem row
#: into the state/persistence shape (total_price is derived, line_item_id is
#: internal). Tuple keeps row output order deterministic.
_EXT_LINE_ITEM_FIELDS: tuple[str, ...] = ("product_name", "sku", "quantity", "unit_price")

_LINE_ITEM_FIELD_NAMES: list[str] = ["product_name", "sku", "quantity", "unit_price", "total_price"]

#: Maximum attempts for each extraction node before the conditional edge stops
#: retrying: the header node fails the run when the cap is hit, the line item
#: node hands a partial extraction off to the verifier.
_MAX_EXTRACTION_ATTEMPTS = 3


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


def _line_item_rows(result: Any) -> list[list[dict[str, Any]]]:
    """Normalize a LineItemExtractionResult into per-row field dicts.

    One model row = one line item row, so the relationship between the fields
    of the same line item is preserved. Values are stringified to keep the
    existing ``extracted_line_item_fields`` / persistence contract.
    """
    if isinstance(result, dict):
        try:
            result = LineItemExtractionResult.model_validate(result)
        except Exception:
            return []
    if not isinstance(result, LineItemExtractionResult):
        return []
    rows: list[list[dict[str, Any]]] = []
    for item in result.line_items:
        data = item.model_dump()
        row = [
            {"field_name": field_name, "value": str(data[field_name])}
            for field_name in _EXT_LINE_ITEM_FIELDS
            if data.get(field_name) is not None
        ]
        if row:
            rows.append(row)
    return rows


def _header_field_rows(result: Any) -> list[dict[str, Any]]:
    """Normalize a HeaderExtractionResult into [{field_name, value}] rows.

    Null/blank values are dropped: the prompts instruct the model to return
    null instead of guessing, and unresolved fields simply stay unextracted.
    """
    if isinstance(result, dict):
        try:
            result = HeaderExtractionResult.model_validate(result)
        except Exception:
            return []
    if not isinstance(result, HeaderExtractionResult):
        return []
    rows: list[dict[str, Any]] = []
    for field in result.header_fields:
        value = field.value
        if value is None or not str(value).strip():
            continue
        rows.append({"field_name": field.field_name, "value": str(value)})
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
        # agent_name -> (rendered system prompt, compiled agent); the prompt
        # embeds per-run data (field definitions, memories, pages) so the cache
        # key is the rendered text itself.
        self._extraction_agents: dict[str, tuple[str, Any]] = {}

    # -- helpers ---------------------------------------------------------------

    def _validated_confidence(self) -> float:
        if self._settings is None:
            return 0.8
        return float(getattr(self._settings, "extraction_validated_confidence", 0.8))

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
        # No tools are bound: the candidate agent is a single-shot text -> JSON
        # generator. Binding the repository tools made the model answer with tool
        # calls instead of the requested candidate JSON.
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
        self._candidate_agent = self._build_inner_agent(candidate_prompt, "candidate_generator")

        graph = StateGraph(ExtractionState)
        graph.add_node("document_processing", self._node_document_processing)
        graph.add_node("customer_identification", self._node_customer_identification)
        graph.add_node("load_memories", self._node_load_memories)
        graph.add_node("header_field_extraction", self._node_header_field_extraction)
        graph.add_node("line_item_field_extraction", self._node_line_item_field_extraction)

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
        graph.add_edge("load_memories", "header_field_extraction")
        graph.add_conditional_edges(
            "header_field_extraction",
            self._after_header_field_extraction,
            {
                "failed": END,
                "line_item": "line_item_field_extraction",
                "retry": "header_field_extraction",
            },
        )
        graph.add_conditional_edges(
            "line_item_field_extraction",
            self._after_line_item_field_extraction,
            {
                "done": END,
                "retry": "line_item_field_extraction",
            },
        )
        self._graph = graph.compile()
        logger.info(
            "extraction_graph_built: nodes=%s",
            [
                "document_processing",
                "customer_identification",
                "load_memories",
                "header_field_extraction",
                "line_item_field_extraction",
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
            "header_section": result.get("header_section", ""),
            "line_item_section": result.get("line_item_section", ""),
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

    @staticmethod
    def _after_header_field_extraction(state: ExtractionState) -> Literal["failed", "line_item", "retry"]:
        if state.get("status") != "RUNNING":
            return "failed"
        if state.get("extracted_header_fields"):
            return "line_item"
        if int(state.get("header_extraction_attempts") or 0) >= _MAX_EXTRACTION_ATTEMPTS:
            return "failed"
        return "retry"

    @staticmethod
    def _after_line_item_field_extraction(state: ExtractionState) -> Literal["done", "retry"]:
        if state.get("status") != "RUNNING":
            return "done"
        # The node only writes extraction_result once it has finalized
        # (rows resolved, retry cap reached, or no line-item content at all).
        if state.get("extraction_result") or state.get("extracted_line_item_fields"):
            return "done"
        if int(state.get("line_item_extraction_attempts") or 0) >= _MAX_EXTRACTION_ATTEMPTS:
            return "done"
        return "retry"

    # -- node implementations --------------------------------------------------

    @staticmethod
    def _normalize_pages(raw: Any) -> list[int]:
        """Keep real ints only, deduplicated and ascending (1-based)."""
        if not isinstance(raw, list):
            return []
        pages: set[int] = set()
        for page in raw:
            if isinstance(page, bool):
                continue
            if isinstance(page, int) and page > 0:
                pages.add(page)
            elif isinstance(page, float) and page.is_integer() and page > 0:
                pages.add(int(page))
        return sorted(pages)

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
        header_section = str(raw.get("headerSection") or "")
        line_item_section = str(raw.get("lineItemsSection") or "")
        header_pages = self._normalize_pages(raw.get("headerPages"))
        line_item_pages = self._normalize_pages(raw.get("lineItemPages"))
        logger.info(
            "node_completed: document_processing | run_id=%s | duration_ms=%.3f | text_chars=%d | "
            "header_pages=%s | line_item_pages=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            len(document_text),
            header_pages,
            line_item_pages,
        )
        return {
            "document_text": document_text,
            "header_section": header_section,
            "line_item_section": line_item_section,
            "header_pages": header_pages,
            "line_item_pages": line_item_pages,
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

    async def _node_header_field_extraction(self, state: ExtractionState) -> dict[str, Any]:
        """Extract header-level fields from ``header_section`` / ``header_pages``.

        The node only ever sees the header section (falling back to the full
        text when the OCR model omitted it) and is routed again by the
        conditional edge while it extracts nothing, up to
        ``_MAX_EXTRACTION_ATTEMPTS``; then the run fails.
        """
        started = time.perf_counter()
        attempts = int(state.get("header_extraction_attempts") or 0) + 1
        document_text = state.get("document_text") or ""
        content = state.get("header_section") or document_text
        pages = state.get("header_pages") or []
        field_definitions, memories = self._scoped_extraction_inputs(state, line_item_scope=False)
        logger.info(
            "node_started: header_field_extraction | run_id=%s | attempt=%d | field_count=%d | pages=%s",
            state.get("run_id"),
            attempts,
            len(field_definitions),
            pages,
        )
        agent = self._build_extraction_agent(
            prompt_key="header_field_extraction",
            pages_placeholder="{{header_pages}}",
            field_definitions=field_definitions,
            memories=memories,
            pages=pages,
            output_model=HeaderExtractionResult,
            agent_name="header_field_extraction",
        )
        structured = await self._run_extraction_agent(agent, content, "header_field_extraction")
        header_fields = _header_field_rows(structured)
        base: dict[str, Any] = {
            "header_extraction_attempts": attempts,
            "current_step": "header_field_extraction",
        }
        if header_fields:
            logger.info(
                "node_completed: header_field_extraction | run_id=%s | duration_ms=%.3f | attempt=%d | field_count=%d",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                attempts,
                len(header_fields),
            )
            return {**base, "extracted_header_fields": header_fields}
        if attempts >= _MAX_EXTRACTION_ATTEMPTS:
            logger.error(
                "node_failed: header_field_extraction | run_id=%s | duration_ms=%.3f | attempt=%d | "
                "reason=no_header_fields",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                attempts,
            )
            return {
                **base,
                "status": "FAILED",
                "extraction_error": "No header fields could be extracted from the document",
                "extraction_error_code": "EXTRACTION_VALIDATION_FAILED",
            }
        logger.warning(
            "node_retry: header_field_extraction | run_id=%s | duration_ms=%.3f | attempt=%d | reason=no_header_fields",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            attempts,
        )
        return base

    async def _node_line_item_field_extraction(self, state: ExtractionState) -> dict[str, Any]:
        """Extract line-item rows from ``line_item_section`` / ``line_item_pages``.

        This is the final node of the subgraph: once the rows resolve (or the
        retry cap is reached, or there is no line-item content at all), it
        reconstructs the structured PO, persists it, and records episodic
        memory for the parent graph / VerifierAgent.
        """
        started = time.perf_counter()
        attempts = int(state.get("line_item_extraction_attempts") or 0) + 1
        document_text = state.get("document_text") or ""
        line_item_section = state.get("line_item_section") or ""
        pages = state.get("line_item_pages") or []
        has_content = bool(line_item_section or pages)
        logger.info(
            "node_started: line_item_field_extraction | run_id=%s | attempt=%d | pages=%s | has_content=%s",
            state.get("run_id"),
            attempts,
            pages,
            has_content,
        )

        line_items: list[list[dict[str, Any]]] = []
        if has_content:
            content = line_item_section or document_text
            field_definitions, memories = self._scoped_extraction_inputs(state, line_item_scope=True)
            agent = self._build_extraction_agent(
                prompt_key="line_item_field_extraction",
                pages_placeholder="{{line_item_pages}}",
                field_definitions=field_definitions,
                memories=memories,
                pages=pages,
                output_model=LineItemExtractionResult,
                agent_name="line_item_field_extraction",
            )
            structured = await self._run_extraction_agent(agent, content, "line_item_field_extraction")
            line_items = _line_item_rows(structured)

        base: dict[str, Any] = {
            "line_item_extraction_attempts": attempts,
            "current_step": "line_item_field_extraction",
        }
        if not line_items and has_content and attempts < _MAX_EXTRACTION_ATTEMPTS:
            logger.warning(
                "node_retry: line_item_field_extraction | run_id=%s | duration_ms=%.3f | attempt=%d | reason=no_rows",
                state.get("run_id"),
                (time.perf_counter() - started) * 1000,
                attempts,
            )
            return base

        header_fields = list(state.get("extracted_header_fields") or [])
        extracted_po = _reconstruct_extracted_po(header_fields, line_items)
        total_amount = float(state.get("po_total_amount") or _line_items_total(extracted_po))
        extraction_result: dict[str, Any] = {
            "header_fields": header_fields,
            "line_items": line_items,
        }

        po_id = state.get("po_id")
        if po_id:
            header_fields, line_items = await self._persist_extracted(po_id, header_fields, line_items)
            extracted_po = _reconstruct_extracted_po(header_fields, line_items)
            extraction_result["persisted"] = True

        customer_id = state.get("customer_id")
        if customer_id and extraction_result.get("persisted"):
            await self._write_episodic_patterns(customer_id, header_fields)

        logger.info(
            "node_completed: line_item_field_extraction | run_id=%s | duration_ms=%.3f | attempt=%d | "
            "header_fields=%d | line_items=%d | total=%s | persisted=%s",
            state.get("run_id"),
            (time.perf_counter() - started) * 1000,
            attempts,
            len(header_fields),
            len(line_items),
            total_amount,
            bool(extraction_result.get("persisted")),
        )
        return {
            **base,
            "extracted_line_item_fields": line_items,
            "extracted_po": extracted_po,
            "po_total_amount": total_amount,
            "extraction_result": extraction_result,
        }

    async def _persist_extracted(
        self,
        po_id: str,
        header_fields: list[dict[str, Any]],
        line_items: list[list[dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        """Persist resolved header fields and line items; best effort per row."""
        persist_header = self._tool_map["persist_header_field"]
        persist_line_items = self._tool_map["persist_line_item"]
        persisted_header: list[dict] = []
        header_failures: list[str] = []
        for field in header_fields:
            try:
                await persist_header.ainvoke(
                    {"po_id": po_id, "field_name": field["field_name"], "value": str(field.get("value", ""))}
                )
                persisted_header.append(field)
            except Exception as exc:
                header_failures.append(f"{field['field_name']}:{type(exc).__name__}")
        persisted_line_items: list[list[dict]] = []
        line_item_failures = 0
        for row_fields in line_items:
            try:
                await persist_line_items.ainvoke({"po_id": po_id, "fields": row_fields})
                persisted_line_items.append(row_fields)
            except Exception:
                line_item_failures += 1
        log = logger.warning if header_failures or line_item_failures else logger.info
        log(
            "node_completed: persist | po_id=%s | header_persisted=%s/%s | "
            "line_items_persisted=%s/%s | failed_fields=%s",
            po_id,
            len(persisted_header),
            len(header_fields),
            len(persisted_line_items),
            len(line_items),
            header_failures,
        )
        return persisted_header, persisted_line_items

    async def _write_episodic_patterns(self, customer_id: str, header_fields: list[dict[str, Any]]) -> None:
        """Record extraction patterns as episodic memory for future runs."""
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
            "node_completed: update_episodic_memory | customer_id=%s | updated=%s/%s",
            customer_id,
            updated,
            len(header_fields),
        )

    # -- inner agent helpers ---------------------------------------------------

    def _best_value(self, candidate_group: dict) -> str | None:
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

    def _scoped_extraction_inputs(
        self,
        state: ExtractionState,
        *,
        line_item_scope: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Field definitions + customer episodic memory for one extraction scope."""
        field_definitions = state.get("field_definitions") or []
        memory_by_field = {m["field"]: m["memory"] for m in (state.get("memories") or [])}
        if line_item_scope:
            scoped = [fd for fd in field_definitions if fd.get("field_name") in _LINE_ITEM_FIELD_NAMES]
        else:
            scoped = [fd for fd in field_definitions if fd.get("field_name") not in _LINE_ITEM_FIELD_NAMES]
        memories = {
            fd["field_name"]: memory_by_field[fd["field_name"]]
            for fd in scoped
            if fd.get("field_name") in memory_by_field
        }
        return scoped, memories

    def _build_extraction_agent(
        self,
        *,
        prompt_key: str,
        pages_placeholder: str,
        field_definitions: list[dict[str, Any]],
        memories: dict[str, Any],
        pages: list[int],
        output_model: Any,
        agent_name: str,
    ) -> Any:
        """Render an extraction.yaml prompt and build its ToolStrategy agent.

        The YAML prompt is the source of truth: field definitions, episodic
        memory, and the allowed pages are substituted into its placeholders at
        runtime; no prompt content is hardcoded here. The rendered prompt
        embeds per-run data, so agents are cached by rendered text.
        """
        rendered = load_prompt("extraction.yaml", prompt_key)
        rendered = rendered.replace("{{field_definitions}}", json.dumps(field_definitions, indent=2, default=str))
        rendered = rendered.replace("{{episodic_memory}}", json.dumps(memories, indent=2, default=str))
        rendered = rendered.replace(
            pages_placeholder,
            json.dumps(list(pages)) if pages else "all pages (unrestricted)",
        )
        cached = self._extraction_agents.get(agent_name)
        if cached is not None and cached[0] == rendered:
            return cached[1]
        if self._chat_model is None:
            return None
        agent = create_agent(
            self._chat_model,
            tools=[],
            system_prompt=SystemMessage(rendered),
            response_format=ToolStrategy(schema=output_model),
            middleware=[TracingMiddleware(agent_name=f"{self.name}.{agent_name}")],
            name=f"{self.name}.{agent_name}",
        )
        self._extraction_agents[agent_name] = (rendered, agent)
        return agent

    async def _run_extraction_agent(self, agent: Any, content: str, node_name: str) -> Any:
        """Invoke a structured extraction agent; return its structured_response.

        Returns ``None`` when the agent is unavailable, the invocation raises,
        or no structured output was produced — the callers treat that as "no
        extraction" and let the retry edges decide the outcome.
        """
        if agent is None:
            return None
        try:
            response = await agent.ainvoke({"messages": [HumanMessage(content=f"Document:\n{content}")]})
        except Exception:
            logger.exception(
                "node_failed: %s | error=structured_agent_invoke_failed",
                node_name,
            )
            return None
        if not isinstance(response, dict):
            return None
        return response.get("structured_response")

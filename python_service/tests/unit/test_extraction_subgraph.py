"""Extraction subgraph unit tests (no database required).

Uses in-memory repository fakes and a scripted inner agent so every node of
the subgraph can be exercised deterministically.
"""

from __future__ import annotations

import json
import types
from typing import Any

import pytest

from app.agents.extraction_agent import ExtractionAgent
from app.helpers.yaml_loader import load_memory

_HEADER_FIELD_NAMES = [
    "po_number",
    "customer",
    "gst_no",
    "po_date",
    "currency",
    "ship_to",
    "address_1",
    "address_2",
    "city",
    "state",
    "country",
    "zip",
    "total_amount",
]
_LINE_ITEM_FIELD_NAMES = ["product_name", "sku", "quantity", "unit_price", "total_price"]


class _FieldDefinition:
    def __init__(self, field_id: int, field_name: str, field_type: str = "string") -> None:
        self.field_id = str(field_id)
        self.field_name = field_name
        self.field_description = field_name
        self.field_type = field_type


class _FieldDefinitionRepo:
    def __init__(self) -> None:
        self._defs = [_FieldDefinition(i, name) for i, name in enumerate(_HEADER_FIELD_NAMES + _LINE_ITEM_FIELD_NAMES)]

    async def list_all(self) -> list:
        return self._defs

    async def list_header_fields(self) -> list:
        return [d for d in self._defs if d.field_name not in _LINE_ITEM_FIELD_NAMES]

    async def list_line_item_fields(self) -> list:
        return [d for d in self._defs if d.field_name in _LINE_ITEM_FIELD_NAMES]

    async def get_by_name(self, field_name: str):
        return next((d for d in self._defs if d.field_name == field_name), None)


class _CustomerRepo:
    def __init__(self, name=None, customer_code=None, customer_id="cust-1", **kwargs) -> None:
        self._name = name
        self._customer_code = customer_code
        self._customer_id = customer_id
        self.created: list = []

    async def find(self, name=None, customer_code=None, **kwargs):
        if self._name is None and self._customer_code is None:
            return None
        return types.SimpleNamespace(
            customer_id=self._customer_id,
            customer_code=self._customer_code,
            name=self._name,
            status="ACTIVE",
        )

    async def create(self, *, name, customer_code=None, status="ACTIVE"):
        customer = types.SimpleNamespace(
            customer_id=f"cust-new-{len(self.created) + 1}",
            customer_code=customer_code,
            name=name,
            status=status,
        )
        self.created.append(customer)
        return customer


class _POHeaderFieldRepo:
    def __init__(self) -> None:
        self.rows: list = []

    async def upsert(self, po_id: str, field_id: str, value: str):
        row = types.SimpleNamespace(id=field_id, po_id=po_id, field_id=field_id, field_value=value)
        self.rows.append(row)
        return row

    async def get_by_po(self, po_id: str):
        return [r for r in self.rows if r.po_id == po_id]

    async def get(self, **kwargs):
        return None


class _POLineItemRepo:
    def __init__(self) -> None:
        self.items: list = []
        self.fields: dict[str, list] = {}

    async def create_line_item(self, po_id: str):
        item = types.SimpleNamespace(po_line_item_id=str(len(self.items) + 1), po_id=po_id)
        self.items.append(item)
        return item

    async def get_line_items(self, po_id: str):
        return self.items

    async def upsert_field(self, po_line_item_id: str, field_id: str, value: str):
        self.fields.setdefault(po_line_item_id, []).append(types.SimpleNamespace(field_id=field_id, field_value=value))

    async def get_fields_by_line_item(self, po_line_item_id: str):
        return self.fields.get(po_line_item_id, [])

    async def get(self, **kwargs):
        return None


class _ProductRepo:
    async def find(self, sku=None, name=None, **kwargs):
        return None


class _EpisodicMemoryRepo:
    def __init__(self) -> None:
        self.records: list = []

    async def get(self, customer_id: str, field_id: str):
        return next((r for r in self.records if r.field_id == field_id), None)

    async def create(self, **kwargs):
        record = types.SimpleNamespace(
            id=f"mem-{len(self.records) + 1}",
            customer_id=kwargs.get("customer_id"),
            field_id=kwargs.get("field_id"),
            location_hint=kwargs.get("location_hint"),
            document_pattern=kwargs.get("document_pattern"),
            instruction=kwargs.get("instruction"),
            confidence=kwargs.get("confidence", 0.5),
            usage_count=1,
            success_count=0,
            failure_count=0,
        )
        self.records.append(record)
        return record

    async def update_pattern(self, memory_id: str, **kwargs):
        for record in self.records:
            if record.id == memory_id:
                record.location_hint = kwargs.get("location_hint", record.location_hint)
                record.document_pattern = kwargs.get("document_pattern", record.document_pattern)
                record.instruction = kwargs.get("instruction", record.instruction)
                return record
        return None


class _Bedrock:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    async def extract_document(self, document, prompt, *, content_type="application/pdf"):
        if self._fail:
            raise RuntimeError("ocr down")
        return {
            "fullText": (
                "PO No: PO-1001\n"
                "Customer: Acme Ltd.\n"
                "GSTIN: 29AAA0000000A1Z5\n"
                "Date: 2026-09-01\n"
                "Ship To: Acme Ltd.\n"
                "1 Main St, Mumbai, MH, India 400001\n"
                "Grand Total: 200.00\n"
                "Qty  Product        SKU     Rate    Amount\n"
                "2    Widget         SKU-1   100     200\n"
            ),
            "headerLines": [{"text": "PO No: PO-1001"}],
            "lineItemLines": [{"text": "2 Widget SKU-1 100 200"}],
        }


def _settings(max_retries: int = 3):
    return types.SimpleNamespace(
        extraction_max_retries=max_retries,
        extraction_min_evidence_score=0.6,
        extraction_min_evidence_sources=2,
        extraction_candidate_separation=0.1,
        extraction_validated_confidence=0.8,
        extraction_evaluation_concurrency=1,
        extraction_evaluation_batch_size=10,
        extraction_max_candidates_per_field=3,
        extraction_max_evaluations_total=100,
        extraction_evaluation_max_retries=1,
        extraction_evaluation_backoff_base=0.1,
        extraction_evaluation_backoff_mult=1.0,
        extraction_evaluation_backoff_max=0.1,
        extraction_no_progress_threshold_retries=0,
    )


class _ScriptedInnerAgent:
    def __init__(self, candidate_map: dict[str, list], validation_score: float = 0.9) -> None:
        self._candidate_map = candidate_map
        self._validation_score = validation_score

    async def ainvoke(self, payload: dict) -> dict:
        text = str(payload["messages"][0].content)
        if "Candidate value:" in text or "Candidates:" in text:
            return {
                "output": json.dumps(
                    {"field_name": "", "score": self._validation_score, "accepted": True, "reasons": ["ok"]}
                )
            }
        return json.dumps({"field_name": "", "candidates": []})


class _CandidateInnerAgent(_ScriptedInnerAgent):
    """Returns canned candidates keyed by 'Field: <name>' in the prompt."""

    def __init__(self, candidate_map: dict[str, list], validation_score: float = 0.9) -> None:
        super().__init__(candidate_map, validation_score)

    async def ainvoke(self, payload: dict) -> dict:
        text = str(payload["messages"][0].content)
        if "Candidate value:" in text or "Candidates:" in text:
            return {
                "output": json.dumps(
                    {"field_name": "", "score": self._validation_score, "accepted": True, "reasons": ["ok"]}
                )
            }
        if "Extract ALL line-item rows" in text:
            rows = [{"product_name": "Widget", "sku": "SKU-1", "quantity": 2, "unit_price": 100}]
            return {
                "output": json.dumps(
                    {
                        "field_name": "__LINE_ITEMS__",
                        "candidates": [{"value": json.dumps(rows), "source": "semantic", "location": "line_items"}],
                    }
                )
            }
        match = None
        for line in text.splitlines():
            if line.startswith("Field:"):
                match = line.split("Field:", 1)[1].strip()
                break
        candidates = self._candidate_map.get(match, [])
        return {"output": json.dumps({"field_name": match, "candidates": candidates})}


def _build_agent(monkeypatch: pytest.MonkeyPatch, *, candidate_map, validation_score=0.9, max_retries=3, customer=None):
    def fake_build(self, system_prompt, agent_key):  # noqa: ANN001
        if agent_key == "validation_agent":
            return _ScriptedInnerAgent(candidate_map, validation_score)
        return _CandidateInnerAgent(candidate_map, validation_score)

    monkeypatch.setattr(ExtractionAgent, "_build_inner_agent", fake_build)
    agent = ExtractionAgent(
        bedrock_client=_Bedrock(),
        chat_model=object(),
        settings=_settings(max_retries),
        customer_repository=_CustomerRepo(**customer or {}),
        field_definition_repository=_FieldDefinitionRepo(),
        po_header_field_repository=_POHeaderFieldRepo(),
        po_line_item_repository=_POLineItemRepo(),
        product_repository=_ProductRepo(),
        episodic_memory_repository=_EpisodicMemoryRepo(),
    )
    return agent


def _happy_header_candidates():
    header = {
        "po_number": [{"value": "PO-1001", "source": "semantic", "location": "header"}],
        "po_date": [{"value": "2026-09-01", "source": "semantic", "location": "header"}],
        "currency": [{"value": "INR", "source": "semantic", "location": "header"}],
        "ship_to": [{"value": "Acme Ltd.", "source": "semantic", "location": "header"}],
        "address_1": [{"value": "1 Main St", "source": "semantic", "location": "header"}],
        "address_2": [{"value": "Near Station", "source": "semantic", "location": "header"}],
        "city": [{"value": "Mumbai", "source": "semantic", "location": "header"}],
        "state": [{"value": "MH", "source": "semantic", "location": "header"}],
        "country": [{"value": "India", "source": "semantic", "location": "header"}],
        "zip": [{"value": "400001", "source": "semantic", "location": "header"}],
        "total_amount": [{"value": "200.00", "source": "semantic", "location": "header"}],
    }
    header["customer"] = [{"value": "Acme Ltd.", "source": "semantic", "location": "header"}]
    header["gst_no"] = [{"value": "29AAA0000000A1Z5", "source": "semantic", "location": "header"}]
    return header


async def test_happy_path_extracts_persists_and_reconstructs(
    monkeypatch: pytest.MonkeyPatch,
):
    agent = _build_agent(
        monkeypatch,
        candidate_map=_happy_header_candidates(),
        customer={"name": "Acme Ltd.", "gst_no": "29AAA0000000A1Z5", "customer_id": "cust-1"},
    )
    result = await agent.invoke_agent({"run_id": "r1", "thread_id": "t1", "file_bytes": b"pdf", "po_id": "po-1"})
    assert result["status"] == "RUNNING"
    assert result["extraction_result"]["passed"] is True

    extracted_po = result["extracted_po"]
    assert extracted_po["po_number"] == "PO-1001"
    assert extracted_po["customer"] == "Acme Ltd."
    assert extracted_po["city"] == "Mumbai"
    assert extracted_po["line_items"][0]["product_name"] == "Widget"
    assert result["po_total_amount"] == 200.0

    persist_header = agent._repo["po_header_field"]
    assert len(persist_header.rows) == len(_HEADER_FIELD_NAMES)  # every header field persisted


async def test_customer_not_found_pauses_for_creation(monkeypatch: pytest.MonkeyPatch):
    agent = _build_agent(monkeypatch, candidate_map=_happy_header_candidates(), customer={})
    result = await agent.invoke_agent({"run_id": "r1", "file_bytes": b"pdf", "po_id": "po-1"})
    assert result["status"] == "RUNNING"
    interrupts = result["__interrupt__"]
    assert len(interrupts) == 1
    hint = interrupts[0].value
    assert hint["question"] == "create_customer"
    assert hint["run_id"] == "r1"
    context = hint["context"]
    assert context["customer_name"] == "Acme Ltd."
    assert context["customer_gst_no"] == "29AAA0000000A1Z5"
    assert context["customer_code"] is None
    assert context["candidates"]


def _compile_parent(agent) -> Any:
    """Wrap the extraction agent as a single parent-graph node with a checkpointer.

    Mirrors the production topology (POOrchestrator._extraction_node) so the
    interrupt fires inside an invaded parent and resume feeds the value back.
    """
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    from app.orchestrator_service.extraction_state import ExtractionState

    async def run_extraction(state):
        return await agent.invoke_agent(state)

    graph = StateGraph(ExtractionState)
    graph.add_node("extraction", run_extraction)
    graph.add_edge(START, "extraction")
    graph.add_edge("extraction", END)
    return graph.compile(checkpointer=InMemorySaver())


async def test_customer_creation_approved_creates_and_proceeds(monkeypatch: pytest.MonkeyPatch):
    customer_repo = _CustomerRepo()
    agent = _build_agent(monkeypatch, candidate_map=_happy_header_candidates(), customer={})
    agent._repo["customer"] = customer_repo
    parent = _compile_parent(agent)
    config = {"configurable": {"thread_id": "t-cust-approve"}}

    first = await parent.ainvoke(
        {"run_id": "r1", "thread_id": "t-cust-approve", "file_bytes": b"pdf", "po_id": "po-1"}, config
    )
    assert first["__interrupt__"][0].value["question"] == "create_customer"

    from langgraph.types import Command

    second = await parent.ainvoke(Command(resume={"decision": "APPROVE", "changes": {}}), config)
    assert second.get("__interrupt__") is None
    assert second["status"] == "RUNNING"
    assert second["extraction_result"]["passed"] is True
    assert len(customer_repo.created) == 1
    created = customer_repo.created[0]
    assert created.name == "Acme Ltd."
    assert created.customer_code.startswith("CUST-")


async def test_customer_creation_edited_uses_human_changes(monkeypatch: pytest.MonkeyPatch):
    customer_repo = _CustomerRepo()
    agent = _build_agent(monkeypatch, candidate_map=_happy_header_candidates(), customer={})
    agent._repo["customer"] = customer_repo
    parent = _compile_parent(agent)
    config = {"configurable": {"thread_id": "t-cust-edit"}}

    await parent.ainvoke({"run_id": "r1", "thread_id": "t-cust-edit", "file_bytes": b"pdf", "po_id": "po-1"}, config)

    from langgraph.types import Command

    second = await parent.ainvoke(
        Command(
            resume={"decision": "EDIT", "changes": {"customer_name": "Acme Pvt Ltd", "customer_code": "CUST-EDIT"}}
        ),
        config,
    )
    assert second.get("__interrupt__") is None
    assert second["status"] == "RUNNING"
    assert len(customer_repo.created) == 1
    assert customer_repo.created[0].name == "Acme Pvt Ltd"
    assert customer_repo.created[0].customer_code == "CUST-EDIT"


async def test_customer_creation_rejected_fails_run(monkeypatch: pytest.MonkeyPatch):
    customer_repo = _CustomerRepo()
    agent = _build_agent(monkeypatch, candidate_map=_happy_header_candidates(), customer={})
    agent._repo["customer"] = customer_repo
    parent = _compile_parent(agent)
    config = {"configurable": {"thread_id": "t-cust-reject"}}

    await parent.ainvoke({"run_id": "r1", "thread_id": "t-cust-reject", "file_bytes": b"pdf", "po_id": "po-1"}, config)

    from langgraph.types import Command

    second = await parent.ainvoke(Command(resume={"decision": "REJECT", "reason": "not our customer"}), config)
    assert second.get("__interrupt__") is None
    assert second["status"] == "FAILED"
    assert second["extraction_error_code"] == "CUSTOMER_IDENTIFICATION_FAILED"
    assert customer_repo.created == []


async def test_document_processing_failure(monkeypatch: pytest.MonkeyPatch):
    candidate_map = {"customer": [], "gst_no": []}

    def fake_build(self, system_prompt, agent_key):  # noqa: ANN001
        return _CandidateInnerAgent(candidate_map, 0.9)

    monkeypatch.setattr(ExtractionAgent, "_build_inner_agent", fake_build)
    agent = ExtractionAgent(
        bedrock_client=_Bedrock(fail=True),
        chat_model=object(),
        settings=_settings(),
        customer_repository=_CustomerRepo(name="Acme Ltd."),
        field_definition_repository=_FieldDefinitionRepo(),
        po_header_field_repository=_POHeaderFieldRepo(),
        po_line_item_repository=_POLineItemRepo(),
        product_repository=_ProductRepo(),
        episodic_memory_repository=_EpisodicMemoryRepo(),
    )
    result = await agent.invoke_agent({"run_id": "r1", "file_bytes": b"pdf"})
    assert result["status"] == "FAILED"
    assert result["extraction_error_code"] == "DOCUMENT_PROCESSING_FAILED"


async def test_recovery_exhausts_with_validation_failure(monkeypatch: pytest.MonkeyPatch):
    # Customer resolves, but no valid candidates for other header fields.
    candidate_map = {
        "customer": [{"value": "Acme Ltd.", "source": "semantic", "location": "header"}],
        "gst_no": [{"value": "29AAA0000000A1Z5", "source": "semantic", "location": "header"}],
    }
    agent = _build_agent(
        monkeypatch,
        candidate_map=candidate_map,
        validation_score=0.1,
        max_retries=1,
        customer={"name": "Acme Ltd."},
    )
    result = await agent.invoke_agent({"run_id": "r1", "file_bytes": b"pdf"})
    assert result["status"] == "FAILED"
    assert result["extraction_error_code"] == "RECOVERY_EXHAUSTED"


class _CaptureInnerAgent:
    def __init__(self) -> None:
        self.payload: dict | None = None

    async def ainvoke(self, payload: dict) -> dict:
        self.payload = payload
        return {"output": json.dumps({"field_name": "", "candidates": []})}


async def test_create_customer_tool_generates_code_and_honours_override(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, candidate_map={})
    await agent._ensure_tools()
    create = agent._tool_map["create_customer"]

    auto = await create.ainvoke({"name": "  New Corp  "})
    assert auto["created"] is True
    assert auto["customer"]["name"] == "New Corp"
    assert auto["customer"]["customer_code"].startswith("CUST-")
    assert auto["customer"]["status"] == "ACTIVE"

    explicit = await create.ainvoke({"name": "New Corp", "customer_code": "X-9"})
    assert explicit["customer"]["customer_code"] == "X-9"


async def test_create_customer_tool_reports_insert_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingRepo(_CustomerRepo):
        async def create(self, *, name, customer_code=None, status="ACTIVE"):
            raise RuntimeError("duplicate code")

    agent = _build_agent(monkeypatch, candidate_map={})
    agent._repo["customer"] = _FailingRepo()
    await agent._ensure_tools()
    result = await agent._tool_map["create_customer"].ainvoke({"name": "New Corp"})
    assert result["created"] is False
    assert "duplicate code" in result["reason"]


def test_memory_yaml_parses() -> None:
    data = load_memory()
    assert "procedural" in data and "semantic" in data and "line_item" in data
    assert isinstance(data["procedural"]["po_number"], list)
    labels = data["semantic"]["po_number"]["labels"]
    assert "PO#" in labels and "Purchase Order" in labels
    assert data["line_item"]["procedure"]


async def test_load_memories_uses_static_baseline_and_episodic_override(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, candidate_map={})
    await agent._ensure_tools()

    result = await agent._node_load_memories({"customer_id": "cust-1"})
    memories = {m["field"]: m["memory"] for m in result["memories"]}
    assert "po_number" in memories and "product_name" in memories

    po_number = memories["po_number"]
    assert "Look after labels" in po_number["instruction"]  # procedural steps from memory.yaml
    assert "PO No" in po_number["location_hint"]  # semantic labels from memory.yaml

    await agent._repo["episodic_memory"].create(
        customer_id="cust-1",
        field_id="0",  # po_number is the first definition
        location_hint="PO:",
        instruction="Prefer the bold PO header",
        confidence=0.9,
    )
    result = await agent._node_load_memories({"customer_id": "cust-1"})
    memories = {m["field"]: m["memory"] for m in result["memories"]}
    merged = memories["po_number"]
    assert "Prefer the bold PO header" in merged["instruction"]  # episodic appended to procedural
    assert merged["location_hint"] == "PO:"  # episodic hint overrides semantic labels


async def test_line_item_agent_injects_memory_procedure_and_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _build_agent(monkeypatch, candidate_map={})
    capture = _CaptureInnerAgent()
    agent._candidate_agent = capture

    await agent._run_line_item_candidate_agent([], "LINE ITEMS SECTION\n2 Widget 100")

    text = str(capture.payload["messages"][0].content)
    assert "Split the line-items section into rows" in text  # line_item.procedure
    assert "Item" in text and "SKU" in text and "Qty" in text  # semantic labels for line-item fields


def test_last_message_text_reads_langchain_messages_payload() -> None:
    """langchain returns {"messages": [...]} with no "output" key."""
    from langchain_core.messages import AIMessage, HumanMessage

    response = {
        "messages": [
            HumanMessage(content="prompt"),
            AIMessage(content=""),
            AIMessage(content='{"field_name": "po_number", "candidates": []}'),
        ]
    }

    assert ExtractionAgent._last_message_text(response) == '{"field_name": "po_number", "candidates": []}'


def test_last_message_text_supports_content_blocks_and_legacy_shapes() -> None:
    from langchain_core.messages import AIMessage

    assert (
        ExtractionAgent._last_message_text(
            {"messages": [AIMessage(content=[{"type": "text", "text": "a"}, {"text": "b"}])]}
        )
        == "a\nb"
    )
    assert ExtractionAgent._last_message_text({"output": "from-output"}) == "from-output"
    assert ExtractionAgent._last_message_text("raw-string") == "raw-string"
    assert ExtractionAgent._last_message_text(None) == ""


def test_inner_agents_are_built_without_repository_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """Binding repo tools made the model answer with tool calls instead of the requested JSON."""
    captured: dict = {}

    def fake_create_agent(model, tools=None, **kwargs):  # noqa: ANN001, ANN003
        captured["tools"] = tools
        return object()

    monkeypatch.setattr("app.agents.extraction_agent.create_agent", fake_create_agent)
    agent = ExtractionAgent(
        bedrock_client=object(),
        chat_model=object(),
        settings=_settings(),
    )

    assert agent._build_inner_agent("system", "candidate_generator") is not None
    assert captured["tools"] == []

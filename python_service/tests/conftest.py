"""Shared test fixtures: Postgres engine, tables, and stub graph components.

Both the repository layer and LangGraph's ``AsyncPostgresSaver`` require a
real Postgres database. Point ``TEST_DATABASE_URL`` at one (defaults to a
local ``poin_test`` database).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.agents.base_agent import BaseAgent
from app.models.domain import ValidationBranchResult
from app.repositories import database
from app.repositories.schemas import orm  # noqa: F401  (registers all tables on Base.metadata)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sarvesh:1234@localhost:5432/poin_test",
)


def _psycopg_url(database_url: str) -> str:
    """Convert a SQLAlchemy asyncpg URL into a psycopg-compatible one."""
    return database_url.replace("+asyncpg", "", 1)


@pytest.fixture
async def postgres_env():
    """Configure the Postgres engine and create all tables."""
    database.configure_engine(TEST_DATABASE_URL)
    await database.create_all()
    yield
    await database.drop_all()
    await database.dispose()


@pytest.fixture
async def checkpointer(postgres_env):
    """An AsyncPostgresSaver connected to the test database."""
    conn = await AsyncConnection.connect(
        _psycopg_url(TEST_DATABASE_URL),
        autocommit=True,
        row_factory=dict_row,
    )
    saver = AsyncPostgresSaver(conn)
    await saver.setup()
    yield saver
    await conn.close()


# ---------------------------------------------------------------- stubs ----


class _StubExtraction(BaseAgent):
    name = "extraction"

    def __init__(self, po: dict, *, fail: bool = False) -> None:
        super().__init__()
        self._po = po
        self._fail = fail
        #: How many times the extraction subgraph ran; a HITL edit must not
        #: re-extract the document, so tests assert this stays at 1.
        self.calls = 0

    def create_agent(self) -> Any:
        return None

    async def invoke_agent(self, state, **kwargs: Any) -> dict[str, Any]:
        return await self.execute(state)

    async def execute(self, state) -> dict[str, Any]:
        self.calls += 1
        if self._fail:
            return {
                "current_step": "quality_gate",
                "status": "FAILED",
                "extraction_error": "could not read the document",
                "extraction_error_code": "DOCUMENT_PROCESSING_FAILED",
                "file_bytes": None,
            }
        items = self._po.get("line_items") or []
        total = round(sum(float(i["unit_price"]) * float(i["quantity"]) for i in items), 2)
        return {
            "extracted_po": self._po,
            "po_total_amount": total,
            "customer_id": "cust-stub-1",
            "extracted_header_fields": [],
            "extracted_line_item_fields": [],
            "extraction_result": {"passed": True},
            "current_step": "extraction",
            "status": "RUNNING",
            "file_bytes": None,
        }


def _stub_branch_result(branch: str, passed: bool = True, issues: list[dict] | None = None) -> dict:
    return {"branch": branch, "passed": passed, "issues": issues or [], "details": {}}


class _StubVerifier(BaseAgent):
    """Emits the three-branch verification result the aggregator would produce."""

    name = "verification"

    def __init__(self, blocking_customer: str = "Bad Co.", *, failing_branch: str | None = None) -> None:
        super().__init__()
        self._blocking_customer = blocking_customer
        self._failing_branch = failing_branch
        #: How many times verification ran, across invoke and HITL resumes.
        self.calls = 0

    def create_agent(self) -> Any:
        return None

    async def invoke_agent(self, state, **kwargs: Any) -> dict[str, Any]:
        return await self.execute(state)

    async def execute(self, state) -> dict[str, Any]:
        from app.agents.verifier_agent import VerifierAgent

        self.calls += 1
        po = state.get("extracted_po") or {}
        issues: list[dict] = []
        if po.get("customer") == self._blocking_customer:
            issues.append({"code": "PRICE_VALIDATION_FAILED", "message": "price off", "severity": "error"})

        branches = [
            _stub_branch_result("header"),
            _stub_branch_result("line_item"),
            _stub_branch_result("commercial"),
        ]
        if issues:
            branches[1] = _stub_branch_result("line_item", passed=False, issues=issues)
        if self._failing_branch is not None:
            index = {"header": 0, "line_item": 1, "commercial": 2}[self._failing_branch]
            branches[index] = {
                "branch": self._failing_branch,
                "passed": False,
                "issues": [
                    {
                        "code": "VALIDATION_BRANCH_FAILED",
                        "message": "validator unavailable",
                        "severity": "error",
                        "details": {"branch": self._failing_branch},
                    }
                ],
                "details": {},
            }

        result = VerifierAgent._aggregate(
            state,
            [ValidationBranchResult.model_validate(branch) for branch in branches],
        )
        payload = result.model_dump()
        blocking = result.blocking_issues
        return {
            "verification_result": payload,
            "criteria_met": result.criteria_met,
            "hitl_required": not result.criteria_met,
            "hitl_context": VerifierAgent._hitl_context(state, blocking, result.warnings)
            if not result.criteria_met
            else None,
            "current_step": "verification",
            "status": "RUNNING",
        }


class _StubSales(BaseAgent):
    name = "sales"

    def create_agent(self) -> Any:
        return None

    async def invoke_agent(self, state, **kwargs: Any) -> dict[str, Any]:
        return await self.execute(state)

    async def execute(self, state) -> dict[str, Any]:
        return {
            "po_id": str(uuid.uuid4()),
            "sale_id": str(uuid.uuid4()),
            "sale_status": "CREATED",
            "current_step": "sales",
            "status": "COMPLETED",
        }


class _StubInvoice(BaseAgent):
    name = "invoice"

    def create_agent(self) -> Any:
        return None

    async def invoke_agent(self, state, **kwargs: Any) -> dict[str, Any]:
        return await self.execute(state)

    async def execute(self, state) -> dict[str, Any]:
        return {
            "invoice_id": str(uuid.uuid4()),
            "invoice_number": "INV-20260912-0001",
            "invoice_status": "GENERATED",
            "s3_url": "https://bucket/invoices/x.pdf",
            "current_step": "invoice",
            "status": "RUNNING",
        }


@pytest.fixture
def stub_extraction_agent() -> BaseAgent:
    return _StubExtraction(
        {
            "po_number": "PO-1001",
            "customer": "Acme Ltd.",
            "gst_no": "GST001",
            "ship_to": "Acme Ltd.",
            "address_1": "1 Main St",
            "city": "Mumbai",
            "state": "MH",
            "country": "India",
            "zip": "400001",
            "line_items": [{"sku": "SKU-1", "product_name": "Widget", "quantity": 2, "unit_price": 100}],
        }
    )


@pytest.fixture
def stub_bad_extraction_agent() -> BaseAgent:
    return _StubExtraction(
        {
            "po_number": "PO-2001",
            "customer": "Bad Co.",
            "gst_no": "GST-BAD",
            "line_items": [{"sku": "SKU-9", "product_name": "Gadget", "quantity": 1, "unit_price": 999}],
        }
    )


@pytest.fixture
def stub_failed_extraction_agent() -> BaseAgent:
    """Extraction fails outright; the verifier must never see this run."""
    return _StubExtraction({}, fail=True)


@pytest.fixture
def stub_verifier_agent() -> BaseAgent:
    return _StubVerifier()


@pytest.fixture
def stub_sales_agent() -> BaseAgent:
    return _StubSales()


@pytest.fixture
def stub_invoice_agent() -> BaseAgent:
    return _StubInvoice()

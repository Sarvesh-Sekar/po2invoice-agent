"""API integration tests: endpoints + HITL flow with stubbed graph components."""

from __future__ import annotations

import time
import uuid

import httpx
import jwt
import pytest

from app.agents.base_agent import BaseAgent
from app.config.settings import Settings
from app.containers import AppContainer
from app.main import create_app, lifespan
from app.repositories import database
from tests.conftest import TEST_DATABASE_URL, _StubExtraction, _StubInvoice, _StubSales, _StubVerifier

TEST_JWT_SECRET = "test-jwt-secret"

VALID_USER = {
    "sub": "user-123",
    "email": "ops@example.com",
    "name": "Ops User",
    "role": "operator",
    "active": True,
}


def _signed_token(*, secret: str = TEST_JWT_SECRET, claims: dict | None = None, expires_in: int = 900) -> str:
    payload = {**VALID_USER, "iat": int(time.time()), "exp": int(time.time()) + expires_in}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def _auth_headers(token: str | None = None) -> dict[str, str]:
    token = token or _signed_token()
    return {"Authorization": f"Bearer {token}"}


async def _prepare(
    *,
    extraction_agent: BaseAgent | None = None,
    verifier_agent: BaseAgent | None = None,
    sales_agent: BaseAgent | None = None,
    invoice_agent: BaseAgent | None = None,
    require_auth: bool = True,
    jwt_secret: str | None = TEST_JWT_SECRET,
    database_url: str | None = None,
):
    settings = Settings(
        database_url=database_url or TEST_DATABASE_URL,
        internal_api_key="test-internal-key",
        require_auth=require_auth,
        jwt_secret=jwt_secret,
        environment="test",
    )
    database.configure_engine(settings.database_url)
    await database.create_all()

    container = AppContainer(settings)
    for attr, agent in (
        ("extraction_agent", extraction_agent),
        ("verifier_agent", verifier_agent),
        ("sales_agent", sales_agent),
        ("invoice_agent", invoice_agent),
    ):
        if agent is not None:
            setattr(container, attr, agent)

    app = create_app(settings)
    app.state.container = container
    return app


@pytest.fixture
async def server():
    app = await _prepare(
        extraction_agent=_StubExtraction(
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
        ),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


def _post_po(
    server: httpx.AsyncClient,
    filename: str = "po-test.pdf",
    token: str | None = None,
) -> httpx.Response:
    return server.post(
        "/api/v1/agents/purchase-orders/process",
        headers=_auth_headers(token),
        files={"file": (filename, b"%PDF-1.4 fake purchase order", "application/pdf")},
    )


def _get_run(server: httpx.AsyncClient, run_id: str, token: str | None = None) -> httpx.Response:
    return server.get(f"/api/v1/agents/runs/{run_id}", headers=_auth_headers(token))


def _post_decision(
    server: httpx.AsyncClient,
    run_id: str,
    *,
    decision: str = "APPROVE",
    token: str | None = None,
) -> httpx.Response:
    return server.post(
        f"/api/v1/agents/purchase-orders/{run_id}/decision",
        headers=_auth_headers(token),
        json={"decision": decision, "reason": "human approved"},
    )


async def test_health(server):
    response = await server.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_process_po_happy_path_completes(server):
    response = await _post_po(server)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["sale_id"] is not None
    assert body["workflow"] == "PURCHASE_ORDER"


async def test_process_po_rejects_bad_extension(server):
    response = await _post_po(server, filename="po.exe")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PO_FILE_INVALID"


async def test_request_validation_error_shape(server):
    response = await server.post(
        "/api/v1/agents/purchase-orders/process",
        headers=_auth_headers(),
        json={"not_a_file": True},
    )
    assert response.status_code == 422
    assert response.json()["success"] is False


async def test_agent_routes_require_authentication():
    app = await _prepare(
        extraction_agent=_StubExtraction({"po_number": "PO-1001", "customer": "Acme", "line_items": []}),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        no_token = await client.post(
            "/api/v1/agents/purchase-orders/process",
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert no_token.status_code == 401
        assert no_token.json()["error"]["code"] == "UNAUTHORIZED"

        bad_scheme = await client.post(
            "/api/v1/agents/purchase-orders/process",
            headers={"Authorization": "Basic abc123"},
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert bad_scheme.status_code == 401

        get_run = await client.get(f"/api/v1/agents/runs/{uuid.uuid4()}")
        assert get_run.status_code == 401

        decision = await client.post(
            f"/api/v1/agents/purchase-orders/{uuid.uuid4()}/decision",
            json={"decision": "APPROVE"},
        )
        assert decision.status_code == 401


async def test_agent_routes_reject_invalid_token():
    app = await _prepare(
        extraction_agent=_StubExtraction({"po_number": "PO-1001", "customer": "Acme", "line_items": []}),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        garbage = await client.post(
            "/api/v1/agents/purchase-orders/process",
            headers={"Authorization": "Bearer not-a-real-token"},
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert garbage.status_code == 401

        wrong_secret = await client.post(
            "/api/v1/agents/purchase-orders/process",
            headers=_auth_headers(token=_signed_token(secret="another-secret")),
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert wrong_secret.status_code == 401

        expired = _signed_token(claims={"exp": int(time.time()) - 60})
        stale = await client.post(
            "/api/v1/agents/purchase-orders/process",
            headers={"Authorization": f"Bearer {expired}"},
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert stale.status_code == 401

        missing_sub = await client.post(
            "/api/v1/agents/purchase-orders/process",
            headers=_auth_headers(token=_signed_token(claims={"sub": None})),
            files={"file": ("po.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert missing_sub.status_code == 401


async def test_agent_routes_allow_when_auth_disabled():
    app = await _prepare(
        extraction_agent=_StubExtraction({"po_number": "PO-1001", "customer": "Acme", "line_items": []}),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
        require_auth=False,
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await _post_po(client)
        assert response.status_code == 202


def _go_style_token(secret: str = TEST_JWT_SECRET) -> str:
    """Mint a token with exactly the claims the Go service's TokenManager issues.

    Mirrors golang_service/internal/googleauth/token.go::buildToken: a UUID
    ``sub``, ``token_type=access``, no ``active`` claim, plus ``iss``/``iat``/``exp``.
    """
    now = int(time.time())
    payload = {
        "iss": "",
        "sub": str(uuid.uuid4()),
        "email": "ops@acme.com",
        "name": "Ops User",
        "role": "operator",
        "token_type": "access",
        "iat": now,
        "exp": now + 900,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def test_agent_routes_accept_go_issued_token():
    """The frontend sends tokens minted by the Go service; Python must accept them."""
    token = _go_style_token()
    app = await _prepare(
        extraction_agent=_StubExtraction({"po_number": "PO-1001", "customer": "Acme", "line_items": []}),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await _post_po(client, token=token)
        assert response.status_code == 202
        assert response.json()["status"] == "COMPLETED"


async def test_process_po_interrupts_for_hitl_then_approve():
    bad = _StubExtraction(
        {
            "po_number": "PO-2001",
            "customer": "Bad Co.",
            "gst_no": "GST-BAD",
            "line_items": [{"sku": "SKU-9", "product_name": "Gadget", "quantity": 1, "unit_price": 999}],
        }
    )
    app = await _prepare(
        extraction_agent=bad,
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        first = await _post_po(client)
        assert first.status_code == 202
        run_id = first.json()["run_id"]
        assert first.json()["status"] == "WAITING_FOR_HUMAN"
        assert first.json()["hitl"] is not None

        fetched = await _get_run(client, run_id)
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "WAITING_FOR_HUMAN"

        decision = await _post_decision(client, run_id, decision="APPROVE")
        assert decision.status_code == 202
        assert decision.json()["status"] == "COMPLETED"
        assert decision.json()["sale_id"] is not None


async def test_unknown_run_returns_404(server):
    response = await _get_run(server, str(uuid.uuid4()))
    assert response.status_code == 404


async def test_decision_on_completed_run_conflicts(server):
    processed = await _post_po(server)
    run_id = processed.json()["run_id"]
    decision = await _post_decision(server, run_id, decision="APPROVE")
    assert decision.status_code == 409


async def test_internal_sale_delivered_is_idempotent(server):
    payload = {"sale_id": str(uuid.uuid4()), "event": "SALE_DELIVERED", "idempotency_key": "evt-1"}
    headers = {"X-Internal-API-Key": "test-internal-key"}

    no_key = await server.post("/api/v1/internal/events/sale-delivered", json=payload)
    assert no_key.status_code == 401

    bad_key = await server.post(
        "/api/v1/internal/events/sale-delivered",
        headers={"X-Internal-API-Key": "wrong-key"},
        json=payload,
    )
    assert bad_key.status_code == 401
    assert bad_key.json()["error"]["code"] == "UNAUTHORIZED"

    first = await server.post("/api/v1/internal/events/sale-delivered", json=payload, headers=headers)
    assert first.status_code == 202
    assert first.json()["status"] == "COMPLETED"
    assert first.json()["invoice_id"] is not None

    duplicate = await server.post("/api/v1/internal/events/sale-delivered", json=payload, headers=headers)
    assert duplicate.status_code == 202
    assert duplicate.json()["run_id"] == first.json()["run_id"]


async def test_internal_event_accepts_legacy_go_event_spelling():
    """The Go client historically sent `event: "sale-delivered"`; Python must accept it."""
    payload = {"sale_id": str(uuid.uuid4()), "event": "sale-delivered", "idempotency_key": "evt-legacy"}
    headers = {"X-Internal-API-Key": "test-internal-key"}

    app = await _prepare(
        extraction_agent=_StubExtraction({"po_number": "PO-1", "customer": "Acme", "line_items": []}),
        verifier_agent=_StubVerifier(),
        sales_agent=_StubSales(),
        invoice_agent=_StubInvoice(),
    )
    async with (
        lifespan(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post("/api/v1/internal/events/sale-delivered", json=payload, headers=headers)
        assert response.status_code == 202
        assert response.json()["status"] == "COMPLETED"

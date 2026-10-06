"""AgentService: idempotent handling of SALE_DELIVERED invoice events.

The sale relationship, not the idempotency key, is what makes an invoice unique,
so both the key replay and the fresh-key redelivery paths are covered.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config.settings import Settings
from app.models.requests.internal_event import SaleDeliveredEvent
from app.services.agent_service import AgentService

_ABSENT = object()


def _event(sale_id: str | None = None, key: object = _ABSENT) -> SaleDeliveredEvent:
    """``key`` is passed through verbatim so blank/absent keys stay absent."""
    return SaleDeliveredEvent(
        sale_id=sale_id or str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()) if key is _ABSENT else key,  # type: ignore[arg-type]
    )


def _service(existing_invoice: object | None = None) -> tuple[AgentService, AsyncMock, AsyncMock]:
    """Build the service with an invoice repo whose ``get_by_sale`` returns
    ``existing_invoice``. Child mocks must be configured explicitly: an
    ``AsyncMock`` attribute would otherwise return a truthy mock and look like
    a duplicate invoice."""
    repo = AsyncMock()
    invoices = AsyncMock()
    invoices.get_by_sale.return_value = existing_invoice
    orchestrator = AsyncMock()
    # `invoke` is what AgentService awaits; `invoke_agent` would leave a
    # coroutine in `result` and trip the finalization branch.
    orchestrator.invoke.return_value = {"invoice_id": str(uuid.uuid4()), "status": "RUNNING"}
    service = AgentService(
        po_orchestrator=orchestrator,
        invoice_orchestrator=orchestrator,
        agent_run_repository=repo,
        settings=Settings(environment="test", internal_api_key="k", jwt_secret="s"),
        invoice_repository=invoices,
    )
    return service, repo, invoices


async def test_replayed_key_returns_the_original_run_without_regenerating():
    prior = SimpleNamespace(
        run_id=uuid.uuid4(),
        workflow="INVOICE",
        status="COMPLETED",
        current_step="invoice",
        po_id=None,
        sale_id=uuid.uuid4(),
        invoice_id=uuid.uuid4(),
        hitl_context=None,
    )
    service, repo, invoices = _service()
    repo.get_by_idempotency_key.return_value = prior
    event = _event(key="stable-key")

    response = await service.handle_sale_delivered(event)
    response2 = await service.handle_sale_delivered(event)

    assert response.run_id == str(prior.run_id)
    assert response2.run_id == str(prior.run_id)
    # The invoice lookup is the second line of defence and must not even be reached.
    invoices.get_by_sale.assert_not_called()


async def test_fresh_key_for_a_sale_that_already_has_an_invoice_is_a_duplicate():
    """A redelivery with a new key must not raise a second invoice."""
    sale_id = str(uuid.uuid4())
    existing_invoice = SimpleNamespace(invoice_id=uuid.uuid4(), po_id=uuid.uuid4())
    service, repo, invoices = _service(existing_invoice)
    repo.get_by_idempotency_key.return_value = None
    repo.get_by_invoice_id.return_value = None

    response = await service.handle_sale_delivered(_event(sale_id=sale_id, key="new-key"))

    assert response.invoice_id == str(existing_invoice.invoice_id)
    assert response.status == "COMPLETED"
    assert response.sale_id == sale_id
    # Nothing new was created and the orchestrator never ran.
    repo.create.assert_not_called()
    service._invoice.invoke.assert_not_called()


async def test_duplicate_invoice_prefers_the_original_run_id():
    sale_id = str(uuid.uuid4())
    existing_invoice = SimpleNamespace(invoice_id=uuid.uuid4(), po_id=uuid.uuid4())
    prior = SimpleNamespace(
        run_id=uuid.uuid4(),
        workflow="INVOICE",
        status="COMPLETED",
        current_step="invoice",
        po_id=None,
        sale_id=uuid.UUID(sale_id),
        invoice_id=existing_invoice.invoice_id,
        hitl_context=None,
    )
    service, repo, invoices = _service(existing_invoice)
    repo.get_by_idempotency_key.return_value = None
    repo.get_by_invoice_id.return_value = prior

    response = await service.handle_sale_delivered(_event(sale_id=sale_id, key="another-new-key"))

    assert response.run_id == str(prior.run_id)
    assert response.invoice_id == str(existing_invoice.invoice_id)


def _configure_run(repo: AsyncMock, service: AgentService, invoice_id: str) -> None:
    """Configure the repository/orchestrator for a first-time, passing run."""
    repo.create.return_value = SimpleNamespace(
        run_id=uuid.uuid4(),
        workflow="INVOICE",
        status="RUNNING",
        current_step="queued",
        po_id=None,
        sale_id=None,
        invoice_id=None,
        hitl_context=None,
    )
    repo.update_status.return_value = SimpleNamespace(
        run_id=uuid.uuid4(),
        workflow="INVOICE",
        status="COMPLETED",
        current_step="invoice",
        po_id=None,
        sale_id=uuid.uuid4(),
        invoice_id=uuid.UUID(invoice_id),
        hitl_context=None,
    )
    service._invoice.invoke.return_value = {"invoice_id": invoice_id, "status": "RUNNING"}


async def test_first_delivery_still_runs_the_workflow():
    service, repo, invoices = _service(None)
    repo.get_by_idempotency_key.return_value = None
    invoice_id = str(uuid.uuid4())
    _configure_run(repo, service, invoice_id)

    response = await service.handle_sale_delivered(_event())

    assert response.invoice_id == invoice_id
    invoices.get_by_sale.assert_awaited_once()
    service._invoice.invoke.assert_awaited_once()


async def test_invoice_run_finalizes_at_step_invoice_not_message():
    """`current_step` is observable state; messaging no longer exists."""
    service, repo, invoices = _service(None)
    repo.get_by_idempotency_key.return_value = None
    _configure_run(repo, service, str(uuid.uuid4()))

    await service.handle_sale_delivered(_event())

    _, kwargs = repo.update_status.call_args
    assert kwargs["current_step"] == "invoice"
    assert kwargs["status"] == "COMPLETED"


@pytest.mark.parametrize("key", ["", "   ", None])
async def test_blank_idempotency_key_falls_back_to_sale_id(key):
    """The sale itself is the stable key when the client sends none."""
    service, repo, invoices = _service(None)
    repo.get_by_idempotency_key.return_value = None
    _configure_run(repo, service, str(uuid.uuid4()))
    sale_id = str(uuid.uuid4())

    await service.handle_sale_delivered(_event(sale_id=sale_id, key=key))

    invoices.get_by_sale.assert_awaited_once_with(sale_id)
    assert repo.create.await_args.kwargs["idempotency_key"] == f"sale:{sale_id}"

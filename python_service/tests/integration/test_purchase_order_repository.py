"""DB-backed tests for the atomic PURCHASE_ORDERS + extracted-field write."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.repositories import database
from app.repositories.repositories.field_definition_repository import FieldDefinitionRepository
from app.repositories.repositories.po_field_repository import POHeaderFieldRepository, POLineItemRepository
from app.repositories.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.schemas.orm.po_fields import POHeaderField
from app.repositories.schemas.orm.purchase_orders import PurchaseOrder


async def _count(model) -> int:
    factory = database.get_session_factory()
    async with factory() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())


@pytest.fixture
def repos(postgres_env):
    factory = database.get_session_factory()
    return (
        PurchaseOrderRepository(factory),
        FieldDefinitionRepository(factory),
        POHeaderFieldRepository(factory),
        POLineItemRepository(factory),
    )


async def test_create_with_fields_writes_all_rows(postgres_env, repos) -> None:
    po_repo, def_repo, header_repo, line_repo = repos
    po_number = await def_repo.create(field_name="po_number")
    sku = await def_repo.create(field_name="sku")
    quantity = await def_repo.create(field_name="quantity")

    po, line_item_ids = await po_repo.create_with_fields(
        customer_id=None,
        s3_url="https://bucket/po.pdf",
        header_fields=[(str(po_number.field_id), "PO-1001")],
        line_items=[[(str(sku.field_id), "SKU-1"), (str(quantity.field_id), "2")]],
    )

    stored = await po_repo.get(str(po.po_id))
    assert stored is not None
    assert stored.s3_url == "https://bucket/po.pdf"

    header_rows = await header_repo.get_by_po(str(po.po_id))
    assert [(r.field_id, r.field_value) for r in header_rows] == [(str(po_number.field_id), "PO-1001")]

    items = await line_repo.get_line_items(str(po.po_id))
    assert len(items) == 1
    assert items[0].product_id is None
    assert line_item_ids == [str(items[0].po_line_item_id)]

    fields = await line_repo.get_fields_by_line_item(str(items[0].po_line_item_id))
    assert {(f.field_id, f.field_value) for f in fields} == {
        (str(sku.field_id), "SKU-1"),
        (str(quantity.field_id), "2"),
    }

    assert await _count(PurchaseOrder) == 1
    assert await _count(POHeaderField) == 1


async def test_create_with_fields_rolls_back_everything_on_failure(postgres_env, repos) -> None:
    po_repo, def_repo, *_ = repos
    po_number = await def_repo.create(field_name="po_number")
    orphan_field_id = "00000000-0000-0000-0000-000000000000"

    with pytest.raises(IntegrityError):
        await po_repo.create_with_fields(
            customer_id=None,
            header_fields=[(str(po_number.field_id), "PO-1"), (orphan_field_id, "orphan")],
            line_items=[],
        )

    assert await _count(PurchaseOrder) == 0
    assert await _count(POHeaderField) == 0

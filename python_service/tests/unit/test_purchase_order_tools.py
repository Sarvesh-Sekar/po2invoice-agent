"""create_purchase_order tool unit tests (fakes, no database)."""

from __future__ import annotations

from app.tools.purchase_order_tools import build_purchase_order_tools


class _Definition:
    def __init__(self, field_name: str) -> None:
        self.field_id = f"fid-{field_name}"
        self.field_name = field_name
        self.field_description = None
        self.field_type = "string"


class _FieldDefinitionRepo:
    def __init__(self, names: list[str]) -> None:
        self._definitions = [_Definition(name) for name in names]

    async def list_all(self) -> list[_Definition]:
        return list(self._definitions)


class _PO:
    po_id = "po-123"
    customer_id = "cust-1"
    s3_url = "https://bucket/po.pdf"


class _PurchaseOrderRepo:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    async def create_with_fields(self, **kwargs):
        if self.fail:
            raise RuntimeError("connection lost")
        self.calls.append(kwargs)
        line_item_ids = [f"li-{index + 1}" for index in range(len(kwargs["line_items"]))]
        return _PO(), line_item_ids

    async def update_metadata(self, **kwargs):  # pragma: no cover - unused
        return None


_HEADER_NAMES = ["po_number", "customer", "city", "total_amount"]
_LINE_NAMES = ["product_name", "sku", "quantity", "unit_price", "total_price"]
_ALL_NAMES = _HEADER_NAMES + _LINE_NAMES


def _tools(repo: _PurchaseOrderRepo | None = None, names: list[str] | None = None):
    repo = repo or _PurchaseOrderRepo()
    create, update = build_purchase_order_tools(repo, _FieldDefinitionRepo(names or _ALL_NAMES))
    return repo, create, update


async def test_happy_path_persists_header_and_line_items() -> None:
    repo, create, _ = _tools()
    result = await create.ainvoke(
        {
            "customer_id": "cust-1",
            "s3_url": "https://bucket/po.pdf",
            "header_fields": [
                {"field_name": "po_number", "value": "PO-1001"},
                {"field_name": "city", "value": "Mumbai"},
            ],
            "line_items": [
                [
                    {"field_name": "sku", "value": "SKU-1"},
                    {"field_name": "quantity", "value": "2"},
                    {"field_name": "unit_price", "value": "100.0"},
                ],
                [{"field_name": "sku", "value": "SKU-2"}],
            ],
        }
    )
    assert result["created"] is True
    assert result["po_id"] == "po-123"
    assert result["customer_id"] == "cust-1"
    assert result["header_fields_persisted"] == 2
    assert result["line_items_persisted"] == 2
    assert result["line_item_fields_persisted"] == 4
    assert result["po_line_item_ids"] == ["li-1", "li-2"]

    call = repo.calls[0]
    assert call["header_fields"] == [("fid-po_number", "PO-1001"), ("fid-city", "Mumbai")]
    assert call["line_items"] == [
        [("fid-sku", "SKU-1"), ("fid-quantity", "2"), ("fid-unit_price", "100.0")],
        [("fid-sku", "SKU-2")],
    ]


async def test_unknown_header_field_aborts_before_any_write() -> None:
    repo, create, _ = _tools()
    result = await create.ainvoke(
        {
            "customer_id": "cust-1",
            "header_fields": [{"field_name": "not_a_field", "value": "x"}],
            "line_items": [[{"field_name": "sku", "value": "SKU-1"}]],
        }
    )
    assert result["created"] is False
    assert result["reason"] == "invalid_field_names"
    assert result["unknown_fields"] == ["not_a_field"]
    assert repo.calls == []


async def test_misscoped_fields_are_rejected() -> None:
    repo, create, _ = _tools()
    header_result = await create.ainvoke(
        {"customer_id": "cust-1", "header_fields": [{"field_name": "quantity", "value": "2"}]}
    )
    assert header_result["created"] is False
    assert header_result["misscoped_fields"] == ["quantity"]

    line_result = await create.ainvoke(
        {"customer_id": "cust-1", "line_items": [[{"field_name": "po_number", "value": "PO-1"}]]}
    )
    assert line_result["created"] is False
    assert line_result["misscoped_fields"] == ["po_number"]
    assert repo.calls == []


async def test_blank_values_skipped_and_duplicates_last_wins() -> None:
    repo, create, _ = _tools()
    result = await create.ainvoke(
        {
            "customer_id": "cust-1",
            "header_fields": [
                {"field_name": "po_number", "value": "PO-1"},
                {"field_name": "po_number", "value": "PO-2"},
                {"field_name": "city", "value": "   "},
                {"field_name": "customer", "value": None},
            ],
            "line_items": [[{"field_name": "sku", "value": ""}]],
        }
    )
    assert result["created"] is True
    assert result["header_fields_persisted"] == 1
    assert result["skipped_blank_values"] == 3
    assert result["line_items_persisted"] == 0  # row emptied by blanks
    assert repo.calls[0]["header_fields"] == [("fid-po_number", "PO-2")]


async def test_line_row_as_plain_mapping_is_accepted() -> None:
    repo, create, _ = _tools()
    result = await create.ainvoke(
        {"customer_id": "cust-1", "line_items": [{"sku": "SKU-9", "quantity": "3"}]}
    )
    assert result["created"] is True
    assert repo.calls[0]["line_items"] == [[("fid-sku", "SKU-9"), ("fid-quantity", "3")]]


async def test_create_without_fields_still_creates_po() -> None:
    repo, create, _ = _tools()
    result = await create.ainvoke({"customer_id": "cust-1"})
    assert result["created"] is True
    assert repo.calls[0]["header_fields"] == []
    assert repo.calls[0]["line_items"] == []
    assert result["header_fields_persisted"] == 0
    assert result["line_items_persisted"] == 0


async def test_repository_failure_returns_created_false() -> None:
    repo, create, _ = _tools(_PurchaseOrderRepo(fail=True))
    result = await create.ainvoke(
        {"customer_id": "cust-1", "header_fields": [{"field_name": "po_number", "value": "PO-1"}]}
    )
    assert result["created"] is False
    assert "persistence failed" in result["reason"]

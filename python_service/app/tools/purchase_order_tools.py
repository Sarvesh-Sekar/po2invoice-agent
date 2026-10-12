"""Agent-callable tools for purchase order metadata.

The boundary is: Agent -> @tool -> Repository -> SQLAlchemy -> PostgreSQL.
Extracted field values are persisted into PO_HEADER_FIELDS /
PO_LINE_ITEM_FIELDS, resolved through FIELD_DEFINITIONS, under a single
transaction that also creates the PURCHASE_ORDERS row.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.field_definition_repository import LINE_ITEM_FIELD_NAMES
from app.repositories.repositories.purchase_order_repository import PurchaseOrderRepository


def _po_payload(po) -> dict[str, Any]:
    return {
        "po_id": str(po.po_id),
        "customer_id": str(po.customer_id) if po.customer_id else None,
        "s3_url": po.s3_url,
    }


def _normalize_rows(raw: Any) -> list[tuple[str, Any]]:
    """Normalize incoming field rows into ``(field_name, value)`` pairs.

    Accepts ``[{"field_name": ..., "value": ...}, ...]`` or a plain mapping
    such as ``{"sku": "SKU-1", "quantity": "2"}``.
    """
    rows: list[tuple[str, Any]] = []
    if not raw:
        return rows
    if isinstance(raw, dict):
        raw = [raw]
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if "field_name" in entry:
            name = entry.get("field_name")
            if name is None:
                continue
            rows.append((str(name), entry.get("value")))
        else:
            for name, value in entry.items():
                rows.append((str(name), value))
    return rows


def build_purchase_order_tools(
    repository: PurchaseOrderRepository,
    field_definition_repository: Any,
) -> list[Any]:
    @tool
    async def create_purchase_order(
        customer_id: str | None,
        s3_url: str | None = None,
        header_fields: list[dict] | None = None,
        line_items: list | None = None,
        created_by: str | None = None,
        modified_by: str | None = None,
    ) -> dict:
        """Create a purchase order with its header fields and line items.

        Persists PURCHASE_ORDERS + PO_HEADER_FIELDS + PO_LINE_ITEMS +
        PO_LINE_ITEM_FIELDS atomically and returns the po_id. ``header_fields``
        is ``[{field_name, value}]``; ``line_items`` is a list of rows, each
        either a list of ``{field_name, value}`` or a plain mapping.
        """
        definitions = await field_definition_repository.list_all()
        id_by_name = {definition.field_name: str(definition.field_id) for definition in definitions}
        known = set(id_by_name)

        header_pairs = _normalize_rows(header_fields)
        line_rows = [_normalize_rows(row) for row in (line_items or [])]

        unknown: set[str] = set()
        misscoped: set[str] = set()
        for name, _ in header_pairs:
            if name not in known:
                unknown.add(name)
            elif name in LINE_ITEM_FIELD_NAMES:
                misscoped.add(name)
        for row in line_rows:
            for name, _ in row:
                if name not in known:
                    unknown.add(name)
                elif name not in LINE_ITEM_FIELD_NAMES:
                    misscoped.add(name)

        if unknown:
            return {"created": False, "reason": "invalid_field_names", "unknown_fields": sorted(unknown)}
        if misscoped:
            return {"created": False, "reason": "misscoped_fields", "misscoped_fields": sorted(misscoped)}

        skipped_blank_values = 0

        def _resolve(pairs: list[tuple[str, Any]]) -> list[tuple[str, str]]:
            nonlocal skipped_blank_values
            resolved: dict[str, str] = {}
            for name, value in pairs:
                if value is None or not str(value).strip():
                    skipped_blank_values += 1
                    continue
                resolved[id_by_name[name]] = str(value)
            return list(resolved.items())

        header_tuples = _resolve(header_pairs)
        resolved_line_rows = [row for row in (_resolve(pairs) for pairs in line_rows) if row]

        try:
            async with repository.transaction() as session:
                po = await repository.create(
                    customer_id=customer_id,
                    s3_url=s3_url,
                    created_by=created_by,
                    modified_by=modified_by,
                    session=session,
                )
                po_id = str(po.po_id)
                header_fields_persisted = await repository.create_header_fields(
                    session, po_id=po_id, header_fields=header_tuples
                )
                po_line_item_ids, line_item_fields_persisted = await repository.create_line_items(
                    session, po_id=po_id, line_items=resolved_line_rows
                )
        except Exception as exc:  # pragma: no cover - db dependent
            return {"created": False, "reason": f"persistence failed: {str(exc)[:200]}"}

        return {
            "created": True,
            "po_id": po_id,
            "customer_id": customer_id,
            "header_fields_persisted": header_fields_persisted,
            "line_items_persisted": len(po_line_item_ids),
            "line_item_fields_persisted": line_item_fields_persisted,
            "po_line_item_ids": po_line_item_ids,
            "skipped_blank_values": skipped_blank_values,
        }

    @tool
    async def update_purchase_order_metadata(
        po_id: str,
        customer_id: str | None = None,
        s3_url: str | None = None,
        modified_by: str | None = None,
    ) -> dict:
        """Update PO-level metadata (customer, s3_url). Never extracted values."""
        po = await repository.update_metadata(
            po_id=po_id,
            customer_id=customer_id,
            s3_url=s3_url,
            modified_by=modified_by,
        )
        if po is None:
            return {"found": False}
        return {"found": True, **_po_payload(po)}

    return [create_purchase_order, update_purchase_order_metadata]

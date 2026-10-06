"""Agent-callable tools for purchase order metadata.

The boundary is: Agent -> @tool -> Repository -> SQLAlchemy -> PostgreSQL.
Extracted field values are never written here — they belong to
PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.purchase_order_repository import PurchaseOrderRepository


def _po_payload(po) -> dict[str, Any]:
    return {
        "po_id": str(po.po_id),
        "customer_id": str(po.customer_id) if po.customer_id else None,
        "s3_url": po.s3_url,
    }


def build_purchase_order_tools(repository: PurchaseOrderRepository) -> list[Any]:
    @tool
    async def create_purchase_order(
        customer_id: str | None,
        s3_url: str | None = None,
        created_by: str | None = None,
        modified_by: str | None = None,
    ) -> dict:
        """Create a purchase order (metadata only) and return its po_id.

        Extracted document values are persisted separately through header/line
        field tools.
        """
        po = await repository.create(
            customer_id=customer_id,
            s3_url=s3_url,
            created_by=created_by,
            modified_by=modified_by,
        )
        return _po_payload(po)

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

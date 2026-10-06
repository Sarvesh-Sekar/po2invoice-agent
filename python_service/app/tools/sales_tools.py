"""Agent-callable tools for sale creation and history lookups."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.sales_repository import SalesRepository


def _sale_payload(sale) -> dict[str, Any] | None:
    if sale is None:
        return None
    return {
        "sale_id": str(sale.sale_id),
        "po_id": str(sale.po_id) if sale.po_id else None,
        "status": sale.status,
    }


def build_sales_tools(repository: SalesRepository) -> list[Any]:
    @tool
    async def create_sale(po_id: str) -> dict:
        """Create a sale record for the given purchase order id.

        Returns the created sale including its sale_id.
        """
        sale = await repository.create(po_id=po_id)
        return _sale_payload(sale) or {}

    @tool
    async def get_sale(sale_id: str) -> dict:
        """Get a sale record by its sale_id."""
        sale = await repository.get(sale_id=sale_id)
        payload = _sale_payload(sale)
        return {"found": payload is not None, "sale": payload}

    @tool
    async def get_customer_history(customer_id: str, limit: int = 20) -> dict:
        """Return the recent order/sale history for a customer.

        Useful for verifying repeat behaviour and pricing patterns.
        """
        sales = await repository.list_by_customer(customer_id=customer_id, limit=limit)
        return {"history": [_sale_payload(s) for s in sales]}

    return [create_sale, get_sale, get_customer_history]


def build_customer_history_tool(repository: SalesRepository) -> list[Any]:
    """Read-only sale lookups for the verifier's commercial branch.

    Deliberately separate from :func:`build_sales_tools` so verification can
    never reach ``create_sale``: the verifier reports issues, it must not be
    able to mutate business records.
    """

    @tool
    async def get_customer_history(customer_id: str, limit: int = 20) -> dict:
        """Return the recent order/sale history for a customer.

        Useful for verifying repeat behaviour and pricing patterns.
        """
        sales = await repository.list_by_customer(customer_id=customer_id, limit=limit)
        return {"history": [_sale_payload(s) for s in sales]}

    return [get_customer_history]

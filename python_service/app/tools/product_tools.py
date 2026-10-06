"""Agent-callable tools for product lookups."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.product_repository import ProductRepository


def _product_payload(product) -> dict[str, Any] | None:
    if product is None:
        return None
    return {
        "product_id": str(product.product_id),
        "name": product.name,
        "sku": product.sku,
        "catalog_price": float(product.catalog_price),
        "status": product.status,
    }


def build_product_tools(repository: ProductRepository) -> list[Any]:
    @tool
    async def get_product(sku: str | None = None, name: str | None = None) -> dict:
        """Get a single product by SKU or name.

        Returns the product with its catalogue price and status.
        """
        product = await repository.find(sku=sku, name=name)
        payload = _product_payload(product)
        return {"found": payload is not None, "product": payload}

    @tool
    async def get_products(skus: list[str]) -> dict:
        """Get multiple products by their SKUs.

        Accepts a list of SKU strings and returns the matching products.
        """
        products = await repository.get_by_skus(skus)
        return {"products": [_product_payload(p) for p in products]}

    return [get_product, get_products]

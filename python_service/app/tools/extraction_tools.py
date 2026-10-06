"""Agent-callable tools for the Extraction Agent subgraph.

The boundary is: ExtractionAgent -> Tool -> Repository -> SQLAlchemy ->
PostgreSQL. The model never touches SQL directly.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.customer_repository import CustomerRepository
from app.repositories.repositories.episodic_memory_repository import EpisodicMemoryRepository
from app.repositories.repositories.field_definition_repository import FieldDefinitionRepository
from app.repositories.repositories.po_field_repository import POHeaderFieldRepository, POLineItemRepository
from app.repositories.repositories.product_repository import ProductRepository


def _customer_payload(customer) -> dict[str, Any] | None:
    if customer is None:
        return None
    return {
        "customer_id": str(customer.customer_id),
        "customer_code": customer.customer_code,
        "name": customer.name,
        "status": customer.status,
    }


def _definition_payload(definition) -> dict[str, Any]:
    return {
        "field_id": str(definition.field_id),
        "field_name": definition.field_name,
        "field_description": definition.field_description,
        "field_type": definition.field_type,
    }


def _memory_payload(memory) -> dict[str, Any] | None:
    if memory is None:
        return None
    return {
        "memory_id": str(memory.id),
        "customer_id": str(memory.customer_id),
        "field_id": str(memory.field_id),
        "location_hint": memory.location_hint,
        "document_pattern": memory.document_pattern,
        "instruction": memory.instruction,
        "confidence": float(memory.confidence or 0),
        "usage_count": memory.usage_count,
        "success_count": memory.success_count,
        "failure_count": memory.failure_count,
    }


def build_extraction_tools(
    customer_repository: CustomerRepository,
    field_definition_repository: FieldDefinitionRepository,
    po_header_field_repository: POHeaderFieldRepository,
    po_line_item_repository: POLineItemRepository,
    product_repository: ProductRepository,
    episodic_memory_repository: EpisodicMemoryRepository,
) -> list[Any]:
    @tool
    async def lookup_customer(name: str | None = None, customer_code: str | None = None) -> dict:
        """Identify the customer of a purchase order by name or customer code."""
        customer = await customer_repository.find(name=name, customer_code=customer_code)
        payload = _customer_payload(customer)
        return {"found": payload is not None, "customer": payload}

    @tool
    async def create_customer(name: str, customer_code: str | None = None) -> dict:
        """Create a new active customer when the extraction lookup finds no match.

        A customer code is auto-generated when one is not supplied.
        """
        resolved_code = customer_code.strip() if customer_code else f"CUST-{uuid.uuid4().hex[:8].upper()}"
        try:
            customer = await customer_repository.create(name=name.strip(), customer_code=resolved_code)
        except Exception as exc:  # pragma: no cover - db dependent
            return {"created": False, "reason": f"customer insert failed: {str(exc)[:200]}"}
        payload = _customer_payload(customer)
        return {"created": payload is not None, "customer": payload}

    @tool
    async def lookup_field_definitions(scope: str = "all") -> dict:
        """List canonical extractable field definitions.

        scope: 'all' | 'header' | 'line_item'.
        """
        if scope == "header":
            definitions = await field_definition_repository.list_header_fields()
        elif scope == "line_item":
            definitions = await field_definition_repository.list_line_item_fields()
        else:
            definitions = await field_definition_repository.list_all()
        return {"fields": [_definition_payload(definition) for definition in definitions]}

    @tool
    async def get_field_definition(field_name: str) -> dict:
        """Get one canonical field definition by name."""
        definition = await field_definition_repository.get_by_name(field_name)
        if definition is None:
            return {"found": False}
        return {"found": True, "field": _definition_payload(definition)}

    @tool
    async def get_episodic_memory(customer_id: str, field_name: str) -> dict:
        """Get the customer-specific extraction pattern for a field."""
        definition = await field_definition_repository.get_by_name(field_name)
        if definition is None:
            return {"found": False, "reason": "unknown field"}
        memory = await episodic_memory_repository.get(customer_id=str(customer_id), field_id=str(definition.field_id))
        payload = _memory_payload(memory)
        return {"found": payload is not None, "memory": payload}

    @tool
    async def persist_header_field(po_id: str, field_name: str, value: str) -> dict:
        """Persist one validated header field value into PO_HEADER_FIELDS."""
        definition = await field_definition_repository.get_by_name(field_name)
        if definition is None:
            return {"persisted": False, "reason": "unknown field"}
        row = await po_header_field_repository.upsert(po_id=po_id, field_id=str(definition.field_id), value=str(value))
        return {"persisted": True, "id": str(row.id), "field_name": field_name}

    @tool
    async def persist_line_item(po_id: str, fields: list[dict]) -> dict:
        """Persist a validated line item and its field values.

        fields: [{field_name, value}] — resolved against FIELD_DEFINITIONS.
        """
        definitions = await field_definition_repository.list_all()
        id_by_name = {definition.field_name: definition.field_id for definition in definitions}
        item = await po_line_item_repository.create_line_item(po_id=po_id)
        for field in fields:
            field_id = id_by_name.get(field.get("field_name"))
            if field_id is None:
                continue
            await po_line_item_repository.upsert_field(
                po_line_item_id=item.po_line_item_id, field_id=field_id, value=str(field.get("value", ""))
            )
        return {"persisted": True, "po_line_item_id": str(item.po_line_item_id)}

    @tool
    async def validate_product(sku: str | None = None, name: str | None = None) -> dict:
        """Validate a line item against the product catalogue (SKU or name)."""
        product = await product_repository.find(sku=sku, name=name)
        if product is None:
            return {"found": False}
        return {
            "found": True,
            "product": {
                "product_id": str(product.product_id),
                "name": product.name,
                "sku": product.sku,
                "catalog_price": float(product.catalog_price),
                "status": product.status,
            },
        }

    @tool
    async def update_episodic_memory(
        customer_id: str,
        field_name: str,
        location_hint: str | None = None,
        document_pattern: str | None = None,
        instruction: str | None = None,
        confidence: float | None = None,
    ) -> dict:
        """Create/update a validated customer-specific extraction pattern.

        Stores reusable knowledge — never extracted values.
        """
        definition = await field_definition_repository.get_by_name(field_name)
        if definition is None:
            return {"updated": False, "reason": "unknown field"}
        memory = await episodic_memory_repository.get(customer_id=str(customer_id), field_id=str(definition.field_id))
        if memory is None:
            memory = await episodic_memory_repository.create(
                customer_id=str(customer_id),
                field_id=str(definition.field_id),
                location_hint=location_hint,
                document_pattern=document_pattern,
                instruction=instruction,
                confidence=Decimal(str(confidence)) if confidence is not None else Decimal("0.5"),
            )
        else:
            memory = await episodic_memory_repository.update_pattern(
                str(memory.id),
                location_hint=location_hint,
                document_pattern=document_pattern,
                instruction=instruction,
                confidence=Decimal(str(confidence)) if confidence is not None else None,
            )
        payload = _memory_payload(memory)
        return {"updated": payload is not None, "memory": payload}

    return [
        lookup_customer,
        create_customer,
        lookup_field_definitions,
        get_field_definition,
        get_episodic_memory,
        persist_header_field,
        persist_line_item,
        validate_product,
        update_episodic_memory,
    ]

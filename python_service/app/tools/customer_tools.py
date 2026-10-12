"""Agent-callable tools for customer lookups.

The boundary is: Agent -> @tool -> Repository -> SQLAlchemy -> PostgreSQL.
Tools receive repository dependencies through their construction factory.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.customer_repository import CustomerRepository


def _customer_payload(customer) -> dict[str, Any] | None:
    if customer is None:
        return None
    return {
        "customer_id": str(customer.customer_id),
        "customer_code": customer.customer_code,
        "name": customer.name,
        "status": customer.status,
    }


def build_customer_tools(repository: CustomerRepository) -> list[Any]:
    @tool
    async def find_customer(name: str | None = None, customer_code: str | None = None) -> dict:
        """Find a customer by name or customer code.

        Returns the customer record (customer_id, customer_code, name, ...)
        or an empty result when no customer matches.
        """
        customer = await repository.find(name=name, customer_code=customer_code)
        payload = _customer_payload(customer)
        print(payload,'customer_payload','found:',payload is not None)
        return {"found": payload is not None, "customer": payload}

    return [find_customer]

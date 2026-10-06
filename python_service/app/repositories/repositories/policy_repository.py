"""Company policy repository.

Business rules that must be deterministic live in Python code (see
`app/agents/verifier_agent.py`). This repository provides retrievable policy
documents to the agent tooling (e.g. credit limits, approval thresholds).
"""

from __future__ import annotations

from app.config.settings import Settings

DEFAULT_POLICY: dict = {
    "max_quantity_per_line_item": 1000,
    "min_order_value": 0,
    "max_order_value_without_approval": 1000000,
    "allow_partial_stock": False,
    "credit_limit_mode": "per_order",
}


class PolicyRepository:
    """Reads applicable policy from configuration.

    A RAG-backed policy store can be plugged in behind this interface later.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_applicable_policy(self, context: dict | None = None) -> dict:
        return dict(DEFAULT_POLICY)

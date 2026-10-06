"""Agent-callable tools for company-policy retrieval."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.repositories.repositories.policy_repository import PolicyRepository


def build_policy_tools(repository: PolicyRepository) -> list[Any]:
    @tool
    async def get_applicable_policy(kind: str = "order") -> dict:
        """Get the applicable company policy for the given decision kind.

        Supported kinds: 'order', 'pricing', 'credit'.
        """
        policy = await repository.get_applicable_policy({"kind": kind})
        return {"policy": policy}

    return [get_applicable_policy]

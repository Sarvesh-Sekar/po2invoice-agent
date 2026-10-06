"""Sales Agent: creates the validated purchase order metadata + sale record.

The agent is built with langchain's ``create_agent`` (tools + middleware +
system prompt) and invoked asynchronously via ``ainvoke``.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.exceptions.agent_exceptions import POVerificationError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt


class SalesAgent(BaseAgent):
    name = "sales"

    def __init__(self, tools: list[Any], chat_model: Any) -> None:
        super().__init__()
        self._tools = list(tools)
        self._chat_model = chat_model
        self._agent: Any = None

    def _ensure_agent(self) -> Any:
        if self._agent is not None:
            return self._agent
        system_prompt = SystemMessage(load_prompt("sales.yaml", "sales"))
        self._agent = create_agent(
            self._chat_model,
            tools=list(self._tools),
            system_prompt=system_prompt,
            middleware=[TracingMiddleware(agent_name=self.name)],
            name=self.name,
        )
        return self._agent

    def create_agent(self) -> Any:
        return self._ensure_agent()

    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        verification = state.get("verification_result") or {}
        customer_id = verification.get("customer_id")
        if state.get("extracted_po") is None or not customer_id:
            raise POVerificationError(details={"reason": "validated PO or customer missing"})

        agent = self._ensure_agent()
        payload = (
            f"Validated customer_id: {customer_id}\n"
            f"Source file url (s3_url): {state.get('source_file_url')}\n"
            "Create the purchase order metadata and the matching sale, then return the JSON result."
        )
        response = await agent.ainvoke({"messages": [SystemMessage(content=payload)]})
        result = self._parse_result(response, customer_id, state.get("source_file_url"))
        return self._map_update(state, result)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_agent(state)

    # -- output handling ------------------------------------------------------

    @staticmethod
    def _parse_result(response: Any, customer_id: str, source_file_url: str | None) -> dict[str, Any]:
        text = response.get("output") if isinstance(response, dict) else None
        if not isinstance(text, str):
            text = None
        if text is None:
            messages = response.get("messages") if isinstance(response, dict) else None
            for message in reversed(messages or []):
                content = getattr(message, "content", None)
                if isinstance(content, str) and content.startswith("{"):
                    text = content
                    break
        result = first_json_object(text or "")
        if not isinstance(result, dict):
            raise POVerificationError(details={"reason": "sales agent returned no parseable JSON result"})
        if not result.get("po_id"):
            raise POVerificationError(details={"reason": "purchase order creation returned no po_id"})
        if not result.get("sale_id"):
            raise POVerificationError(details={"reason": "sale creation returned no sale_id"})
        result.setdefault("customer_id", customer_id)
        result.setdefault("source_file_url", source_file_url)
        return result

    @staticmethod
    def _map_update(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        return {
            "po_id": result["po_id"],
            "sale_id": result["sale_id"],
            "sale_status": result.get("sale_status", "CREATED"),
            "source_file_url": result.get("source_file_url"),
            "current_step": "sales",
            "status": "COMPLETED",
        }

"""Sales Agent: creates the validated purchase order metadata + sale record.

The agent is built with langchain's ``create_agent`` (tools + middleware +
system prompt) and invoked asynchronously via ``ainvoke``.
"""

from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage,HumanMessage

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.exceptions.agent_exceptions import POVerificationError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt


NEEDED_TOOLS = ['create_purchase_order','create_sale']

#: Header (non line-item) fields carried from the validated PO into persistence.
_HEADER_FIELD_NAMES = (
    "po_number",
    "customer",
    "gst_no",
    "ship_to",
    "address_1",
    "address_2",
    "city",
    "state",
    "country",
    "zip",
    "total_amount",
)

#: Line-item fields persisted per row (total_price is derived, not extracted).
_LINE_ITEM_FIELD_NAMES = ("product_name", "sku", "quantity", "unit_price")
class SalesAgent(BaseAgent):
    name = "sales"

    def __init__(self, tools: list[Any], chat_model: Any) -> None:
        super().__init__()
        self._tools = list(tools)
        self._chat_model = chat_model
        self._agent: Any = None

    def _ensure_agent(self) -> Any:
        # if self._agent is not None:
        #     return self._agent
        system_prompt = SystemMessage(load_prompt("sales.yaml", "sales"))
        
        filtered_tools = [tool  for tool in self._tools if tool.name in NEEDED_TOOLS]
         
        self._agent = create_agent(
            self._chat_model,
            tools=filtered_tools,
            system_prompt=system_prompt,
            middleware=[TracingMiddleware(agent_name=self.name)],
            name=self.name,
        )
        return self._agent

    def create_agent(self) -> Any:
        return self._ensure_agent()

    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        verification_result = state.get("verification_result") or {}
        customer_id = state.get("customer_id") or verification_result.get("customer_id")
        extracted_po = state.get("extracted_po")
        if extracted_po is None or not customer_id:
            raise POVerificationError(details={"reason": "validated PO or customer missing"})

        agent = self._ensure_agent()
        header_fields, line_items = self._rebuild_fields_from_po(extracted_po)
        payload = (
            f"Validated customer_id: {customer_id}\n"
            f"Source file url (s3_url): {state.get('source_file_url')}\n"
            f"header_fields: {json.dumps(header_fields)}\n"
            f"line_items: {json.dumps(line_items)}\n"
            
        )
        response = await agent.ainvoke({"messages": [HumanMessage(content=payload)]})
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
    def _rebuild_fields_from_po(extracted_po: dict[str, Any]) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
        """Rebuild header/line item field lists from the (possibly HITL-edited) extracted PO."""
        header_fields: list[dict[str, Any]] = []
        for name in _HEADER_FIELD_NAMES:
            if name in extracted_po:
                value = extracted_po.get(name)
                if value is None or not str(value).strip():
                    continue
                header_fields.append({"field_name": name, "value": str(value)})

        line_items: list[list[dict[str, Any]]] = []
        for item in extracted_po.get("line_items") or []:
            row: list[dict[str, Any]] = []
            if not isinstance(item, dict):
                continue
            for name in _LINE_ITEM_FIELD_NAMES:
                if name in item:
                    value = item.get(name)
                    if value is None or not str(value).strip():
                        continue
                    row.append({"field_name": name, "value": str(value)})
            if row:
                line_items.append(row)
        return header_fields, line_items

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

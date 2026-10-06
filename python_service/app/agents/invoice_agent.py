"""Invoice Agent: generates and persists an invoice for a delivered sale.

The agent is built with langchain's ``create_agent`` (tools + middleware +
system prompt) and invoked asynchronously via ``ainvoke``. The GST e-invoice,
PDF build, and S3 upload run inside agent tools.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.exceptions.agent_exceptions import WorkflowExecutionError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt


class InvoiceAgent(BaseAgent):
    name = "invoice"

    def __init__(self, tools: list[Any], chat_model: Any) -> None:
        super().__init__()
        self._tools = list(tools)
        self._chat_model = chat_model
        self._agent: Any = None

    @staticmethod
    def _invoice_number(sale_id: str) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%d")
        return f"INV-{stamp}-{str(sale_id)[:8].upper()}"

    def _ensure_agent(self) -> Any:
        if self._agent is not None:
            return self._agent
        system_prompt = SystemMessage(load_prompt("invoice.yaml", "invoice"))
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
        sale_id = state.get("sale_id")
        if not sale_id:
            raise WorkflowExecutionError(details={"reason": "no sale_id in state"})

        invoice_number = self._invoice_number(sale_id)
        agent = self._ensure_agent()
        payload = (
            f"sale_id: {sale_id}\n"
            f"invoice_number: {invoice_number} (use exactly this value)\n"
            "Upload the invoice PDF, persist the invoice, then return the JSON result."
        )
        self._logger.info(
            "invoice_generation_started: run_id=%s | sale_id=%s | invoice_number=%s",
            state.get("run_id"),
            sale_id,
            invoice_number,
        )
        response = await agent.ainvoke({"messages": [SystemMessage(content=payload)]})
        result = self._parse_result(response, invoice_number)
        return self._map_update(state, result)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_agent(state)

    # -- output handling ------------------------------------------------------

    @staticmethod
    def _parse_result(response: Any, invoice_number: str) -> dict[str, Any]:
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
            raise WorkflowExecutionError(details={"reason": "invoice agent returned no parseable JSON result"})
        if not result.get("invoice_id"):
            raise WorkflowExecutionError(details={"reason": "invoice persistence returned no invoice_id"})
        # Node is authoritative over the model's echo of the invoice number.
        result["invoice_number"] = result.get("invoice_number") or invoice_number
        return result

    @staticmethod
    def _map_update(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        return {
            "invoice_id": result["invoice_id"],
            "invoice_number": result["invoice_number"],
            "invoice_status": result.get("invoice_status", "GENERATED"),
            "s3_url": result.get("s3_url"),
            "current_step": "invoice",
            "status": "RUNNING",
        }

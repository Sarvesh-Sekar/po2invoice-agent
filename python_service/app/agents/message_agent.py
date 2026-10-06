"""Message Agent: sends the invoice to the customer via WhatsApp.

The agent is built with langchain's ``create_agent`` (tools + middleware +
system prompt) and invoked asynchronously via ``ainvoke``. Delivery runs
through a WhatsApp @tool; failures are non-fatal to the workflow.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage

from app.agents.base_agent import BaseAgent
from app.agents.middleware import TracingMiddleware
from app.exceptions.client_exceptions import WhatsAppError
from app.helpers.json_output import first_json_object
from app.helpers.yaml_loader import load_prompt


class MessageAgent(BaseAgent):
    name = "message"

    def __init__(self, tools: list[Any], chat_model: Any) -> None:
        super().__init__()
        self._tools = list(tools)
        self._chat_model = chat_model
        self._agent: Any = None

    def _ensure_agent(self) -> Any:
        if self._agent is not None:
            return self._agent
        system_prompt = SystemMessage(
            load_prompt("message.yaml", "message")
            + "\n\nDeliver the customer message above via send_invoice_document using the supplied "
            "recipient, invoice url, and rendered caption. Then mark the invoice as sent with "
            'mark_invoice_sent. Return a JSON object: {"message_status": "SENT"|"SKIPPED"|"FAILED", '
            '"invoice_status": string}. The caption must be the rendered template text exactly.'
        )
        self._agent = create_agent(
            self._chat_model,
            tools=list(self._tools),
            system_prompt=system_prompt,
            middleware=[TracingMiddleware(agent_name=self.name)],
            name=self.name,
        )
        return self._agent

    def _render_caption(self, state: dict[str, Any]) -> str:
        prompt = load_prompt("message.yaml", "message")
        return prompt.format(
            invoice_number=state.get("invoice_number") or "",
            total_amount=state.get("invoice_total") or state.get("invoice_amount") or "",
        )

    def create_agent(self) -> Any:
        return self._ensure_agent()

    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        invoice_id = state.get("invoice_id")
        s3_url = state.get("s3_url")
        to = state.get("customer_phone")

        if not invoice_id or not s3_url:
            return self._warn("invoice document not available; message skipped")

        if not to:
            return self._warn("no customer phone on file; message skipped")

        caption = self._render_caption(state)
        agent = self._ensure_agent()
        payload = (
            f"to: {to}\n"
            f"document_url: {s3_url}\n"
            f"caption:\n{caption}\n\n"
            f"invoice_id: {invoice_id}\n"
            f"invoice_status: {state.get('invoice_status') or 'GENERATED'}\n"
            "Deliver the message and return the JSON result."
        )
        try:
            response = await agent.ainvoke({"messages": [SystemMessage(content=payload)]})
        except WhatsAppError as exc:
            self._logger.warning(
                "message_delivery_failed: run_id=%s | invoice_id=%s | error=%s",
                state.get("run_id"),
                invoice_id,
                exc,
            )
            return {
                "current_step": "message",
                "status": "COMPLETED",
                "message_status": "FAILED",
                "invoice_status": state.get("invoice_status") or "GENERATED",
            }
        return self._map_update(state, response)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return await self.invoke_agent(state)

    # -- output handling ------------------------------------------------------

    @staticmethod
    def _map_update(state: dict[str, Any], response: Any) -> dict[str, Any]:
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
        if isinstance(result, dict) and result.get("message_status") in ("SENT", "FAILED", "SKIPPED"):
            return {
                "current_step": "message",
                "status": "COMPLETED",
                "message_status": result["message_status"],
                "invoice_status": result.get("invoice_status") or state.get("invoice_status") or "GENERATED",
            }
        return {
            "current_step": "message",
            "status": "COMPLETED",
            "message_status": "SENT",
            "invoice_status": "SENT",
        }

    def _warn(self, reason: str) -> dict[str, Any]:
        return {
            "current_step": "message",
            "status": "COMPLETED",
            "message_status": "SKIPPED",
            "invoice_status": "GENERATED",
            "message_note": reason,
        }

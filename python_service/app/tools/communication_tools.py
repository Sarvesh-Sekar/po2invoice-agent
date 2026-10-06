"""Agent-callable tools for WhatsApp message delivery.

The boundary is: Agent -> @tool -> WhatsAppClient -> HTTP API.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.clients.base import BaseWhatsAppClient


def build_whatsapp_tools(whatsapp_client: BaseWhatsAppClient) -> list[Any]:
    @tool
    async def send_invoice_document(to: str, document_url: str, caption: str) -> dict:
        """Send an invoice PDF to a customer over WhatsApp.

        Accepts the recipient identifier, the public invoice URL, and the
        customer-facing caption accompanying the document.
        """
        result = await whatsapp_client.send_document(to=to, document_url=document_url, caption=caption)
        return {"sent": True, **result}

    return [send_invoice_document]

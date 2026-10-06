"""WhatsApp business messaging client."""

from __future__ import annotations

import httpx

from app.clients.base import BaseWhatsAppClient
from app.config.settings import Settings
from app.exceptions.client_exceptions import WhatsAppError


class WhatsAppClient(BaseWhatsAppClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._settings.whatsapp_token:
            headers["Authorization"] = f"Bearer {self._settings.whatsapp_token}"
        return headers

    def _base_url(self) -> str:
        url = self._settings.whatsapp_api_url
        if not url:
            raise WhatsAppError(details={"reason": "whatsapp_api_url not configured"})
        return url.rstrip("/")

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url()}/{path}",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise WhatsAppError(details={"reason": str(exc)[:500]}) from exc

        if response.status_code >= 400:
            raise WhatsAppError(
                details={
                    "status_code": response.status_code,
                    "reason": response.text[:500],
                }
            )
        if response.status_code == 204 or not response.content:
            return {"ok": True}
        try:
            return response.json()
        except ValueError:
            return {"ok": True}

    async def send_document(self, *, to: str, document_url: str, caption: str) -> dict:
        return await self._post(
            "messages",
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "document",
                "document": {"link": document_url, "caption": caption, "filename": "invoice.pdf"},
            },
        )

    async def send_text(self, *, to: str, message: str) -> dict:
        return await self._post(
            "messages",
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"body": message},
            },
        )

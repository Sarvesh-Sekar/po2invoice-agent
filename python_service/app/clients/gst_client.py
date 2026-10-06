"""GST / e-invoice API client."""

from __future__ import annotations

import httpx

from app.clients.base import BaseGSTClient
from app.config.settings import Settings
from app.exceptions.client_exceptions import GSTError


class GSTClient(BaseGSTClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._settings.gst_api_key:
            headers["X-API-Key"] = self._settings.gst_api_key
        return headers

    async def generate_einvoice(self, payload: dict) -> dict:
        url = self._settings.gst_api_url
        if not url:
            raise GSTError(details={"reason": "gst_api_url not configured"})
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise GSTError(details={"reason": str(exc)[:500]}) from exc

        if response.status_code >= 400:
            raise GSTError(
                details={
                    "status_code": response.status_code,
                    "reason": response.text[:500],
                }
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise GSTError(details={"reason": "non-JSON response"}) from exc

        irn = data.get("irn") or data.get("invoice_reference") or data.get("TicketNumber")
        if not irn:
            raise GSTError(details={"reason": "response missing IRN", "body": response.text[:500]})
        return {"irn": str(irn), "response": data}

"""Agent-callable tools for invoice generation data.

PO-level values are read dynamically from PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS
(resolved through FIELD_DEFINITIONS), never from denormalized PO columns.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import tool

from app.clients.base import BaseGSTClient, BaseS3Client
from app.helpers.invoice_pdf import build_invoice_pdf
from app.repositories.repositories.field_definition_repository import FieldDefinitionRepository
from app.repositories.repositories.invoice_repository import InvoiceRepository
from app.repositories.repositories.po_field_repository import POHeaderFieldRepository, POLineItemRepository
from app.repositories.repositories.sales_repository import SalesRepository

_HEADER_KEY_MAP = {
    "po_number": "po_number",
    "ship_to": "ship_to",
    "address_1": "address_1",
    "address_2": "address_2",
    "city": "city",
    "state": "state",
    "country": "country",
    "zip": "zip",
    "total_amount": "total_amount",
}

_LINE_ITEM_KEY_MAP = {
    "product_name": "product_name",
    "sku": "sku",
    "quantity": "quantity",
    "unit_price": "unit_price",
    "total_price": "total",
}


def build_invoice_tools(
    sales_repository: SalesRepository,
    invoice_repository: InvoiceRepository,
    purchase_order_repository: Any,
    po_header_field_repository: POHeaderFieldRepository,
    po_line_item_repository: POLineItemRepository,
    field_definition_repository: FieldDefinitionRepository,
) -> list[Any]:
    async def _resolve_header_fields(po_id: str) -> dict[str, Any]:
        """Resolve PO header field values through FIELD_DEFINITIONS."""
        definitions = await field_definition_repository.list_all()
        name_by_id = {definition.field_id: definition.field_name for definition in definitions}
        rows = await po_header_field_repository.get_by_po(po_id)
        resolved: dict[str, Any] = {}
        for row in rows:
            field_name = name_by_id.get(row.field_id, row.field_id)
            key = _HEADER_KEY_MAP.get(field_name, field_name.lower())
            resolved[key] = row.field_value
        return resolved

    async def _line_item_payload(po_id: str) -> tuple[list[dict[str, Any]], float]:
        """Resolve line items with product/sku/qty/unit price across rows."""
        items = await po_line_item_repository.get_line_items(po_id)
        definitions = await field_definition_repository.list_all()
        id_by_name = {definition.field_name: definition.field_id for definition in definitions}
        key_by_id = {
            definition.field_id: name.lower() for name, definition in id_by_name.items() if name in _LINE_ITEM_KEY_MAP
        }
        payload: list[dict[str, Any]] = []
        total = 0.0
        for item in items:
            fields = await po_line_item_repository.get_fields_by_line_item(item.po_line_item_id)
            row: dict[str, Any] = {}
            for f in fields:
                key = key_by_id.get(f.field_id)
                if key:
                    row[key] = f.field_value
            quantity = float(row.get("quantity", 0) or 0)
            unit_price = float(row.get("unit_price", 0) or 0)
            row.setdefault("total", round(quantity * unit_price, 2))
            total += float(row["total"])
            payload.append(row)
        return payload, round(total, 2)

    async def _total_from_line_items(po_id: str) -> float:
        items = await po_line_item_repository.get_line_items(po_id)
        definitions = await field_definition_repository.list_all()
        id_by_name = {definition.field_name: definition.field_id for definition in definitions}
        total = 0.0
        price_field_id = id_by_name.get("unit_price")
        qty_field_id = id_by_name.get("quantity")
        for item in items:
            fields = await po_line_item_repository.get_fields_by_line_item(item.po_line_item_id)
            values = {f.field_id: f.field_value for f in fields}
            price = float(values.get(price_field_id, 0) or 0)
            quantity = float(values.get(qty_field_id, 0) or 0)
            total += price * quantity
        return round(total, 2)

    @tool
    async def get_sale_details(sale_id: str) -> dict:
        """Fetch sale details plus the linked PO header fields and total."""
        sale = await sales_repository.get(sale_id=sale_id)
        if sale is None:
            return {"found": False}
        payload: dict[str, Any] = {
            "sale_id": str(sale.sale_id),
            "po_id": str(sale.po_id) if sale.po_id else None,
            "status": sale.status,
        }
        if sale.po_id:
            po = await purchase_order_repository.get(sale.po_id)
            headers = await _resolve_header_fields(sale.po_id)
            line_items, line_total = await _line_item_payload(sale.po_id)
            total = headers.get("total_amount") or line_total or await _total_from_line_items(sale.po_id)
            payload["purchase_order"] = {
                **(headers if "po_number" in headers else {"po_number": None}),
                "total_amount": round(float(total), 2),
                "line_items": line_items,
                "customer_id": str(po.customer_id) if po and po.customer_id else None,
                "s3_url": po.s3_url if po else None,
            }
        return {"found": True, **payload}

    @tool
    async def create_invoice(
        po_id: str | None,
        invoice_number: str,
        gst_irn: str | None = None,
        s3_url: str | None = None,
    ) -> dict:
        """Persist a generated invoice and return its invoice_id."""
        invoice = await invoice_repository.create(
            po_id=po_id,
            invoice_number=invoice_number,
            gst_irn=gst_irn,
            s3_url=s3_url,
            status="GENERATED",
        )
        return {
            "invoice_id": str(invoice.invoice_id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
        }

    @tool
    async def mark_invoice_sent(invoice_id: str) -> dict:
        """Mark an invoice as SENT after successful delivery."""
        invoice = await invoice_repository.update_status(invoice_id=invoice_id, status="SENT")
        if invoice is None:
            return {"updated": False}
        return {"updated": True, "invoice_id": str(invoice.invoice_id), "status": invoice.status}

    return [get_sale_details, create_invoice, mark_invoice_sent]


def build_invoice_service_tools(
    gst_client: BaseGSTClient,
    s3_client: BaseS3Client,
    *,
    include_gst_irn: bool = False,
) -> list[Any]:
    """Tools that wrap the invoice PDF/S3 pipeline and, optionally, the GST API.

    GST e-invoice generation is outside the current business scope, so
    ``generate_invoice_irn`` is not exposed by default. The client and tool stay
    so the capability can be re-enabled with ``include_gst_irn=True``.
    """

    @tool
    async def upload_invoice_pdf(
        invoice_number: str,
        sale_id: str,
        po_number: str | None,
        ship_to: dict[str, Any],
        line_items: list[dict[str, Any]],
        total_amount: float,
        gst_irn: str | None = None,
    ) -> dict:
        """Build the invoice PDF and upload it to object storage.

        Returns the public s3_url of the generated invoice document.
        """
        pdf = await asyncio.to_thread(
            build_invoice_pdf,
            invoice_number=invoice_number,
            sale_id=sale_id,
            po_number=po_number,
            ship_to=ship_to,
            line_items=line_items,
            total_amount=total_amount,
            gst_irn=gst_irn,
        )
        s3_key = f"invoices/{sale_id}/{invoice_number}.pdf"
        s3_url = await s3_client.upload(pdf, s3_key, "application/pdf")
        return {"s3_url": s3_url}

    tools: list[Any] = [upload_invoice_pdf]
    if not include_gst_irn:
        return tools

    @tool
    async def generate_invoice_irn(
        invoice_number: str,
        sale_id: str,
        total_amount: float,
        gst_details: dict[str, Any] | None = None,
    ) -> dict:
        """Generate a GST e-invoice IRN for the given invoice.

        Returns the IRN issued by the GST API plus the raw response.
        """
        response = await gst_client.generate_einvoice(
            {
                "invoice_number": invoice_number,
                "sale_id": sale_id,
                "total_amount": total_amount,
                "gst_details": gst_details or {},
            }
        )
        return response

    tools.append(generate_invoice_irn)
    return tools

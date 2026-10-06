"""Minimal invoice PDF generation using ReportLab (CPU-bound, run in thread)."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_invoice_pdf(
    *,
    invoice_number: str,
    sale_id: str,
    po_number: str | None,
    ship_to: dict,
    line_items: list[dict],
    total_amount: float,
    gst_irn: str | None,
) -> bytes:
    """Render an invoice as a PDF and return the raw bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()

    story: list[Any] = []
    story.append(Paragraph(f"Invoice {invoice_number}", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Issued: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))

    if ship_to:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Bill to: {ship_to.get('ship_to', '')}", styles["Normal"]))

    story.append(Spacer(1, 10))
    header = ["Item", "SKU", "Qty", "Unit Price", "Total"]
    rows = [header]
    for item in line_items:
        rows.append(
            [
                item.get("product_name", ""),
                item.get("sku", ""),
                str(item.get("quantity", "")),
                f"{float(item.get('unit_price', 0)):.2f}",
                f"{float(item.get('total_price', 0)):.2f}",
            ]
        )
    table = Table(rows, colWidths=[70 * mm, 40 * mm, 20 * mm, 30 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Total: {total_amount:.2f}", styles["Heading3"]))
    if gst_irn:
        story.append(Paragraph(f"GST IRN: {gst_irn}", styles["Normal"]))

    doc.build(story)
    return buffer.getvalue()

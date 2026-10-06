"""Invoice repository backed by SQLAlchemy / PostgreSQL.

Invoices reference the purchase order directly through ``po_id``.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.invoices import Invoice
from app.repositories.schemas.orm.sales import Sale


class InvoiceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self,
        *,
        po_id: str | None,
        invoice_number: str | None,
        gst_irn: str | None,
        s3_url: str | None,
        status: str = "GENERATED",
    ) -> Invoice:
        async with self._sf() as session:
            invoice = Invoice(
                po_id=po_id,
                invoice_number=invoice_number,
                gst_irn=gst_irn,
                s3_url=s3_url,
                status=status,
            )
            session.add(invoice)
            await session.commit()
            await session.refresh(invoice)
            return invoice

    async def get(self, invoice_id: str) -> Invoice | None:
        async with self._sf() as session:
            result = await session.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
            return result.scalar_one_or_none()

    async def get_by_po(self, po_id: str) -> Invoice | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Invoice).where(Invoice.po_id == po_id).order_by(Invoice.created_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_by_sale(self, sale_id: str) -> Invoice | None:
        """Return the invoice already raised for a sale, if any.

        Guards invoice generation against a redelivered event that carries a
        fresh idempotency key: the sale relationship, not the key, is what
        makes an invoice unique.
        """
        async with self._sf() as session:
            result = await session.execute(
                select(Invoice).join(Sale, Sale.po_id == Invoice.po_id).where(Sale.sale_id == sale_id).limit(1)
            )
            return result.scalar_one_or_none()

    async def update_status(self, invoice_id: str, status: str) -> Invoice | None:
        async with self._sf() as session:
            await session.execute(update(Invoice).where(Invoice.invoice_id == invoice_id).values(status=status))
            await session.commit()
            result = await session.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
            return result.scalar_one_or_none()

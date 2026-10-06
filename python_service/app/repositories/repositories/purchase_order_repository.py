"""Purchase order repository backed by SQLAlchemy / PostgreSQL.

PURCHASE_ORDERS holds only PO-level metadata. Extracted values are persisted
elsewhere (PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS).
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.purchase_orders import PurchaseOrder


class PurchaseOrderRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self,
        *,
        customer_id: str | None,
        s3_url: str | None = None,
        created_by: str | None = None,
        modified_by: str | None = None,
    ) -> PurchaseOrder:
        async with self._sf() as session:
            po = PurchaseOrder(
                customer_id=customer_id,
                s3_url=s3_url,
                created_by=created_by,
                modified_by=modified_by,
            )
            session.add(po)
            await session.commit()
            await session.refresh(po)
            return po

    async def get(self, po_id: str) -> PurchaseOrder | None:
        async with self._sf() as session:
            result = await session.execute(select(PurchaseOrder).where(PurchaseOrder.po_id == po_id))
            return result.scalar_one_or_none()

    async def update_metadata(
        self,
        po_id: str,
        *,
        customer_id: str | None = None,
        s3_url: str | None = None,
        modified_by: str | None = None,
    ) -> PurchaseOrder | None:
        """Update only PO-level metadata; never extracted field values."""
        async with self._sf() as session:
            values: dict = {}
            if customer_id is not None:
                values["customer_id"] = customer_id
            if s3_url is not None:
                values["s3_url"] = s3_url
            if modified_by is not None:
                values["modified_by"] = modified_by
            if values:
                await session.execute(update(PurchaseOrder).where(PurchaseOrder.po_id == po_id).values(**values))
                await session.commit()
            result = await session.execute(select(PurchaseOrder).where(PurchaseOrder.po_id == po_id))
            return result.scalar_one_or_none()

"""Sales repository backed by SQLAlchemy / PostgreSQL.

Sales reference the purchase order directly through ``po_id``.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.purchase_orders import PurchaseOrder
from app.repositories.schemas.orm.sales import Sale


class SalesRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(self, *, po_id: str, status: str = "CREATED") -> Sale:
        async with self._sf() as session:
            sale = Sale(po_id=po_id, status=status)
            session.add(sale)
            await session.commit()
            await session.refresh(sale)
            return sale

    async def get(self, sale_id: str) -> Sale | None:
        async with self._sf() as session:
            result = await session.execute(select(Sale).where(Sale.sale_id == sale_id))
            return result.scalar_one_or_none()

    async def get_by_po(self, po_id: str) -> Sale | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Sale).where(Sale.po_id == po_id).order_by(Sale.created_at.desc()).limit(1)
            )
            return result.scalar_one_or_none()

    async def update_status(self, sale_id: str, status: str) -> Sale | None:
        async with self._sf() as session:
            await session.execute(update(Sale).where(Sale.sale_id == sale_id).values(status=status))
            await session.commit()
            result = await session.execute(select(Sale).where(Sale.sale_id == sale_id))
            return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: str, limit: int = 20) -> list[Sale]:
        """Sale history for a customer via the owning purchase order."""
        async with self._sf() as session:
            statement = (
                select(Sale)
                .join(PurchaseOrder, Sale.po_id == PurchaseOrder.po_id)
                .where(PurchaseOrder.customer_id == customer_id)
                .order_by(Sale.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(statement)
            return list(result.scalars().all())

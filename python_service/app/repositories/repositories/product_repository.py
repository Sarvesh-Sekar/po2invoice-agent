"""Product repository backed by SQLAlchemy / PostgreSQL."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.products import Product

ACTIVE = "ACTIVE"


class ProductRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_by_sku(self, sku: str) -> Product | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Product).where(func.lower(Product.sku) == sku.strip().lower(), Product.status == ACTIVE)
            )
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Product | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Product).where(func.lower(Product.name) == name.strip().lower(), Product.status == ACTIVE)
            )
            return result.scalar_one_or_none()

    async def get_by_skus(self, skus: list[str]) -> list[Product]:
        normalized = [s.strip().lower() for s in skus if s and s.strip()]
        if not normalized:
            return []
        async with self._sf() as session:
            result = await session.execute(
                select(Product)
                .where(func.lower(Product.sku).in_(normalized), Product.status == ACTIVE)
                .order_by(Product.name)
            )
            return list(result.scalars().all())

    async def find(self, sku: str | None = None, name: str | None = None) -> Product | None:
        if sku:
            return await self.get_by_sku(sku)
        if name:
            return await self.get_by_name(name)
        return None

    async def search(self, term: str | None = None, limit: int = 50) -> list[Product]:
        async with self._sf() as session:
            statement = select(Product).where(Product.status == ACTIVE)
            if term:
                like = f"%{term.strip()}%"
                statement = statement.where(or_(Product.name.ilike(like), Product.sku.ilike(like)))
            statement = statement.order_by(Product.name).limit(limit)
            result = await session.execute(statement)
            return list(result.scalars().all())

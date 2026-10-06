"""Customer repository backed by SQLAlchemy / PostgreSQL."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.customers import Customer

ACTIVE = "ACTIVE"


class CustomerRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def get_by_customer_code(self, customer_code: str) -> Customer | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Customer).where(
                    func.lower(Customer.customer_code) == customer_code.strip().lower(),
                    Customer.status == ACTIVE,
                )
            )
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Customer | None:
        async with self._sf() as session:
            result = await session.execute(
                select(Customer).where(
                    func.lower(Customer.name) == name.strip().lower(),
                    Customer.status == ACTIVE,
                )
            )
            return result.scalar_one_or_none()

    async def find(self, name: str | None = None, customer_code: str | None = None) -> Customer | None:
        """Look up a customer by name or customer code."""
        if customer_code:
            return await self.get_by_customer_code(customer_code)
        if name:
            return await self.get_by_name(name)
        return None

    async def create(self, *, name: str, customer_code: str | None = None, status: str = ACTIVE) -> Customer:
        """Create a new active customer record."""
        async with self._sf() as session:
            customer = Customer(name=name, customer_code=customer_code, status=status)
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            return customer

    async def search(self, term: str | None = None, limit: int = 20) -> list[Customer]:
        async with self._sf() as session:
            statement = select(Customer).where(Customer.status == ACTIVE)
            if term:
                like = f"%{term.strip()}%"
                statement = statement.where(or_(Customer.name.ilike(like), Customer.customer_code.ilike(like)))
            statement = statement.order_by(Customer.name).limit(limit)
            result = await session.execute(statement)
            return list(result.scalars().all())

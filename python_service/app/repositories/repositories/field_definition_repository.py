"""Field definition repository backed by SQLAlchemy / PostgreSQL.

FIELD_DEFINITIONS is the canonical registry of extractable fields. The set of
line-item (vs header) fields is a bounded configuration constant because the
ER provides no scope column; everything else is read dynamically from the
database at extraction time.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.field_definitions import FieldDefinition

#: Canonical names of fields that are repeated per line item. These anchor the
#: header-vs-line classification; the schema of each field still lives in
#: FIELD_DEFINITIONS and feeds extraction dynamically.
LINE_ITEM_FIELD_NAMES = {"product_name", "sku", "quantity", "unit_price", "total_price"}


class FieldDefinitionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self,
        *,
        field_name: str,
        field_description: str | None = None,
        field_type: str = "string",
    ) -> FieldDefinition:
        async with self._sf() as session:
            definition = FieldDefinition(
                field_name=field_name,
                field_description=field_description,
                field_type=field_type,
            )
            session.add(definition)
            await session.commit()
            await session.refresh(definition)
            return definition

    async def get(self, field_id: str) -> FieldDefinition | None:
        async with self._sf() as session:
            result = await session.execute(select(FieldDefinition).where(FieldDefinition.field_id == field_id))
            return result.scalar_one_or_none()

    async def get_by_name(self, field_name: str) -> FieldDefinition | None:
        async with self._sf() as session:
            result = await session.execute(select(FieldDefinition).where(FieldDefinition.field_name == field_name))
            return result.scalar_one_or_none()

    async def list_all(self) -> list[FieldDefinition]:
        async with self._sf() as session:
            result = await session.execute(select(FieldDefinition).order_by(FieldDefinition.field_name))
            return list(result.scalars().all())

    async def list_header_fields(self) -> list[FieldDefinition]:
        async with self._sf() as session:
            result = await session.execute(
                select(FieldDefinition)
                .where(FieldDefinition.field_name.notin_(sorted(LINE_ITEM_FIELD_NAMES)))
                .order_by(FieldDefinition.field_name)
            )
            return list(result.scalars().all())

    async def list_line_item_fields(self) -> list[FieldDefinition]:
        async with self._sf() as session:
            result = await session.execute(
                select(FieldDefinition)
                .where(FieldDefinition.field_name.in_(sorted(LINE_ITEM_FIELD_NAMES)))
                .order_by(FieldDefinition.field_name)
            )
            return list(result.scalars().all())

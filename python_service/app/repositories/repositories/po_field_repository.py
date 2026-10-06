"""PO header/line extracted-field repositories backed by SQLAlchemy / PostgreSQL.

These repositories persist extracted document values into PO_HEADER_FIELDS and
PO_LINE_ITEM_FIELDS, and manage the PO_LINE_ITEMS rows they attach to.
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.po_fields import POHeaderField, POLineItemField
from app.repositories.schemas.orm.purchase_orders import POLineItem


class POHeaderFieldRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def upsert(self, *, po_id: str, field_id: str, value: str) -> POHeaderField:
        """Create or update one extracted header field for a PO."""
        async with self._sf() as session:
            existing = await self.get(po_id=po_id, field_id=field_id)
            if existing is not None:
                if existing.field_value == value:
                    return existing
                await session.execute(
                    update(POHeaderField)
                    .where(POHeaderField.po_id == po_id, POHeaderField.field_id == field_id)
                    .values(field_value=value)
                )
                await session.commit()
                return await self.get(po_id=po_id, field_id=field_id)  # type: ignore[return-value]
            header = POHeaderField(po_id=po_id, field_id=field_id, field_value=value)
            session.add(header)
            await session.commit()
            await session.refresh(header)
            return header

    async def create(self, *, po_id: str, field_id: str, value: str) -> POHeaderField:
        return await self.upsert(po_id=po_id, field_id=field_id, value=value)

    async def update_value(self, *, po_id: str, field_id: str, value: str) -> POHeaderField | None:
        async with self._sf() as session:
            await session.execute(
                update(POHeaderField)
                .where(POHeaderField.po_id == po_id, POHeaderField.field_id == field_id)
                .values(field_value=value)
            )
            await session.commit()
            return await self.get(po_id=po_id, field_id=field_id)

    async def get(self, *, po_id: str, field_id: str) -> POHeaderField | None:
        async with self._sf() as session:
            result = await session.execute(
                select(POHeaderField).where(POHeaderField.po_id == po_id, POHeaderField.field_id == field_id)
            )
            return result.scalar_one_or_none()

    async def get_by_po(self, po_id: str) -> list[POHeaderField]:
        async with self._sf() as session:
            result = await session.execute(
                select(POHeaderField).where(POHeaderField.po_id == po_id).order_by(POHeaderField.field_id)
            )
            return list(result.scalars().all())

    async def delete_for_po(self, po_id: str) -> None:
        async with self._sf() as session:
            await session.execute(delete(POHeaderField).where(POHeaderField.po_id == po_id))
            await session.commit()


class POLineItemRepository:
    """PO_LINE_ITEMS management plus PO_LINE_ITEM_FIELDS persistence."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_line_item(self, *, po_id: str, product_id: str | None = None) -> POLineItem:
        async with self._sf() as session:
            item = POLineItem(po_id=po_id, product_id=product_id)
            session.add(item)
            await session.commit()
            await session.refresh(item)
            return item

    async def get_line_items(self, po_id: str) -> list[POLineItem]:
        async with self._sf() as session:
            result = await session.execute(
                select(POLineItem).where(POLineItem.po_id == po_id).order_by(POLineItem.po_line_item_id)
            )
            return list(result.scalars().all())

    async def set_product(self, po_line_item_id: str, product_id: str | None) -> POLineItem | None:
        async with self._sf() as session:
            await session.execute(
                update(POLineItem).where(POLineItem.po_line_item_id == po_line_item_id).values(product_id=product_id)
            )
            await session.commit()
            result = await session.execute(select(POLineItem).where(POLineItem.po_line_item_id == po_line_item_id))
            return result.scalar_one_or_none()

    async def delete_for_po(self, po_id: str) -> None:
        async with self._sf() as session:
            await session.execute(delete(POLineItem).where(POLineItem.po_id == po_id))
            await session.commit()

    # --- line-item field persistence ---

    async def upsert_field(self, *, po_line_item_id: str, field_id: str, value: str) -> POLineItemField:
        async with self._sf() as session:
            existing = await self.get_field(po_line_item_id=po_line_item_id, field_id=field_id)
            if existing is not None:
                if existing.field_value == value:
                    return existing
                await session.execute(
                    update(POLineItemField)
                    .where(
                        POLineItemField.po_line_item_id == po_line_item_id,
                        POLineItemField.field_id == field_id,
                    )
                    .values(field_value=value)
                )
                await session.commit()
                return await self.get_field(po_line_item_id=po_line_item_id, field_id=field_id)  # type: ignore[return-value]
            field = POLineItemField(po_line_item_id=po_line_item_id, field_id=field_id, field_value=value)
            session.add(field)
            await session.commit()
            await session.refresh(field)
            return field

    async def create_field(self, *, po_line_item_id: str, field_id: str, value: str) -> POLineItemField:
        return await self.upsert_field(po_line_item_id=po_line_item_id, field_id=field_id, value=value)

    async def update_field_value(self, *, po_line_item_id: str, field_id: str, value: str) -> POLineItemField | None:
        async with self._sf() as session:
            await session.execute(
                update(POLineItemField)
                .where(
                    POLineItemField.po_line_item_id == po_line_item_id,
                    POLineItemField.field_id == field_id,
                )
                .values(field_value=value)
            )
            await session.commit()
            return await self.get_field(po_line_item_id=po_line_item_id, field_id=field_id)

    async def get_field(self, *, po_line_item_id: str, field_id: str) -> POLineItemField | None:
        async with self._sf() as session:
            result = await session.execute(
                select(POLineItemField).where(
                    POLineItemField.po_line_item_id == po_line_item_id,
                    POLineItemField.field_id == field_id,
                )
            )
            return result.scalar_one_or_none()

    async def get_fields_by_line_item(self, po_line_item_id: str) -> list[POLineItemField]:
        async with self._sf() as session:
            result = await session.execute(
                select(POLineItemField)
                .where(POLineItemField.po_line_item_id == po_line_item_id)
                .order_by(POLineItemField.field_id)
            )
            return list(result.scalars().all())

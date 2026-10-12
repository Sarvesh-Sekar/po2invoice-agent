"""Purchase order repository backed by SQLAlchemy / PostgreSQL.

PURCHASE_ORDERS holds only PO-level metadata. Extracted values are persisted
elsewhere (PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.schemas.orm.po_fields import POHeaderField, POLineItemField
from app.repositories.schemas.orm.purchase_orders import POLineItem, PurchaseOrder


class PurchaseOrderRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield one session for a multi-table write; commit once, rollback on error.

        Every write done with the yielded session is committed together on a
        clean exit and rolled back as a unit if any write raises.
        """
        async with self._sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create(
        self,
        *,
        customer_id: str | None,
        s3_url: str | None = None,
        created_by: str | None = None,
        modified_by: str | None = None,
        session: AsyncSession | None = None,
    ) -> PurchaseOrder:
        """Create the PO metadata row.

        When a ``session`` is supplied the insert is flushed (not committed) so
        the caller can compose it with sibling writes in one transaction.
        """
        po = PurchaseOrder(
            customer_id=customer_id,
            s3_url=s3_url,
            created_by=created_by,
            modified_by=modified_by,
        )
        if session is not None:
            session.add(po)
            await session.flush()
            return po
        async with self._sf() as own_session:
            own_session.add(po)
            await own_session.commit()
            await own_session.refresh(po)
            return po

    async def create_header_fields(
        self,
        session: AsyncSession,
        *,
        po_id: str,
        header_fields: list[tuple[str, str]],
    ) -> int:
        """Insert PO_HEADER_FIELDS rows for a PO (no commit; caller owns the tx)."""
        for field_id, value in header_fields:
            session.add(POHeaderField(po_id=po_id, field_id=field_id, field_value=value))
        if header_fields:
            await session.flush()
        return len(header_fields)

    async def create_line_items(
        self,
        session: AsyncSession,
        *,
        po_id: str,
        line_items: list[list[tuple[str, str]]],
    ) -> tuple[list[str], int]:
        """Insert PO_LINE_ITEMS + PO_LINE_ITEM_FIELDS rows (no commit).

        Returns the created ``po_line_item_id`` list and the total number of
        field rows written.
        """
        line_item_ids: list[str] = []
        field_count = 0
        for row_fields in line_items:
            item = POLineItem(po_id=po_id)
            session.add(item)
            await session.flush()
            line_item_ids.append(str(item.po_line_item_id))
            for field_id, value in row_fields:
                session.add(
                    POLineItemField(
                        po_line_item_id=item.po_line_item_id,
                        field_id=field_id,
                        field_value=value,
                    )
                )
                field_count += 1
        return line_item_ids, field_count

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

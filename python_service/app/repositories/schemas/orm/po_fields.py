"""PO extracted-field ORM models (ER: PO_HEADER_FIELDS, PO_LINE_ITEM_FIELDS).

Extracted document values are persisted here — never into PURCHASE_ORDERS or
PO_LINE_ITEMS. Each row pairs a canonical FIELD_DEFINITIONS reference with the
extracted string value.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Text

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class POHeaderField(Base, ModifiedTimestampMixin):
    __tablename__ = "po_header_fields"

    id = Column(GUID(), primary_key=True, default=new_uuid_id)
    po_id = Column(GUID(), ForeignKey("purchase_orders.po_id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = Column(GUID(), ForeignKey("field_definitions.field_id", ondelete="CASCADE"), nullable=False, index=True)
    field_value = Column(Text, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<POHeaderField po_id={self.po_id} field_id={self.field_id}>"


class POLineItemField(Base, ModifiedTimestampMixin):
    __tablename__ = "po_line_item_fields"

    id = Column(GUID(), primary_key=True, default=new_uuid_id)
    po_line_item_id = Column(
        GUID(), ForeignKey("po_line_items.po_line_item_id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_id = Column(GUID(), ForeignKey("field_definitions.field_id", ondelete="CASCADE"), nullable=False, index=True)
    field_value = Column(Text, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<POLineItemField po_line_item_id={self.po_line_item_id} field_id={self.field_id}>"

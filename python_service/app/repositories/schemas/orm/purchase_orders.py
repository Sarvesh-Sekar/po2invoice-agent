"""Purchase order + line item ORM models (ER: PURCHASE_ORDERS, PO_LINE_ITEMS).

PURCHASE_ORDERS carries ONLY PO-level metadata. Extracted document values live
in PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS referenced through FIELD_DEFINITIONS.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Text

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class PurchaseOrder(Base, ModifiedTimestampMixin):
    __tablename__ = "purchase_orders"

    po_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    customer_id = Column(GUID(), ForeignKey("customers.customer_id", ondelete="SET NULL"), nullable=True, index=True)
    s3_url = Column(Text, nullable=True)
    created_by = Column(GUID(), nullable=True)
    modified_by = Column(GUID(), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<PurchaseOrder po_id={self.po_id} customer_id={self.customer_id}>"


class POLineItem(Base, ModifiedTimestampMixin):
    __tablename__ = "po_line_items"

    po_line_item_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    po_id = Column(GUID(), ForeignKey("purchase_orders.po_id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(GUID(), ForeignKey("products.product_id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<POLineItem po_line_item_id={self.po_line_item_id} po_id={self.po_id}>"

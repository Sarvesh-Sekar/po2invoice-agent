"""Invoice ORM model (ER: INVOICES).

Invoices reference the purchase order directly through ``po_id``.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Text

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class Invoice(Base, ModifiedTimestampMixin):
    __tablename__ = "invoices"

    invoice_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    po_id = Column(GUID(), ForeignKey("purchase_orders.po_id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_number = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    gst_irn = Column(String(128), nullable=True)
    s3_url = Column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Invoice invoice_id={self.invoice_id} status={self.status}>"

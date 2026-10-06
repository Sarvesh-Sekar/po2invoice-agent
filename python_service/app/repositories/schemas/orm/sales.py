"""Sale ORM model (ER: SALES).

Sales reference the purchase order directly through ``po_id``.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class Sale(Base, ModifiedTimestampMixin):
    __tablename__ = "sales"

    sale_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    po_id = Column(GUID(), ForeignKey("purchase_orders.po_id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="CREATED", index=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Sale sale_id={self.sale_id} status={self.status}>"

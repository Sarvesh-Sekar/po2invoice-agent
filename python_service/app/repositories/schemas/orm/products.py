"""Product ORM model (ER2: PRODUCTS).

ER2 shape: catalogue price is ``catalog_price``; stock and legacy ER1
profile flags were removed in favour of extracted FIELD_DEFINITIONS values.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Column, Numeric, String

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class Product(Base, ModifiedTimestampMixin):
    __tablename__ = "products"

    product_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    sku = Column(String(128), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    catalog_price = Column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Product product_id={self.product_id} sku={self.sku}>"

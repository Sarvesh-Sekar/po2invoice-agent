"""Customer ORM model (ER2: CUSTOMERS).

ER2 shape: identity is the ``customer_code``; free-text/profile columns
(``email``/``phone``/``gst_no``) were removed in favour of extracted
FIELD_DEFINITIONS values.
"""

from __future__ import annotations

from sqlalchemy import Column, String

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class Customer(Base, ModifiedTimestampMixin):
    __tablename__ = "customers"

    customer_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    customer_code = Column(String(64), nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Customer customer_id={self.customer_id} name={self.name}>"

"""Field definition ORM model (ER: FIELD_DEFINITIONS).

FIELD_DEFINITIONS is the canonical registry of extractable PO fields. Both
PO_HEADER_FIELDS and PO_LINE_ITEM_FIELDS reference it, and the extraction
agent works dynamically against it rather than hardcoding columns.
"""

from __future__ import annotations

from sqlalchemy import Column, String

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class FieldDefinition(Base, ModifiedTimestampMixin):
    __tablename__ = "field_definitions"

    field_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    field_name = Column(String(128), nullable=False, unique=True, index=True)
    field_description = Column(String(500), nullable=True)
    field_type = Column(String(32), nullable=False, default="string")

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<FieldDefinition field_id={self.field_id} field_name={self.field_name}>"

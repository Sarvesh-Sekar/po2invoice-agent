"""Episodic memory ORM model (ER: EPISODIC_MEMORY).

Stores customer-specific *extraction knowledge* (location hints, document
patterns, instructions) — never extracted values.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, ModifiedTimestampMixin, new_uuid_id


class EpisodicMemory(Base, ModifiedTimestampMixin):
    __tablename__ = "episodic_memory"

    id = Column(GUID(), primary_key=True, default=new_uuid_id)
    customer_id = Column(GUID(), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False, index=True)
    field_id = Column(GUID(), ForeignKey("field_definitions.field_id", ondelete="CASCADE"), nullable=False, index=True)
    location_hint = Column(String(255), nullable=True)
    document_pattern = Column(String(255), nullable=True)
    instruction = Column(Text, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=False, default=Decimal("0.5"))
    usage_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<EpisodicMemory customer_id={self.customer_id} field_id={self.field_id}>"

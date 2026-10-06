"""Agent run persistence model.

One row per workflow execution. The `thread_id` is the LangGraph checkpoint
identity and remains stable for HITL resume.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, String, Text

from app.repositories.database import Base
from app.repositories.schemas.orm.base import GUID, TimestampMixin, new_uuid_id


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_idempotency_key", "idempotency_key"),)

    run_id = Column(GUID(), primary_key=True, default=new_uuid_id)
    thread_id = Column(String(255), nullable=False, unique=True, index=True)
    workflow = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    current_step = Column(String(64), nullable=True)
    po_id = Column(GUID(), nullable=True)
    sale_id = Column(GUID(), nullable=True)
    invoice_id = Column(GUID(), nullable=True)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(64), nullable=True)
    source_file_url = Column(Text, nullable=True)
    idempotency_key = Column(String(255), nullable=True)
    hitl_context = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - repr is cosmetic
        return f"<AgentRun run_id={self.run_id} status={self.status} workflow={self.workflow}>"

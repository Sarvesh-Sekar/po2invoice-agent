"""Agent run persistence operations."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.logging import get_logger
from app.repositories.schemas.orm.agent_run import AgentRun

logger = get_logger(__name__)


class AgentRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create(
        self,
        *,
        run_id: str,
        thread_id: str,
        workflow: str,
        status: str,
        current_step: str | None = None,
        file_name: str | None = None,
        mime_type: str | None = None,
        source_file_url: str | None = None,
        idempotency_key: str | None = None,
    ) -> AgentRun:
        async with self._sf() as session:
            run = AgentRun(
                run_id=run_id,
                thread_id=thread_id,
                workflow=workflow,
                status=status,
                current_step=current_step,
                file_name=file_name,
                mime_type=mime_type,
                source_file_url=source_file_url,
                idempotency_key=idempotency_key,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

            logger.debug("run_created: run_id=%s | thread_id=%s | workflow=%s", run_id, thread_id, workflow)
            return run

    async def get(self, run_id: str) -> AgentRun | None:
        async with self._sf() as session:
            result = await session.execute(select(AgentRun).where(AgentRun.run_id == run_id))
            run = result.scalar_one_or_none()
            logger.debug("run_fetched: run_id=%s | found=%s", run_id, run is not None)
            return run

    async def get_by_thread_id(self, thread_id: str) -> AgentRun | None:
        async with self._sf() as session:
            result = await session.execute(select(AgentRun).where(AgentRun.thread_id == thread_id))
            return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> AgentRun | None:
        async with self._sf() as session:
            result = await session.execute(
                select(AgentRun).where(
                    AgentRun.idempotency_key == idempotency_key,
                    AgentRun.workflow == "INVOICE",
                )
            )
            return result.scalar_one_or_none()

    async def get_by_invoice_id(self, invoice_id: str) -> AgentRun | None:
        async with self._sf() as session:
            result = await session.execute(
                select(AgentRun).where(AgentRun.invoice_id == invoice_id, AgentRun.workflow == "INVOICE")
            )
            return result.scalar_one_or_none()

    async def update_status(
        self,
        run_id: str,
        *,
        status: str,
        current_step: str | None = None,
        po_id: str | None = None,
        sale_id: str | None = None,
        invoice_id: str | None = None,
        hitl_context: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> AgentRun | None:
        async with self._sf() as session:
            values: dict = {"status": status}
            if current_step is not None:
                values["current_step"] = current_step
            if po_id is not None:
                values["po_id"] = po_id
            if sale_id is not None:
                values["sale_id"] = sale_id
            if invoice_id is not None:
                values["invoice_id"] = invoice_id
            if hitl_context is not None:
                values["hitl_context"] = hitl_context
            if error_code is not None:
                values["error_code"] = error_code
            if error_message is not None:
                values["error_message"] = error_message

            await session.execute(update(AgentRun).where(AgentRun.run_id == run_id).values(**values))
            await session.commit()

            result = await session.execute(select(AgentRun).where(AgentRun.run_id == run_id))
            run = result.scalar_one_or_none()
            logger.debug(
                "run_status_changed: run_id=%s | status=%s | step=%s",
                run_id,
                status,
                current_step,
            )
            return run

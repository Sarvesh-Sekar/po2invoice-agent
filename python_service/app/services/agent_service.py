"""Agent orchestration service: coordinates workflow use cases.

The service decides what the agent workflows should do, persists run state,
and invokes the compiled orchestrators. It never executes agent logic.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import UploadFile

from app.clients.base import BaseS3Client
from app.config.logging import get_logger
from app.config.settings import Settings
from app.exceptions.agent_exceptions import (
    POFileTooLargeError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
)
from app.helpers.file_helper import guess_mime_type, validate_po_file
from app.helpers.hitl_context import interrupt_hitl_payload, parse_hitl_context
from app.helpers.idempotency import normalize_idempotency_key
from app.models.requests.internal_event import SaleDeliveredEvent
from app.models.responses.agent_response import AgentRunResponse, HitlContext
from app.orchestrator_service.base_orchestrator import BaseOrchestrator
from app.repositories.repositories.agent_run_repository import AgentRunRepository
from app.repositories.repositories.invoice_repository import InvoiceRepository
from app.repositories.schemas.orm.agent_run import AgentRun

STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_WAITING = "WAITING_FOR_HUMAN"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"


class AgentService:
    def __init__(
        self,
        po_orchestrator: BaseOrchestrator,
        invoice_orchestrator: BaseOrchestrator,
        agent_run_repository: AgentRunRepository,
        settings: Settings,
        s3_client: BaseS3Client | None = None,
        invoice_repository: InvoiceRepository | None = None,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._po = po_orchestrator
        self._invoice = invoice_orchestrator
        self._repo = agent_run_repository
        self._settings = settings
        self._s3 = s3_client
        self._invoices = invoice_repository
        self._logger = logger or get_logger("app.services.agent")

    # ------------------------------------------------------------------ PO --

    async def process_purchase_order(self, file: UploadFile) -> AgentRunResponse:
        started = time.perf_counter()
        file_name = file.filename or "purchase-order.pdf"

        content = await file.read()
        validate_po_file(
            file_name,
            len(content),
            self._settings.allowed_extensions,
            self._settings.max_upload_size_bytes,
        )
        if len(content) > self._settings.max_upload_size_bytes:
            raise POFileTooLargeError(details={"max_size_bytes": self._settings.max_upload_size_bytes})

        run_id = str(uuid.uuid4())
        thread_id = f"po-{run_id}"
        self._logger.info(
            "workflow_start: PURCHASE_ORDER | run_id=%s | thread_id=%s | file_name=%s | size_bytes=%s",
            run_id,
            thread_id,
            file_name,
            len(content),
        )

        source_file_url: str | None = None
        if self._s3 is not None and self._settings.aws_s3_bucket:
            prefix = self._settings.aws_s3_key_prefix or "po"
            source_file_url = await self._s3.upload(
                content,
                f"{prefix.strip('/')}/{run_id}/{file_name}",
                guess_mime_type(file_name),
            )
            self._logger.info("document_uploaded: run_id=%s | source_file_url=%s", run_id, source_file_url)

        run = await self._repo.create(
            run_id=run_id,
            thread_id=thread_id,
            workflow="PURCHASE_ORDER",
            status=STATUS_RUNNING,
            current_step="queued",
            file_name=file_name,
            mime_type=guess_mime_type(file_name),
            source_file_url=source_file_url,
        )

        state: dict[str, Any] = {
            "run_id": str(run_id),
            "thread_id": thread_id,
            "workflow": "PURCHASE_ORDER",
            "file_bytes": content,
            "file_name": file_name,
            "mime_type": guess_mime_type(file_name),
            "source_file_url": source_file_url,
            "status": STATUS_RUNNING,
            "current_step": "queued",
        }
        result = await self._po.invoke(state, thread_id)
        response = await self._finalize_po_run(run, result)
        self._logger.info(
            "workflow_end: PURCHASE_ORDER | run_id=%s | thread_id=%s | duration_ms=%.3f | status=%s | step=%s",
            run_id,
            thread_id,
            (time.perf_counter() - started) * 1000,
            response.status,
            response.current_step,
        )
        return response

    async def _finalize_po_run(self, run: AgentRun, result: dict[str, Any]) -> AgentRunResponse:
        if "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            hint = interrupts[0].value if interrupts else None
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_WAITING,
                current_step="hitl",
                hitl_context=json.dumps(interrupt_hitl_payload(hint), default=str),
            )
            self._logger.info("workflow_paused: run_id=%s | status=%s | waiting_for=human", run.run_id, STATUS_WAITING)
            return self._to_response(run)

        if result.get("sale_id"):
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_COMPLETED,
                current_step="sales",
                po_id=result.get("po_id"),
                sale_id=result.get("sale_id"),
            )
        elif result.get("workflow_error") or result.get("status") == STATUS_FAILED:
            error = result.get("workflow_error") or {}
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_FAILED,
                current_step=result.get("current_step"),
                error_code=error.get("code") if isinstance(error, dict) else None,
                error_message=error.get("message") if isinstance(error, dict) else str(error),
            )
            self._logger.error(
                "workflow_failed: run_id=%s | step=%s | error_code=%s",
                run.run_id,
                result.get("current_step"),
                error.get("code") if isinstance(error, dict) else None,
            )
        else:
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_RUNNING,
                current_step=result.get("current_step") or "in_progress",
            )
            self._logger.info(
                "workflow_incomplete: run_id=%s | step=%s | status=%s",
                run.run_id,
                result.get("current_step"),
                STATUS_RUNNING,
            )
        return self._to_response(run)

    # ---------------------------------------------------------------- runs --

    async def get_run(self, run_id: str) -> AgentRunResponse:
        run = await self._repo.get(run_id)
        if run is None:
            raise WorkflowNotFoundError(details={"run_id": str(run_id)})
        return self._to_response(run)

    # ------------------------------------------------------- sale delivered --

    async def handle_sale_delivered(self, event: SaleDeliveredEvent) -> AgentRunResponse:
        key = normalize_idempotency_key(event.idempotency_key, str(event.sale_id))
        existing = await self._repo.get_by_idempotency_key(key)
        if existing is not None:
            self._logger.info(
                "sale_delivered_duplicate: sale_id=%s | idempotency_key=%s",
                str(event.sale_id),
                key,
            )
            return self._to_response(existing)

        # A redelivery can carry a fresh key; the sale relationship is what makes
        # an invoice unique, so return the one already raised instead of duplicating.
        existing_invoice = await self._invoices.get_by_sale(str(event.sale_id))
        if existing_invoice is not None:
            self._logger.info(
                "sale_delivered_duplicate: sale_id=%s | invoice_id=%s | reason=invoice_exists",
                str(event.sale_id),
                existing_invoice.invoice_id,
            )
            # Prefer the original run when it is still on record, so the caller
            # gets the real run_id; otherwise report the invoice itself.
            prior_run = await self._repo.get_by_invoice_id(existing_invoice.invoice_id)
            if prior_run is not None:
                return self._to_response(prior_run)
            return AgentRunResponse(
                run_id=str(uuid.uuid4()),
                workflow="INVOICE",
                status=STATUS_COMPLETED,
                current_step="invoice",
                sale_id=str(event.sale_id),
                invoice_id=str(existing_invoice.invoice_id),
                hitl=None,
            )

        run_id = str(uuid.uuid4())
        thread_id = f"invoice-{run_id}"
        started = time.perf_counter()
        self._logger.info(
            "workflow_start: INVOICE | run_id=%s | thread_id=%s | sale_id=%s | idempotency_key=%s",
            run_id,
            thread_id,
            event.sale_id,
            key,
        )
        run = await self._repo.create(
            run_id=run_id,
            thread_id=thread_id,
            workflow="INVOICE",
            status=STATUS_RUNNING,
            current_step="queued",
            idempotency_key=key,
        )

        state: dict[str, Any] = {
            "run_id": str(run_id),
            "thread_id": thread_id,
            "workflow": "INVOICE",
            "sale_id": str(event.sale_id),
            "idempotency_key": key,
            "status": STATUS_RUNNING,
            "current_step": "invoice",
        }
        try:
            result = await self._invoice.invoke(state, thread_id)
        except WorkflowExecutionError as exc:
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_FAILED,
                current_step="invoice",
                error_code=exc.code,
                error_message=exc.message,
            )
            self._logger.error(
                "workflow_failed: INVOICE | run_id=%s | step=invoice | error_code=%s | duration_ms=%.3f",
                run_id,
                exc.code,
                (time.perf_counter() - started) * 1000,
            )
            return self._to_response(run)

        if result.get("workflow_error") or result.get("status") == STATUS_FAILED:
            error = result.get("workflow_error") or {}
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_FAILED,
                error_code=error.get("code"),
                error_message=error.get("message"),
            )
            log = self._logger.error
        elif result.get("invoice_id"):
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_COMPLETED,
                current_step="invoice",
                sale_id=result.get("sale_id") or run.sale_id,
                invoice_id=result.get("invoice_id"),
            )
            log = self._logger.info
        else:
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_RUNNING,
                current_step=result.get("current_step") or "in_progress",
            )
            log = self._logger.warning
        log(
            "workflow_end: INVOICE | run_id=%s | thread_id=%s | duration_ms=%.3f | status=%s | step=%s | invoice_id=%s",
            run_id,
            thread_id,
            (time.perf_counter() - started) * 1000,
            run.status,
            run.current_step,
            run.invoice_id,
        )
        return self._to_response(run)

    # ---------------------------------------------------------------- misc --

    def _to_response(self, run: AgentRun | None) -> AgentRunResponse:
        if run is None:
            raise WorkflowNotFoundError()
        hitl: HitlContext | None = None
        if run.status == STATUS_WAITING:
            hitl_info = parse_hitl_context(run.hitl_context)
            hitl = HitlContext(
                message="Purchase order requires human decision",
                options=["APPROVE", "REJECT", "EDIT"],
                question=hitl_info.get("question"),
                context=hitl_info.get("context") or {},
            )
        return AgentRunResponse(
            run_id=str(run.run_id),
            workflow=run.workflow,  # type: ignore[arg-type]
            status=run.status,  # type: ignore[arg-type]
            current_step=run.current_step,
            po_id=str(run.po_id) if run.po_id else None,
            sale_id=str(run.sale_id) if run.sale_id else None,
            invoice_id=str(run.invoice_id) if run.invoice_id else None,
            hitl=hitl,
        )

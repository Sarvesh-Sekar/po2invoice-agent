"""HITL decision service: resumes workflows paused for human review."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.config.logging import get_logger
from app.exceptions.agent_exceptions import (
    HITLNotPendingError,
    WorkflowAlreadyCompletedError,
    WorkflowNotFoundError,
)
from app.helpers.hitl_context import interrupt_hitl_payload
from app.models.requests.hitl_request import HITLDecisionRequest
from app.models.responses.agent_response import AgentRunResponse
from app.orchestrator_service.base_orchestrator import BaseOrchestrator
from app.repositories.repositories.agent_run_repository import AgentRunRepository

STATUS_WAITING = "WAITING_FOR_HUMAN"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"


class HITLService:
    def __init__(
        self,
        po_orchestrator: BaseOrchestrator,
        agent_run_repository: AgentRunRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._po = po_orchestrator
        self._repo = agent_run_repository
        self._logger = logger or get_logger("app.services.hitl")

    async def submit_decision(self, run_id: str, request: HITLDecisionRequest) -> AgentRunResponse:
        started = time.perf_counter()
        run = await self._repo.get(run_id)
        if run is None:
            self._logger.warning("hitl_lookup_failed: run_id=%s | reason=not_found", run_id)
            raise WorkflowNotFoundError(details={"run_id": str(run_id)})

        if run.status != STATUS_WAITING:
            if run.status in (STATUS_COMPLETED, STATUS_FAILED):
                self._logger.warning(
                    "hitl_rejected: run_id=%s | thread_id=%s | status=%s | reason=already_completed",
                    run_id,
                    run.thread_id,
                    run.status,
                )
                raise WorkflowAlreadyCompletedError(
                    details={
                        "run_id": str(run_id),
                        "status": run.status,
                        "reason": "workflow is no longer waiting for a decision",
                    }
                )
            self._logger.warning(
                "hitl_rejected: run_id=%s | thread_id=%s | status=%s | reason=not_pending",
                run_id,
                run.thread_id,
                run.status,
            )
            raise HITLNotPendingError(details={"run_id": str(run_id), "status": run.status})

        self._logger.info(
            "hitl_decision_received: run_id=%s | thread_id=%s | decision=%s | changed_field_count=%d",
            run_id,
            run.thread_id,
            request.decision,
            len(request.changes or {}),
        )

        resume_value: dict[str, Any] = {
            "decision": request.decision,
            "changes": request.changes,
            "reason": request.reason,
            "submitted_at": datetime.now(UTC).isoformat(),
        }

        # Same run, same thread_id, same checkpoint — resume, never new thread.
        result = await self._po.resume(run.thread_id, resume_value)

        if "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            hint = interrupts[0].value if interrupts else None
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_WAITING,
                current_step="hitl",
                hitl_context=json.dumps(interrupt_hitl_payload(hint), default=str),
            )
        elif result.get("sale_id"):
            run = await self._repo.update_status(
                run.run_id,
                status=STATUS_COMPLETED,
                current_step="sales",
                po_id=result.get("po_id"),
                sale_id=result.get("sale_id"),
            )
        else:
            final_status = STATUS_FAILED if result.get("status") == "FAILED" else STATUS_RUNNING
            run = await self._repo.update_status(
                run.run_id,
                status=final_status,
                current_step=result.get("current_step") or "in_progress",
            )
        self._logger.info(
            "hitl_resume_end: run_id=%s | thread_id=%s | duration_ms=%.3f | status=%s | step=%s",
            run_id,
            run.thread_id,
            (time.perf_counter() - started) * 1000,
            run.status,
            run.current_step,
        )
        return self._to_response(run)

    def _to_response(self, run) -> AgentRunResponse:
        return AgentRunResponse(
            run_id=str(run.run_id),
            workflow=run.workflow,  # type: ignore[arg-type]
            status=run.status,  # type: ignore[arg-type]
            current_step=run.current_step,
            po_id=str(run.po_id) if run.po_id else None,
            sale_id=str(run.sale_id) if run.sale_id else None,
            invoice_id=str(run.invoice_id) if run.invoice_id else None,
        )

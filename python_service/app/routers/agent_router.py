"""Agent orchestration HTTP endpoints (frontend-facing, user-authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_agent_service, get_hitl_service
from app.models.requests.hitl_request import HITLDecisionRequest
from app.models.responses.agent_response import AgentRunResponse
from app.services.agent_service import AgentService
from app.services.hitl_service import HITLService

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/purchase-orders/process",
    status_code=202,
    response_model=AgentRunResponse,
    summary="Start PO extraction and verification workflow",
)
async def process_purchase_order(
    file: UploadFile = File(...),
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    return await service.process_purchase_order(file)


@router.post(
    "/purchase-orders/{run_id}/decision",
    status_code=202,
    response_model=AgentRunResponse,
    summary="Submit HITL decision and resume workflow",
)
async def submit_decision(
    run_id: str,
    payload: HITLDecisionRequest,
    service: HITLService = Depends(get_hitl_service),
) -> AgentRunResponse:
    return await service.submit_decision(run_id, payload)


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunResponse,
    summary="Get agent workflow status",
)
async def get_run(
    run_id: str,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    return await service.get_run(run_id)

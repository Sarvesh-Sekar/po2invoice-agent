"""Internal integration endpoints (Go service -> Python service)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_internal_api_key
from app.dependencies.services import get_agent_service
from app.models.requests.internal_event import SaleDeliveredEvent
from app.models.responses.agent_response import AgentRunResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/events/sale-delivered",
    status_code=202,
    response_model=AgentRunResponse,
    summary="Handle sale delivered event from Go service",
    dependencies=[Depends(require_internal_api_key)],
)
async def sale_delivered(
    event: SaleDeliveredEvent,
    service: AgentService = Depends(get_agent_service),
) -> AgentRunResponse:
    return await service.handle_sale_delivered(event)

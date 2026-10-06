"""FastAPI dependency providers.

Dependencies resolve services from the app container attached to
`app.state.container` during startup, which makes them trivially overridable
in tests via `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from app.services.agent_service import AgentService
from app.services.hitl_service import HITLService

if TYPE_CHECKING:
    from app.containers import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


async def get_agent_service(request: Request) -> AgentService:
    return request.app.state.container.agent_service


async def get_hitl_service(request: Request) -> HITLService:
    return request.app.state.container.hitl_service

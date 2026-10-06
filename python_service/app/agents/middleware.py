"""LangChain agent middleware.

Wraps model and tool calls for tracing / structured logging without coupling
agent implementations to a logging framework.

Tool calls log their start at INFO so a live run can be followed, completion at
DEBUG to keep volume manageable, and failure at ERROR so it is never invisible.
Argument *keys* are logged; argument *values* are not (they carry customer PII).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware

from app.config.logging import get_logger

logger = get_logger(__name__)


def _tool_name(tool_call: Any) -> str | None:
    """Read a tool-call name from either a mapping or an object payload."""
    if tool_call is None:
        return None
    if isinstance(tool_call, dict):
        return tool_call.get("name")
    return getattr(tool_call, "name", None)


def _arg_keys(tool_call: Any) -> list[str]:
    """Read tool argument *names* only; values are never logged."""
    if tool_call is None:
        return []
    args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", None)
    if isinstance(args, dict):
        return sorted(str(key) for key in args)
    return []


class TracingMiddleware(AgentMiddleware):
    """Logs model and tool calls emitted by create_agent() agents."""

    name = "tracing"

    def __init__(self, agent_name: str = "unknown") -> None:
        super().__init__()
        self.agent_name = agent_name

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        tool = _tool_name(getattr(request, "tool_call", None))
        arg_keys = _arg_keys(getattr(request, "tool_call", None))
        started = time.perf_counter()
        logger.info(
            "tool_started: %s | agent=%s | arg_keys=%s",
            tool,
            self.agent_name,
            arg_keys,
        )
        try:
            result = await handler(request)
        except Exception as exc:
            logger.exception(
                "tool_failed: %s | agent=%s | duration_ms=%.3f | error=%s: %s",
                tool,
                self.agent_name,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            raise
        logger.debug(
            "tool_completed: %s | agent=%s | duration_ms=%.3f",
            tool,
            self.agent_name,
            (time.perf_counter() - started) * 1000,
        )
        return result

    async def awrap_model_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        started = time.perf_counter()
        logger.debug("model_call_started: agent=%s", self.agent_name)
        try:
            result = await handler(request)
        except Exception as exc:
            logger.exception(
                "model_call_failed: agent=%s | duration_ms=%.3f | error=%s: %s",
                self.agent_name,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            raise
        logger.info(
            "model_call_completed: agent=%s | duration_ms=%.3f",
            self.agent_name,
            (time.perf_counter() - started) * 1000,
        )
        return result

    def wrap_tool_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        return self.awrap_tool_call(request, handler)  # pragma: no cover - sync shim

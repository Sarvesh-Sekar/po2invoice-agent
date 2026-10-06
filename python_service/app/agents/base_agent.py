"""Common agent abstraction.

All agents expose `execute(state) -> state_update` for a single workflow step
and `create_agent()/invoke_agent()` for the LangGraph/LangChain agent interface.
Error handling, timing, and structured logging are centralized here.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.config.logging import get_logger


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self._logger = get_logger(f"app.agents.{self.name}")

    @abstractmethod
    def create_agent(self) -> Any:
        """Compile the LangChain agent (asyncio.create_agent / StateGraph)."""
        raise NotImplementedError

    @abstractmethod
    async def invoke_agent(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Invoke the compiled agent asynchronously and return a state update."""
        raise NotImplementedError

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Perform the agent's workflow step and return state updates."""
        raise NotImplementedError

    async def run(self, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Callable entry point used by the orchestrator (node).

        Dispatches to `invoke_agent` for agents that manage their own compiled
        graph; subclasses may still use `execute` internally.
        """
        started = time.perf_counter()
        run_id = state.get("run_id")
        thread_id = state.get("thread_id")
        step = state.get("current_step")
        self._logger.info(
            "agent_started: %s | run_id=%s | thread_id=%s | step=%s",
            self.name,
            run_id,
            thread_id,
            step,
        )
        try:
            update = await self.invoke_agent(state, **kwargs)
        except Exception as exc:
            self._logger.exception(
                "agent_failed: %s | run_id=%s | thread_id=%s | step=%s | duration_ms=%.3f | error=%s: %s",
                self.name,
                run_id,
                thread_id,
                step,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                exc,
            )
            raise
        self._logger.info(
            "agent_completed: %s | run_id=%s | thread_id=%s | step=%s | duration_ms=%.3f | status=%s",
            self.name,
            run_id,
            thread_id,
            (update or {}).get("current_step") or step,
            (time.perf_counter() - started) * 1000,
            (update or {}).get("status"),
        )
        return update

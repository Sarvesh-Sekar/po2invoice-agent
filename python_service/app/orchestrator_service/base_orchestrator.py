"""Base orchestrator: owns a compiled LangGraph.

Compilation happens exactly once at application startup. Invocation (and
HITL resume) happens at the service layer using a stable thread_id.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from langgraph.graph import StateGraph
from langgraph.types import Command

from app.exceptions.agent_exceptions import WorkflowExecutionError


class BaseOrchestrator(ABC):
    name: str = "base"

    def __init__(self, checkpointer: Any, *, logger: logging.Logger | None = None) -> None:
        self.checkpointer = checkpointer
        self.compiled_graph: Any | None = None
        self._logger = logger or logging.getLogger(f"app.orchestrator.{self.name}")

    def config(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    @abstractmethod
    def _build_graph(self) -> StateGraph:
        """Build the StateGraph with nodes, edges, and conditional edges."""

    async def compile(self) -> None:
        """Compile the graph once at startup with the durable checkpointer."""
        if self.compiled_graph is not None:
            return
        started = time.perf_counter()
        graph = self._build_graph()
        try:
            self.compiled_graph = graph.compile(checkpointer=self.checkpointer)
        except Exception as exc:
            self._logger.exception("graph_compilation_failed: workflow=%s", self.name)
            raise WorkflowExecutionError(details={"reason": f"graph compilation failed: {exc}"}) from exc
        self._logger.info(
            "graph_compiled: workflow=%s | duration_ms=%.3f",
            self.name,
            (time.perf_counter() - started) * 1000,
        )

    async def invoke(self, input_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        run_id = (input_state or {}).get("run_id")
        self._logger.info(
            "graph_invoked: workflow=%s | run_id=%s | thread_id=%s",
            self.name,
            run_id,
            thread_id,
        )
        if self.compiled_graph is None:
            raise WorkflowExecutionError(details={"reason": "graph not compiled"})
        try:
            result = await self.compiled_graph.ainvoke(input_state, config=self.config(thread_id))
        except Exception as exc:
            self._logger.exception(
                "graph_invocation_failed: workflow=%s | run_id=%s | thread_id=%s | duration_ms=%.3f",
                self.name,
                run_id,
                thread_id,
                (time.perf_counter() - started) * 1000,
            )
            raise WorkflowExecutionError(details={"reason": str(exc)[:500]}) from exc
        if not isinstance(result, dict):
            result = {"workflow_result": result}
        self._logger.info(
            "graph_completed: workflow=%s | run_id=%s | thread_id=%s | duration_ms=%.3f | status=%s | step=%s | "
            "interrupted=%s",
            self.name,
            run_id,
            thread_id,
            (time.perf_counter() - started) * 1000,
            result.get("status"),
            result.get("current_step"),
            "__interrupt__" in result,
        )
        return result

    async def resume(self, thread_id: str, resume_value: Any) -> dict[str, Any]:
        """Resume a paused graph with the same thread_id (never a new thread)."""
        started = time.perf_counter()
        run_id = (resume_value or {}).get("run_id") if isinstance(resume_value, dict) else None
        self._logger.info(
            "graph_resumed: workflow=%s | run_id=%s | thread_id=%s",
            self.name,
            run_id,
            thread_id,
        )
        if self.compiled_graph is None:
            raise WorkflowExecutionError(details={"reason": "graph not compiled"})
        try:
            result = await self.compiled_graph.ainvoke(
                Command(resume=resume_value),
                config=self.config(thread_id),
            )
        except Exception as exc:
            self._logger.exception(
                "graph_resume_failed: workflow=%s | run_id=%s | thread_id=%s | duration_ms=%.3f",
                self.name,
                run_id,
                thread_id,
                (time.perf_counter() - started) * 1000,
            )
            raise WorkflowExecutionError(details={"reason": str(exc)[:500]}) from exc
        if not isinstance(result, dict):
            result = {"workflow_result": result}
        self._logger.info(
            "graph_resume_completed: workflow=%s | run_id=%s | thread_id=%s | duration_ms=%.3f | status=%s | "
            "step=%s | interrupted=%s",
            self.name,
            run_id,
            thread_id,
            (time.perf_counter() - started) * 1000,
            result.get("status"),
            result.get("current_step"),
            "__interrupt__" in result,
        )
        return result

    async def get_state(self, thread_id: str) -> dict[str, Any]:
        """Return the snapshot (values + next nodes) for a thread."""
        if self.compiled_graph is None:
            raise WorkflowExecutionError(details={"reason": "graph not compiled"})
        snapshot = await self.compiled_graph.aget_state(self.config(thread_id))
        return {
            "values": snapshot.values or {},
            "next": list(snapshot.next or []),
            "interrupts": [interrupt.value for interrupt in (snapshot.interrupts or [])],
        }

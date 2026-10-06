"""Invoice orchestrator: builds and compiles the invoice LangGraph.

Flow: invoice generation (number, data, PDF, persist) -> END

GST IRN generation and invoice message delivery are outside the current
business scope. Both remain available in the codebase (``GSTClient`` /
``generate_invoice_irn`` and ``MessageAgent``) but are not wired into this
graph.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.base_agent import BaseAgent
from app.orchestrator_service.base_orchestrator import BaseOrchestrator
from app.orchestrator_service.graph import InvoiceWorkflowState


class InvoiceOrchestrator(BaseOrchestrator):
    name = "invoice"

    def __init__(
        self,
        invoice_agent: BaseAgent,
        checkpointer: Any,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(checkpointer, logger=logger)
        self.invoice_agent = invoice_agent

    def _finalize(self, state: dict[str, Any]) -> dict[str, Any]:
        """Terminal node: the invoice node itself reports RUNNING."""
        return {"current_step": "invoice", "status": "COMPLETED"}

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(InvoiceWorkflowState)
        graph.add_node("invoice", self.invoice_agent.run)
        graph.add_node("finalize", self._finalize)
        graph.add_edge(START, "invoice")
        graph.add_edge("invoice", "finalize")
        graph.add_edge("finalize", END)
        return graph

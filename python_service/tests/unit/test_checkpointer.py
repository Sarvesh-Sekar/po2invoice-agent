"""Durable checkpointer behaviour: interrupt + resume against Postgres."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class S(TypedDict, total=False):
    x: str


async def _decide(state: dict) -> str:
    decision = interrupt({"question": "approve?", "state": state.get("x")})
    return {"x": decision}


async def _done(state: dict) -> dict:
    return {"x": "done"}


def _route(state: dict) -> str:
    return "done" if state.get("x") == "APPROVE" else END


async def test_interrupt_then_resume(checkpointer):
    saver = checkpointer
    graph = StateGraph(S)
    graph.add_node("decide", _decide)
    graph.add_node("done", _done)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges("decide", _route, {"done": "done", END: END})
    graph.add_edge("done", END)
    compiled = graph.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "thread-1"}}

    first = await compiled.ainvoke({"x": "candidate"}, config=config)
    assert "__interrupt__" in first
    interrupt_value = first["__interrupt__"][0].value
    assert interrupt_value["question"] == "approve?"

    snapshot = await compiled.aget_state(config)
    assert "decide" in list(snapshot.next)

    second = await compiled.ainvoke(Command(resume="APPROVE"), config=config)
    assert second["x"] == "done"

    final = await compiled.aget_state(config)
    assert final.values["x"] == "done"


async def test_reject_ends_workflow(checkpointer):
    saver = checkpointer
    graph = StateGraph(S)
    graph.add_node("decide", _decide)
    graph.add_node("done", _done)
    graph.add_edge(START, "decide")
    graph.add_conditional_edges("decide", _route, {"done": "done", END: END})
    graph.add_edge("done", END)
    compiled = graph.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": "thread-reject"}}
    await compiled.ainvoke({}, config=config)
    result = await compiled.ainvoke(Command(resume="REJECT"), config=config)
    assert "__interrupt__" not in result

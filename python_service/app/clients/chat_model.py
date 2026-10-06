"""LangChain chat model backed by the Bedrock client.

Implements the BaseChatModel contract so langchain's create_agent() can bind
tools and drive the agent loop over AWS Bedrock (Converse API).

The model is async-only: invoke/ainvoke use ``_agenerate``. Sync ``_generate``
is intentionally unsupported.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import PrivateAttr

from app.clients.base import BaseBedrockClient


def _from_openai_tool(openai_tool: dict) -> dict:
    fn = openai_tool.get("function", openai_tool)
    return {
        "name": fn.get("name"),
        "description": fn.get("description"),
        "inputSchema": {"json": fn.get("parameters", {"type": "object", "properties": {}})},
    }


def _to_tool_spec(tool: Any) -> dict:
    if isinstance(tool, dict):
        if "toolSpec" in tool:
            return tool
        return {"toolSpec": _from_openai_tool(tool)}
    if isinstance(tool, type):
        return {"toolSpec": {"name": tool.__name__, "inputSchema": {"json": {"type": "object", "properties": {}}}}}
    if isinstance(tool, BaseTool):
        return {"toolSpec": _from_openai_tool(convert_to_openai_tool(tool))}
    return {"toolSpec": _from_openai_tool(convert_to_openai_tool(tool))}


def _to_bedrock_messages(messages: list[BaseMessage]) -> tuple[list[dict], str | None]:
    system_parts = [str(m.content) for m in messages if isinstance(m, SystemMessage)]
    system = "\n".join(system_parts) if system_parts else None
    converted: list[dict] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            continue
        if isinstance(message, ToolMessage):
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": message.tool_call_id or "",
                                "content": [{"text": str(message.content)}],
                            }
                        }
                    ],
                }
            )
        elif isinstance(message, AIMessage):
            content: list[dict] = []
            if message.content:
                content.append({"text": str(message.content)})
            for index, call in enumerate(message.tool_calls):
                content.append(
                    {
                        "toolUse": {
                            "toolUseId": call.get("id") or f"call_{index}",
                            "name": call["name"],
                            "input": call.get("args") or {},
                        }
                    }
                )
            converted.append({"role": "assistant", "content": content})
        else:
            converted.append({"role": "user", "content": [{"text": str(message.content)}]})
    if not converted:
        # Bedrock rejects a conversation with no messages ("must start with a user message").
        # System-only prompts have to be sent as the user turn to be callable.
        converted.append({"role": "user", "content": [{"text": system or ""}]})
    return converted, system


def _parse_payload(payload: dict) -> tuple[str, list[dict]]:
    blocks = payload.get("output", {}).get("message", {}).get("content", [])
    texts: list[str] = []
    tool_calls: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if "text" in block:
            texts.append(str(block["text"]))
        tool_use = block.get("toolUse")
        if isinstance(tool_use, dict):
            tool_calls.append(
                {
                    "name": tool_use.get("name"),
                    "args": tool_use.get("input") or {},
                    "id": tool_use.get("toolUseId"),
                }
            )
    return "\n".join(texts), tool_calls


class BedrockChatModel(BaseChatModel):
    """Async chat model bound to a BaseBedrockClient."""

    client: BaseBedrockClient
    model_id: str | None = None
    max_tokens: int = 1024
    model_type: str = "chat"

    _tool_specs: list[dict] = PrivateAttr(default_factory=list)
    _tool_choice: str | None = PrivateAttr(default=None)

    @property
    def _llm_type(self) -> str:
        return "bedrock"

    def bind_tools(
        self,
        tools: Sequence[dict | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> BedrockChatModel:
        bound = self.model_copy(update={})
        object.__setattr__(bound, "_tool_specs", [_to_tool_spec(tool) for tool in tools])
        object.__setattr__(bound, "_tool_choice", tool_choice)
        return bound

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("BedrockChatModel is async-only; use asyncio (ainvoke)")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        bedrock_messages, system = _to_bedrock_messages(messages)
        payload = await self.client.converse(
            messages=bedrock_messages,
            system=system,
            max_tokens=self.max_tokens,
            tools=self._tool_specs or None,
        )
        text, tool_calls = _parse_payload(payload)
        if tool_calls and text:
            message = AIMessage(content=text, tool_calls=tool_calls)
        elif tool_calls:
            message = AIMessage(content="", tool_calls=tool_calls)
        else:
            message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message, text=text)])

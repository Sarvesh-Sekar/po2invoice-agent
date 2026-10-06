"""Unit tests for BedrockClient chat paths (Converse API)."""

from __future__ import annotations

from typing import Any

import pytest

from app.clients.bedrock_client import _OCR_SYSTEM, BedrockClient
from app.config.settings import Settings
from app.exceptions.client_exceptions import BedrockError


def _settings(**overrides: Any) -> Settings:
    return Settings(aws_region="us-east-1", aws_bedrock_model_id="amazon.nova-pro-v1:0", **overrides)


class _FakeRuntimeClient:
    def __init__(self, *, response: dict | None = None, error: Exception | None = None) -> None:
        self._response = response or {
            "output": {"message": {"role": "assistant", "content": [{"text": '{"ok": true}'}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 1, "outputTokens": 5, "totalTokens": 6},
        }
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


async def test_converse_uses_boto3_converse_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    payload = await client.converse(
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        system="sys",
        max_tokens=512,
        tools=[{"toolSpec": {"name": "t"}}],
    )

    assert payload == fake._response
    assert fake.calls and "body" not in fake.calls[0]
    call = fake.calls[0]
    assert call["modelId"] == "amazon.nova-pro-v1:0"
    assert call["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]
    assert call["system"] == [{"text": "sys"}]
    assert call["inferenceConfig"] == {"maxTokens": 512}
    assert call["toolConfig"] == {"tools": [{"toolSpec": {"name": "t"}}]}
    assert "guardrailIdentifier" not in call
    assert "guardrailConfig" not in call


async def test_converse_omits_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    await client.converse(messages=[{"role": "user", "content": [{"text": "hi"}]}])

    call = fake.calls[0]
    assert "system" not in call
    assert "toolConfig" not in call
    assert call["inferenceConfig"] == {"maxTokens": 1024}


async def test_converse_wraps_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(error=RuntimeError("boom"))
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError):
        await client.converse(messages=[{"role": "user", "content": [{"text": "hi"}]}])


async def test_complete_extracts_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response={"output": {"message": {"content": [{"text": "hello"}]}}})
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    text = await client.complete("hi", system="sys")

    assert text == "hello"
    assert fake.calls[0]["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


async def test_complete_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response={"output": {"message": {"content": []}}})
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError):
        await client.complete("hi")


def _text_response(text: str) -> dict:
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}, "stopReason": "end_turn"}


async def test_extract_document_sends_pdf_as_converse_document_block(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response=_text_response('```json\n{"fullText": "PO 42"}\n```'))
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    result = await client.extract_document(b"%PDF-1.4", "TRANSCRIBE")

    assert result == {"fullText": "PO 42"}
    call = fake.calls[0]
    assert "body" not in call
    assert call["modelId"] == "amazon.nova-pro-v1:0"
    blocks = call["messages"][0]["content"]
    assert call["messages"][0]["role"] == "user"
    assert blocks[0]["document"]["format"] == "pdf"
    assert blocks[0]["document"]["source"]["bytes"] == b"%PDF-1.4"  # raw bytes, not base64
    assert blocks[-1] == {"text": "TRANSCRIBE"}
    assert call["system"] == [{"text": _OCR_SYSTEM}]
    assert call["inferenceConfig"] == {"maxTokens": 4096}


async def test_extract_document_maps_image_mime_to_image_block(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response=_text_response("{}"))
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    await client.extract_document(b"\xff\xd8", "READ", content_type="image/jpeg; charset=binary")

    assert fake.calls[0]["messages"][0]["content"][0] == {
        "image": {"format": "jpeg", "source": {"bytes": b"\xff\xd8"}},
    }


async def test_extract_document_rejects_unsupported_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client.extract_document(b"II*\x00", "READ", content_type="image/tiff")

    assert excinfo.value.details["reason"] == "unsupported document type for the Bedrock Converse API"
    assert not fake.calls


async def test_extract_document_rejects_empty_document(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError):
        await client.extract_document(b"", "READ")

    assert not fake.calls


async def test_extract_document_parses_json_wrapped_in_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response=_text_response('Here is the document: {"fullText": "PO 42"} - end'))
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    assert await client.extract_document(b"%PDF", "READ") == {"fullText": "PO 42"}


async def test_extract_document_raises_on_non_json_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(response=_text_response("I cannot read that document"))
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client.extract_document(b"%PDF", "READ")

    assert excinfo.value.details["reason"] == "model did not return a valid JSON object"


async def test_invoke_raises_on_empty_response_with_stop_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(
        response={"output": {"message": {"role": "assistant", "content": []}}, "stopReason": "max_tokens"}
    )
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client._invoke("amazon.nova-pro-v1:0", "sys", "prompt")

    assert excinfo.value.details["reason"] == "empty model response"
    assert excinfo.value.details["stopReason"] == "max_tokens"


async def test_invoke_requires_content(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client._invoke("amazon.nova-pro-v1:0", "sys", None)

    assert excinfo.value.details["reason"] == "no content to send to the model"
    assert not fake.calls


async def test_invoke_hints_at_inference_profile_on_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(
        error=Exception(
            "An error occurred (ValidationException) when calling the Converse operation: "
            "Invocation of model ID meta.llama3-3-70b-instruct-v1:0 with on-demand throughput isn't "
            "supported. Retry your request with the ID or ARN of an inference profile."
        )
    )
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client.extract_document(b"%PDF", "READ")

    assert "inference profile" in excinfo.value.details["reason"]
    assert "cross-region inference profile" in excinfo.value.details["hint"]


async def test_invoke_hints_at_model_support_on_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(
        error=Exception(
            "An error occurred (ValidationException) when calling the Converse operation: "
            "The model does not support image input"
        )
    )
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client.extract_document(b"%PDF", "READ")

    assert "model does not support image input" in excinfo.value.details["reason"]
    assert "supports document input" in excinfo.value.details["hint"]


async def test_chat_calls_do_not_get_a_document_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings())
    fake = _FakeRuntimeClient(
        error=Exception("An error occurred (ValidationException) when calling the Converse operation: bad input")
    )
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    with pytest.raises(BedrockError) as excinfo:
        await client.complete("hi")

    assert "hint" not in excinfo.value.details


async def test_extract_text_joins_every_text_block() -> None:
    payload = {"output": {"message": {"content": [{"text": "a"}, {"text": "b"}]}}}
    assert BedrockClient._extract_text(payload) == "a\nb"


async def test_guardrail_is_forwarded_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BedrockClient(_settings(aws_bedrock_guardrail_id="gr-1", aws_bedrock_guardrail_version="1"))
    fake = _FakeRuntimeClient()
    monkeypatch.setattr(client, "_get_client", lambda: fake)

    await client.converse(messages=[{"role": "user", "content": [{"text": "hi"}]}])

    assert fake.calls[0]["guardrailIdentifier"] == "gr-1"
    assert fake.calls[0]["guardrailVersion"] == "1"


def test_system_only_prompt_still_produces_a_user_turn() -> None:
    """Bedrock rejects an empty conversation: 'A conversation must start with a user message'."""
    from langchain_core.messages import SystemMessage

    from app.clients.chat_model import _to_bedrock_messages

    messages, system = _to_bedrock_messages([SystemMessage(content="only a system prompt")])

    assert system == "only a system prompt"
    assert messages == [{"role": "user", "content": [{"text": "only a system prompt"}]}]


def test_system_and_human_messages_map_to_converse_roles() -> None:
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.clients.chat_model import _to_bedrock_messages

    messages, system = _to_bedrock_messages(
        [SystemMessage(content="sys"), HumanMessage(content="extract po_number")],
    )

    assert system == "sys"
    assert messages == [{"role": "user", "content": [{"text": "extract po_number"}]}]

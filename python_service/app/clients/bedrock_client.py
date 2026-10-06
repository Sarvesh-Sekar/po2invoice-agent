"""AWS Bedrock client.

Wraps boto3 so agents never depend directly on boto3. Blocking SDK calls are
offloaded to a thread executor to avoid stalling the event loop. Every model
call goes through the Bedrock Converse API so one client works with any
model that Converse supports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from botocore.config import Config
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.clients.base import BaseBedrockClient
from app.config.logging import get_logger
from app.config.settings import Settings
from app.exceptions.client_exceptions import BedrockError

logger = get_logger(__name__)
retry_logger = get_logger("app.clients.bedrock_client.retry")

_OCR_SYSTEM = (
    "Extract structured data from the supplied document. "
    "Return JSON only. Do not invent values not present in the document."
)

_OCR_MAX_TOKENS = 4096

_INFERENCE_PROFILE_HINT = (
    "This model cannot be invoked with on-demand throughput; it must be addressed through a "
    "cross-region inference profile. Use the region-prefixed id, e.g. "
    "us.meta.llama3-3-70b-instruct-v1:0 (or us.amazon.nova-pro-v1:0) for us-east-1."
)

_DOCUMENT_INPUT_HINT = (
    "The model rejected the document/image input. Use a model that supports document input, "
    "e.g. us.amazon.nova-pro-v1:0 or us.anthropic.claude-3-5-sonnet-20241022-v2:0."
)


def _is_retryable_bedrock_exception(exc: BaseException) -> bool:
    if isinstance(exc, BedrockError):
        details = exc.details or {}
        code = details.get("code") or details.get("errorCode") or details.get("ErrorCode")
        if code and str(code) in _RETRYABLE_BEDROCK_CODES:
            return True
    try:
        from botocore.exceptions import ClientError

        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {}) if hasattr(exc, "response") else {}
            code = error.get("Code") or error.get("code")
            if code and str(code) in _RETRYABLE_BEDROCK_CODES:
                return True
    except Exception:
        pass
    return False


def _error_hint(reason: str) -> str | None:
    """Turn a botocore ValidationException into an actionable hint."""
    lowered = reason.lower()
    if "inference profile" in lowered or "on-demand throughput" in lowered:
        return _INFERENCE_PROFILE_HINT
    if "does not support" in lowered or "invalid input" in lowered:
        return _DOCUMENT_INPUT_HINT
    return None


_RETRYABLE_BEDROCK_CODES = (
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "ServiceUnavailable",
    "ModelTimeoutException",
    "InternalServerException",
    "RequestLimitExceeded",
    "TooManyRequestsException",
)


# MIME type -> Converse document format (text/office documents).
_DOCUMENT_FORMATS: dict[str, str] = {
    "application/pdf": "pdf",
    "application/x-pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "text/html": "html",
}

# MIME type -> Converse image format.
_IMAGE_FORMATS: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/gif": "gif",
    "image/webp": "webp",
}


def _document_content_block(document: bytes, content_type: str) -> dict[str, Any]:
    """Build a Converse document/image content block from raw file bytes.

    Converse takes the raw blob and base64-encodes it on the wire, so the bytes
    are passed through untouched.
    """
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in _DOCUMENT_FORMATS:
        return {
            "document": {
                "name": "document",
                "format": _DOCUMENT_FORMATS[mime],
                "source": {"bytes": document},
            }
        }
    if mime in _IMAGE_FORMATS:
        return {"image": {"format": _IMAGE_FORMATS[mime], "source": {"bytes": document}}}
    raise BedrockError(
        details={
            "content_type": content_type,
            "reason": "unsupported document type for the Bedrock Converse API",
            "supported_content_types": sorted({*_DOCUMENT_FORMATS, *_IMAGE_FORMATS}),
        }
    )


class BedrockClient(BaseBedrockClient):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3

            load_dotenv(override=False)
            # Prefer the dotenv/process environment, then fall back to Settings.
            access_key = os.getenv("AWS_ACCESS_KEY_ID") or self._settings.aws_access_key_id
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or self._settings.aws_secret_access_key
            region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or self._settings.aws_region
            kwargs: dict[str, Any] = {"region_name": region}
            if access_key:
                kwargs["aws_access_key_id"] = access_key
            if secret_key:
                kwargs["aws_secret_access_key"] = secret_key

            config = Config(
                retries={
                    "max_attempts": self._settings.aws_bedrock_max_attempts,
                    "mode": self._settings.aws_bedrock_retry_mode,
                },
                connect_timeout=self._settings.aws_bedrock_connect_timeout,
                read_timeout=self._settings.aws_bedrock_read_timeout,
                max_pool_connections=self._settings.aws_bedrock_max_pool_connections,
            )
            self._client = boto3.client("bedrock-runtime", config=config, **kwargs)
            return self._client
        except Exception as exc:  # pragma: no cover - environment dependent
            raise BedrockError(details={"reason": str(exc)}) from exc

    async def extract_document(self, document: bytes, prompt: str, *, content_type: str = "application/pdf") -> dict:
        """Send the document to the model as a Converse content block and return the parsed reply."""
        if not document:
            raise BedrockError(details={"reason": "empty document"})
        model_id = self._settings.aws_bedrock_ocr_model_id
        return await self._invoke(
            model_id,
            _OCR_SYSTEM,
            prompt,
            content=[_document_content_block(document, content_type)],
            max_tokens=_OCR_MAX_TOKENS,
            json_mode=True,
        )

    async def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        model_id = self._settings.aws_bedrock_model_id
        payload = await self.converse(
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=system,
            max_tokens=max_tokens,
        )
        text = self._extract_text(payload)
        if not text:
            raise BedrockError(details={"model": model_id, "reason": "empty model response"})
        return text

    async def converse(
        self,
        *,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> dict:
        """Call the AWS Bedrock Converse API (model-agnostic) and return the parsed payload."""
        return await self._request(
            self._settings.aws_bedrock_model_id,
            messages,
            system=system,
            max_tokens=max_tokens,
            tools=tools,
        )

    async def _invoke(
        self,
        model_id: str,
        system: str | None,
        prompt: str | None,
        *,
        content: list[dict] | None = None,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str | dict:
        """Single-turn Converse call: content blocks (document/image) plus the prompt.

        Returns the model text, or the parsed JSON object when ``json_mode`` is set.
        """
        blocks: list[dict] = [block for block in (content or []) if block]
        if prompt:
            blocks.append({"text": prompt})
        if not blocks:
            raise BedrockError(details={"model": model_id, "reason": "no content to send to the model"})

        carries_file = any("document" in block or "image" in block for block in blocks)
        payload = await self._request(
            model_id,
            [{"role": "user", "content": blocks}],
            system=system,
            max_tokens=max_tokens,
            hint=_DOCUMENT_INPUT_HINT if carries_file else None,
        )

        text = self._extract_text(payload)
        if not text:
            raise BedrockError(
                details={
                    "model": model_id,
                    "reason": "empty model response",
                    "stopReason": payload.get("stopReason") if isinstance(payload, dict) else None,
                }
            )
        if json_mode:
            return self._extract_json(text, model_id=model_id)
        return text

    async def _request(
        self,
        model_id: str,
        messages: list[dict],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
        hint: str | None = None,
    ) -> dict:
        """Build the Converse request contract and run it off the event loop."""
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        if tools:
            kwargs["toolConfig"] = {"tools": tools}
        if self._settings.aws_bedrock_guardrail_id:
            kwargs["guardrailIdentifier"] = self._settings.aws_bedrock_guardrail_id
            if self._settings.aws_bedrock_guardrail_version:
                kwargs["guardrailVersion"] = self._settings.aws_bedrock_guardrail_version
        started = time.perf_counter()

        client = self._get_client()

        @retry(
            retry=retry_if_exception(_is_retryable_bedrock_exception),
            wait=wait_random_exponential(multiplier=0.5, max=30.0),
            stop=stop_after_attempt(self._settings.aws_bedrock_app_retry_attempts),
            reraise=True,
            before_sleep=before_sleep_log(retry_logger, logging.WARNING),
        )
        def _converse_sync(**call_kwargs: Any) -> Any:
            return client.converse(**call_kwargs)

        try:
            payload = await asyncio.to_thread(_converse_sync, **kwargs)
        except BedrockError:
            logger.exception(
                "llm_call_failed: model=%s | duration_ms=%.3f | error=BedrockError",
                model_id,
                (time.perf_counter() - started) * 1000,
            )
            raise
        except Exception as exc:
            reason = str(exc)[:500]
            details: dict[str, Any] = {"model": model_id, "reason": reason}
            resolved_hint = _error_hint(reason) if hint else None
            if resolved_hint:
                details["hint"] = resolved_hint
            logger.exception(
                "llm_call_failed: model=%s | duration_ms=%.3f | error=%s: %s | hint=%s",
                model_id,
                (time.perf_counter() - started) * 1000,
                type(exc).__name__,
                reason,
                resolved_hint,
            )
            raise BedrockError(details=details) from exc
        usage = payload.get("usage") or {} if isinstance(payload, dict) else {}
        logger.info(
            "llm_call: model=%s | duration_ms=%.3f | input_tokens=%s | output_tokens=%s | stop_reason=%s | "
            "tool_count=%s",
            model_id,
            (time.perf_counter() - started) * 1000,
            usage.get("inputTokens"),
            usage.get("outputTokens"),
            payload.get("stopReason") if isinstance(payload, dict) else None,
            len(tools or []),
        )
        return payload

    @staticmethod
    def _extract_text(payload: dict) -> str:
        """Pull the model text out of a Converse payload (legacy invoke_model shapes included)."""
        if not isinstance(payload, dict):
            return ""
        output = payload.get("output")
        message = output.get("message") if isinstance(output, dict) else None
        blocks = message.get("content") if isinstance(message, dict) else None
        if isinstance(blocks, list):
            texts = [str(block["text"]) for block in blocks if isinstance(block, dict) and block.get("text")]
            if texts:
                return "\n".join(texts)
        for key in ("generatedText", "completion"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        outputs = payload.get("outputs")
        if isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, dict) and isinstance(output.get("text"), str) and output["text"].strip():
                    return output["text"]
        return ""

    @staticmethod
    def _extract_json(text: str, *, model_id: str | None = None) -> dict:
        """Parse the model reply as a JSON object, tolerating markdown fences and surrounding prose."""
        cleaned = (text or "").strip()
        candidates: list[str] = [cleaned]
        if cleaned.startswith("```"):
            fenced = cleaned.split("\n", 1)[-1]
            candidates.append(fenced.removesuffix("```").strip())
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            candidates.append(cleaned[start : end + 1])
        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(parsed, dict):
                return parsed
        raise BedrockError(details={"model": model_id, "reason": "model did not return a valid JSON object"})

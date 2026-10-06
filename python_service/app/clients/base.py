"""Abstract client interfaces.

Agents depend on these abstractions so AWS/GST/WhatsApp implementation details
and failure behaviour can be mocked in tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseBedrockClient(ABC):
    @abstractmethod
    async def extract_document(self, document: bytes, prompt: str, *, content_type: str = "application/pdf") -> dict:
        """Extract structured data from a document using AWS Bedrock OCR."""

    @abstractmethod
    async def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        """Run a text generation request against a Bedrock chat model."""

    async def converse(
        self,
        *,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
    ) -> dict:
        """Low-level chat completion used by the LangChain chat model wrapper."""
        raise NotImplementedError("converse is not implemented by this client")


class BaseS3Client(ABC):
    @abstractmethod
    async def upload(self, file: bytes, key: str, content_type: str) -> str:
        """Upload bytes to S3 and return the object URL / key."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download bytes from S3 by key."""


class BaseGSTClient(ABC):
    @abstractmethod
    async def generate_einvoice(self, payload: dict) -> dict:
        """Call the GST/e-invoice API and return the IRN + API response."""


class BaseWhatsAppClient(ABC):
    @abstractmethod
    async def send_document(self, *, to: str, document_url: str, caption: str) -> dict:
        """Send a document message via WhatsApp."""

    @abstractmethod
    async def send_text(self, *, to: str, message: str) -> dict:
        """Send a text message via WhatsApp."""

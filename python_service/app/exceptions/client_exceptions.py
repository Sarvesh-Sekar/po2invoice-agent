from __future__ import annotations

from app.err_codes import codes
from app.exceptions.base import BaseAppError, ErrorCategory


class BedrockError(BaseAppError):
    def __init__(self, message: str = "AWS Bedrock request failed", details: dict | None = None) -> None:
        super().__init__(
            codes.BEDROCK_ERROR,
            message,
            category=ErrorCategory.CLIENT,
            status_code=502,
            details=details,
        )


class S3Error(BaseAppError):
    def __init__(self, message: str = "S3 operation failed", details: dict | None = None) -> None:
        super().__init__(
            codes.S3_UPLOAD_FAILED,
            message,
            category=ErrorCategory.CLIENT,
            status_code=502,
            details=details,
        )


class GSTError(BaseAppError):
    def __init__(self, message: str = "GST / e-invoice API call failed", details: dict | None = None) -> None:
        super().__init__(
            codes.GST_API_FAILED,
            message,
            category=ErrorCategory.CLIENT,
            status_code=502,
            details=details,
        )


class WhatsAppError(BaseAppError):
    def __init__(self, message: str = "WhatsApp message delivery failed", details: dict | None = None) -> None:
        super().__init__(
            codes.WHATSAPP_SEND_FAILED,
            message,
            category=ErrorCategory.CLIENT,
            status_code=502,
            details=details,
        )


class ExternalClientUnavailableError(BaseAppError):
    def __init__(self, client: str) -> None:
        super().__init__(
            codes.INTERNAL_ERROR,
            f"External client '{client}' is not configured",
            category=ErrorCategory.CLIENT,
            status_code=503,
        )

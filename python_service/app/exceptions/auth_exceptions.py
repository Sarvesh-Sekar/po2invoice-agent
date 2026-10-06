"""Authentication + authorization exceptions shared by all security layers."""

from __future__ import annotations

from app.err_codes import codes
from app.exceptions.base import BaseAppError, ErrorCategory


class UnauthorizedError(BaseAppError):
    """Raised when a request lacks valid credentials (HTTP 401)."""

    def __init__(self, message: str = "Missing or invalid credentials", details: dict | None = None) -> None:
        super().__init__(
            codes.UNAUTHORIZED,
            message,
            category=ErrorCategory.AUTH,
            status_code=401,
            details=details,
        )


class ForbiddenError(BaseAppError):
    """Raised when the caller is authenticated but not allowed to act (HTTP 403)."""

    def __init__(self, message: str = "Forbidden", details: dict | None = None) -> None:
        super().__init__(
            codes.FORBIDDEN,
            message,
            category=ErrorCategory.AUTH,
            status_code=403,
            details=details,
        )

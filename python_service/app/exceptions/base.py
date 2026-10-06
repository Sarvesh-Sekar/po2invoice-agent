from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    VALIDATION = "VALIDATION"
    AGENT = "AGENT"
    CLIENT = "CLIENT"
    WORKFLOW = "WORKFLOW"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    STORAGE = "STORAGE"
    INTERNAL = "INTERNAL"
    AUTH = "AUTH"


class BaseAppError(Exception):
    """Base error carrying an error code and category for the API response."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        status_code: int = 500,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                **({"details": self.details} if self.details else {}),
            },
        }

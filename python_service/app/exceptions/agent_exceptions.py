from __future__ import annotations

from app.err_codes import codes
from app.exceptions.base import BaseAppError, ErrorCategory


class POFileInvalidError(BaseAppError):
    def __init__(self, message: str = "Invalid purchase order file", details: dict | None = None) -> None:
        super().__init__(
            codes.PO_FILE_INVALID,
            message,
            category=ErrorCategory.VALIDATION,
            status_code=400,
            details=details,
        )


class POFileTooLargeError(BaseAppError):
    def __init__(self, message: str = "Purchase order file is too large", details: dict | None = None) -> None:
        super().__init__(
            codes.PO_FILE_TOO_LARGE,
            message,
            category=ErrorCategory.VALIDATION,
            status_code=413,
            details=details,
        )


class POExtractionError(BaseAppError):
    def __init__(self, message: str = "Unable to extract purchase order data", details: dict | None = None) -> None:
        super().__init__(
            codes.PO_EXTRACTION_FAILED,
            message,
            category=ErrorCategory.AGENT,
            status_code=502,
            details=details,
        )


class DocumentProcessingError(BaseAppError):
    def __init__(self, message: str = "Document processing failed", details: dict | None = None) -> None:
        super().__init__(
            codes.DOCUMENT_PROCESSING_FAILED,
            message,
            category=ErrorCategory.AGENT,
            status_code=502,
            details=details,
        )


class CustomerIdentificationError(BaseAppError):
    def __init__(self, message: str = "Customer identification failed", details: dict | None = None) -> None:
        super().__init__(
            codes.CUSTOMER_IDENTIFICATION_FAILED,
            message,
            category=ErrorCategory.AGENT,
            status_code=404,
            details=details,
        )


class FieldDefinitionError(BaseAppError):
    def __init__(self, message: str = "Field definition error", details: dict | None = None) -> None:
        super().__init__(
            codes.FIELD_DEFINITION_ERROR,
            message,
            category=ErrorCategory.AGENT,
            status_code=502,
            details=details,
        )


class ExtractionCandidateGenerationError(BaseAppError):
    def __init__(self, message: str = "Candidate generation failed", details: dict | None = None) -> None:
        super().__init__(
            codes.EXTRACTION_CANDIDATE_GENERATION_FAILED,
            message,
            category=ErrorCategory.AGENT,
            status_code=502,
            details=details,
        )


class ExtractionValidationError(BaseAppError):
    def __init__(self, message: str = "Extraction validation failed", details: dict | None = None) -> None:
        super().__init__(
            codes.EXTRACTION_VALIDATION_FAILED,
            message,
            category=ErrorCategory.WORKFLOW,
            status_code=422,
            details=details,
        )


class RecoveryExhaustedError(BaseAppError):
    def __init__(self, message: str = "Extraction recovery attempts exhausted", details: dict | None = None) -> None:
        super().__init__(
            codes.RECOVERY_EXHAUSTED,
            message,
            category=ErrorCategory.WORKFLOW,
            status_code=422,
            details=details,
        )


class ExtractionPersistenceError(BaseAppError):
    def __init__(self, message: str = "Extraction persistence failed", details: dict | None = None) -> None:
        super().__init__(
            codes.EXTRACTION_PERSISTENCE_FAILED,
            message,
            category=ErrorCategory.STORAGE,
            status_code=502,
            details=details,
        )


class EpisodicMemoryError(BaseAppError):
    def __init__(self, message: str = "Episodic memory update failed", details: dict | None = None) -> None:
        super().__init__(
            codes.EPISODIC_MEMORY_ERROR,
            message,
            category=ErrorCategory.STORAGE,
            status_code=502,
            details=details,
        )


class POVerificationError(BaseAppError):
    def __init__(self, message: str = "Purchase order verification failed", details: dict | None = None) -> None:
        super().__init__(
            codes.PO_VERIFICATION_FAILED,
            message,
            category=ErrorCategory.AGENT,
            status_code=502,
            details=details,
        )


class CustomerNotFoundError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.CUSTOMER_NOT_FOUND,
            "Customer not found for the supplied purchase order",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
            details=details,
        )


class ProductNotFoundError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.PRODUCT_NOT_FOUND,
            "Product not found for a purchase order line item",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
            details=details,
        )


class PriceValidationError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.PRICE_VALIDATION_FAILED,
            "Line item price validation failed",
            category=ErrorCategory.AGENT,
            status_code=422,
            details=details,
        )


class QuantityValidationError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.QUANTITY_VALIDATION_FAILED,
            "Line item quantity validation failed",
            category=ErrorCategory.AGENT,
            status_code=422,
            details=details,
        )


class HITLNotPendingError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.HITL_NOT_PENDING,
            "Workflow is not waiting for a human decision",
            category=ErrorCategory.CONFLICT,
            status_code=409,
            details=details,
        )


class WorkflowNotFoundError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.WORKFLOW_NOT_FOUND,
            "Agent workflow not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
            details=details,
        )


class WorkflowAlreadyCompletedError(BaseAppError):
    def __init__(self, details: dict | None = None) -> None:
        super().__init__(
            codes.WORKFLOW_ALREADY_COMPLETED,
            "Agent workflow already completed",
            category=ErrorCategory.CONFLICT,
            status_code=409,
            details=details,
        )


class WorkflowExecutionError(BaseAppError):
    def __init__(self, message: str = "Agent workflow execution failed", details: dict | None = None) -> None:
        super().__init__(
            codes.WORKFLOW_EXECUTION_FAILED,
            message,
            category=ErrorCategory.WORKFLOW,
            status_code=502,
            details=details,
        )


class InvalidWorkflowStatusError(BaseAppError):
    def __init__(
        self, message: str = "Workflow status is not valid for this operation", details: dict | None = None
    ) -> None:
        super().__init__(
            codes.INVALID_WORKFLOW_STATUS,
            message,
            category=ErrorCategory.CONFLICT,
            status_code=409,
            details=details,
        )

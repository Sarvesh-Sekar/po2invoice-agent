package errorcodes

import (
	"errors"
	"fmt"
	"net/http"
)

// ErrorCode is a stable machine-readable identifier shared with the solution
// definition (§ error code list). Clients may switch on the code without
// parsing free-text messages.
type ErrorCode string

// Defined codes.
const (
	CodeInvalidRequest      ErrorCode = "INVALID_REQUEST"
	CodeUnauthorized        ErrorCode = "UNAUTHORIZED"
	CodeForbidden           ErrorCode = "FORBIDDEN"
	CodeUserNotFound        ErrorCode = "USER_NOT_FOUND"
	CodeInvalidCredentials  ErrorCode = "INVALID_CREDENTIALS"
	CodeUserInactive        ErrorCode = "USER_INACTIVE"
	CodeOAuthStateMismatch  ErrorCode = "OAUTH_STATE_MISMATCH"
	CodeOAuthExchangeFailed ErrorCode = "OAUTH_EXCHANGE_FAILED"

	CodeCustomerNotFound     ErrorCode = "CUSTOMER_NOT_FOUND"
	CodeCustomerExists       ErrorCode = "CUSTOMER_ALREADY_EXISTS"
	CodeProductNotFound      ErrorCode = "PRODUCT_NOT_FOUND"
	CodeProductExists        ErrorCode = "PRODUCT_ALREADY_EXISTS"
	CodePONotFound           ErrorCode = "PURCHASE_ORDER_NOT_FOUND"
	CodePOAlreadyExists      ErrorCode = "PURCHASE_ORDER_ALREADY_EXISTS"
	CodeInvalidPOStatus      ErrorCode = "INVALID_PURCHASE_ORDER_STATUS"
	CodeSaleNotFound         ErrorCode = "SALE_NOT_FOUND"
	CodeInvalidSaleStatus    ErrorCode = "INVALID_SALE_STATUS"
	CodeSaleAlreadyDelivered ErrorCode = "SALE_ALREADY_DELIVERED"
	CodeDuplicateSale        ErrorCode = "DUPLICATE_SALE"
	CodeInvoiceNotFound      ErrorCode = "INVOICE_NOT_FOUND"
	CodeInvoiceAlreadyExists ErrorCode = "INVOICE_ALREADY_EXISTS"

	CodeDatabaseError      ErrorCode = "DATABASE_ERROR"
	CodeInternalError      ErrorCode = "INTERNAL_SERVER_ERROR"
	CodePythonServiceError ErrorCode = "PYTHON_SERVICE_ERROR"
	CodeAgentEventDispatch ErrorCode = "AGENT_EVENT_DISPATCH"
)

// AppError is the typed application error used across services and handlers
// (§ handler error mapping). Message is safe to expose to clients.
type AppError struct {
	Code       ErrorCode
	Message    string
	HTTPStatus int
	Cause      error
}

func (e *AppError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("%s: %s: %v", e.Code, e.Message, e.Cause)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

func (e *AppError) Unwrap() error { return e.Cause }

func New(code ErrorCode, httpStatus int, msg string) error {
	return &AppError{Code: code, Message: msg, HTTPStatus: httpStatus}
}

func Wrap(code ErrorCode, httpStatus int, msg string, cause error) error {
	return &AppError{Code: code, Message: msg, HTTPStatus: httpStatus, Cause: cause}
}

func InvalidRequest(msg string) error {
	return &AppError{Code: CodeInvalidRequest, Message: msg, HTTPStatus: http.StatusBadRequest}
}

func Unauthorized(msg string) error {
	return &AppError{Code: CodeUnauthorized, Message: msg, HTTPStatus: http.StatusUnauthorized}
}

func Forbidden(msg string) error {
	return &AppError{Code: CodeForbidden, Message: msg, HTTPStatus: http.StatusForbidden}
}

func NotFound(code ErrorCode, msg string) error {
	return &AppError{Code: code, Message: msg, HTTPStatus: http.StatusNotFound}
}

func Conflict(code ErrorCode, msg string) error {
	return &AppError{Code: code, Message: msg, HTTPStatus: http.StatusConflict}
}

func Database(cause error) error {
	return Wrap(CodeDatabaseError, http.StatusInternalServerError, "database operation failed", cause)
}

func Internal(msg string, cause error) error {
	if cause == nil {
		return &AppError{Code: CodeInternalError, Message: msg, HTTPStatus: http.StatusInternalServerError}
	}
	return Wrap(CodeInternalError, http.StatusInternalServerError, msg, cause)
}

func PythonService(cause error) error {
	return Wrap(CodePythonServiceError, http.StatusBadGateway, "python service unavailable", cause)
}

// HTTPStatus returns the HTTP status code associated with err. Unknown errors
// map to 500 per §45 ("Unexpected errors → 500 Internal Server Error").
func HTTPStatus(err error) int {
	var appErr *AppError
	if errors.As(err, &appErr) && appErr.HTTPStatus != 0 {
		return appErr.HTTPStatus
	}
	return http.StatusInternalServerError
}

// ToResponseBody renders a stable {code, message} body for the client.
func ToResponseBody(err error) (code string, message string) {
	var appErr *AppError
	if errors.As(err, &appErr) {
		return string(appErr.Code), appErr.Message
	}
	if err == nil {
		return "", ""
	}
	return string(CodeInternalError), "internal server error"
}

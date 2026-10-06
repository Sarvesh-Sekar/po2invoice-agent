// Package middleware provides the HTTP cross-cutting concerns: request ID,
// structured logging, panic recovery, and Bearer-token authentication.
package middleware

import (
	"context"
	"crypto/rand"
	"encoding/hex"

	"github.com/gin-gonic/gin"
)

type ctxKey string

const requestIDKey ctxKey = "request_id"

// RequestIDKey is exported so handlers/services can carry it into context.
const RequestIDKey = requestIDKey

// GetRequestID returns the inbound request id if present.
func GetRequestID(c context.Context) string {
	if v, ok := c.Value(requestIDKey).(string); ok {
		return v
	}
	return ""
}

func newRequestID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return "unknown"
	}
	return hex.EncodeToString(b)
}

// RequestID ensures every request has a request_id, honouring an inbound
// X-Request-ID when present.
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader("X-Request-ID")
		if rid == "" {
			rid = newRequestID()
		}
		c.Set("request_id", rid)
		c.Header("X-Request-ID", rid)
		ctx := context.WithValue(c.Request.Context(), requestIDKey, rid)
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}

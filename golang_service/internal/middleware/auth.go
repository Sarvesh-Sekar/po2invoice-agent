package middleware

import (
	"strings"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/googleauth"
)

// Auth authenticates the caller's Bearer access token (§13). Only access
// tokens are accepted; refresh tokens are rejected here. On success the user
// identity is stored in the gin context (user_id / email / name / role / token
// type) for handlers to read via CurrentUser.
func Auth(tm *googleauth.TokenManager, log *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		header := c.GetHeader("Authorization")
		if header == "" || !strings.HasPrefix(header, "Bearer ") {
			abortAuth(c, errorcodes.CodeUnauthorized, "missing or malformed Authorization header")
			return
		}
		token := strings.TrimSpace(strings.TrimPrefix(header, "Bearer "))

		claims, err := tm.Parse(token)
		if err != nil {
			log.Debug("token rejected",
				zap.String("request_id", GetRequestID(c.Request.Context())),
				zap.Error(err),
			)
			abortAuth(c, errorcodes.CodeUnauthorized, "invalid or expired token")
			return
		}
		if claims.TokenType != googleauth.TokenTypeAccess {
			abortAuth(c, errorcodes.CodeUnauthorized, "refresh tokens cannot access this resource")
			return
		}

		c.Set("user_id", claims.UserID.String())
		c.Set("user_email", claims.Email)
		c.Set("user_name", claims.Name)
		c.Set("user_role", claims.Role)
		c.Set("token_type", string(claims.TokenType))
		c.Next()
	}
}

func abortAuth(c *gin.Context, code errorcodes.ErrorCode, msg string) {
	c.AbortWithStatusJSON(401, gin.H{
		"code":    string(code),
		"message": msg,
	})
}

// CurrentUserID returns the authenticated user's id, or "" when missing.
func CurrentUserID(c *gin.Context) string {
	if v, ok := c.Get("user_id"); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

// CurrentUserRole returns the authenticated user's role, or "".
func CurrentUserRole(c *gin.Context) string {
	if v, ok := c.Get("user_role"); ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

package handlers

import (
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"net/url"
	"strconv"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/po-in/golang-service/internal/config"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/middleware"
	"github.com/po-in/golang-service/internal/services"
)

const stateCookieName = "poin_oauth_state"

// AuthHandler exposes the Google-only auth surface (§10–§12):
//   - GET  /auth/google          redirects the browser to Google consent
//   - GET  /auth/google/callback exchanges the code and redirects with tokens
//   - POST /auth/refresh         mints a new access token from a refresh token
//   - POST /auth/logout          204 no-op (stateless)
//   - GET  /auth/me              resolves the authenticated user
type AuthHandler struct {
	svc          services.AuthService
	cfg          config.Config
	log          *zap.Logger
	authRequired gin.HandlerFunc
}

func NewAuthHandler(svc services.AuthService, cfg config.Config, log *zap.Logger, authRequired gin.HandlerFunc) *AuthHandler {
	return &AuthHandler{svc: svc, cfg: cfg, log: log, authRequired: authRequired}
}

type refreshRequest struct {
	RefreshToken string `json:"refresh_token" binding:"required"`
}

func (h *AuthHandler) Register(r *gin.RouterGroup) {
	r.GET("/google", h.Begin)
	r.GET("/google/callback", h.Callback)
	r.POST("/refresh", h.Refresh)
	r.POST("/logout", h.Logout)
	r.GET("/me", h.authRequired, h.Me)
}

// Begin issues a short-lived signed state param and 302s to Google.
func (h *AuthHandler) Begin(c *gin.Context) {
	state, err := newState()
	if err != nil {
		writeError(c, errorcodes.Internal("generate oauth state", err))
		return
	}
	c.SetCookie(stateCookieName, state, 600, "/api/v1/auth/google/callback", "", false, true)
	authorizeURL := h.svc.GetAuthorizeURL(state)
	c.Redirect(http.StatusFound, authorizeURL)
}

// Callback exchanges the Google code for tokens and 302s back to the frontend.
func (h *AuthHandler) Callback(c *gin.Context) {
	code := c.Query("code")
	state := c.Query("state")
	if code == "" || state == "" {
		h.callbackError(c, errorcodes.CodeOAuthExchangeFailed, "missing code or state")
		return
	}
	cookieState, err := c.Cookie(stateCookieName)
	if err != nil || cookieState == "" {
		h.callbackError(c, errorcodes.CodeOAuthStateMismatch, "oauth state not found")
		return
	}
	if cookieState != state {
		h.callbackError(c, errorcodes.CodeOAuthStateMismatch, "oauth state mismatch")
		return
	}

	tokens, _, err := h.svc.HandleGoogleCallback(c.Request.Context(), code)
	if err != nil {
		code, msg := errorcodes.ToResponseBody(err)
		h.callbackError(c, errorcodes.ErrorCode(code), msg)
		return
	}

	q := url.Values{}
	q.Set("access_token", tokens.AccessToken)
	q.Set("refresh_token", tokens.RefreshToken)
	q.Set("token_type", tokens.TokenType)
	q.Set("expires_in", strconv.FormatInt(tokens.ExpiresIn, 10))
	c.Redirect(http.StatusFound, h.cfg.FrontendRedirectURL+"?"+q.Encode())
}

func (h *AuthHandler) callbackError(c *gin.Context, code errorcodes.ErrorCode, msg string) {
	c.SetCookie(stateCookieName, "", -1, "/api/v1/auth/google/callback", "", false, true)
	q := url.Values{}
	q.Set("error", msg)
	c.Redirect(http.StatusFound, h.cfg.FrontendRedirectURL+"?error="+q.Encode())
}

func (h *AuthHandler) Refresh(c *gin.Context) {
	var req refreshRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("refresh_token is required"))
		return
	}
	tokens, err := h.svc.RefreshToken(c.Request.Context(), req.RefreshToken)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, tokens)
}

func (h *AuthHandler) Logout(c *gin.Context) {
	c.Status(http.StatusNoContent)
}

func (h *AuthHandler) Me(c *gin.Context) {
	me, err := h.svc.Me(c.Request.Context(), middleware.CurrentUserID(c))
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, me)
}

func newState() (string, error) {
	b := make([]byte, 24)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

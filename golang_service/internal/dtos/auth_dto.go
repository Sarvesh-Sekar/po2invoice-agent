package dtos

import "time"

// Auth DTOs (§ auth API). Only email-based account lookup is supported; the
// app provisions users and Google OAuth is the sole login mechanism.

// AuthRedirectResponse is returned by GET /api/v1/auth/google.
type AuthRedirectResponse struct {
	AuthorizeURL string `json:"authorize_url"`
	State        string `json:"state"`
}

// SessionTokens is returned by the OAuth callback and the /auth/me refresh
// flow. Access tokens are short-lived JWTs; refresh tokens are opaque
// high-entropy strings stored server-side.
type SessionTokens struct {
	AccessToken  string    `json:"access_token"`
	TokenType    string    `json:"token_type"`
	ExpiresIn    int64     `json:"expires_in"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
}

// MeResponse is returned by GET /api/v1/auth/me.
type MeResponse struct {
	UserID   string `json:"user_id"`
	Name     string `json:"name"`
	Email    string `json:"email"`
	Role     string `json:"role"`
	IsActive bool   `json:"is_active"`
}

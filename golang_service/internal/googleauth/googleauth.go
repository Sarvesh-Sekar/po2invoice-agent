// Package googleauth implements Google OAuth 2.0 sign-in and JWT minting.
// Login is Google-only: the app provisions users and Google authorizes them
// (§10–§12). All tokens are HS256 JWTs whose claims are verified by both the
// Go service and the Python agent service.
package googleauth

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/po-in/golang-service/internal/config"
)

// UserInfo is the normalized Google profile after a successful exchange.
type UserInfo struct {
	ID    string
	Email string
	Name  string
}

// Authenticator is the OAuth surface used by the auth handler/service.
type Authenticator interface {
	// AuthorizeURL builds the Google consent URL for a caller-chosen state.
	AuthorizeURL(state string) string
	// ExchangeCode trades an authorization code for the user profile.
	ExchangeCode(ctx context.Context, code string) (*UserInfo, error)
}

type googleAuthenticator struct {
	clientID     string
	clientSecret string
	redirectURL  string
	scopes       []string
	authURL      string
	tokenURL     string
	userInfoURL  string
	httpClient   *http.Client
}

// NewGoogleAuthenticator wires the OAuth flow (§11).
func NewGoogleAuthenticator(cfg config.GoogleOAuthConfig, authURL, tokenURL, userInfoURL string) Authenticator {
	return &googleAuthenticator{
		clientID:     cfg.ClientID,
		clientSecret: cfg.ClientSecret,
		redirectURL:  cfg.RedirectURL,
		scopes:       cfg.Scopes,
		authURL:      authURL,
		tokenURL:     tokenURL,
		userInfoURL:  userInfoURL,
		httpClient:   &http.Client{Timeout: 10 * time.Second},
	}
}

func (g *googleAuthenticator) AuthorizeURL(state string) string {
	q := url.Values{}
	q.Set("client_id", g.clientID)
	q.Set("redirect_uri", g.redirectURL)
	q.Set("response_type", "code")
	q.Set("scope", strings.Join(g.scopes, " "))
	q.Set("access_type", "online")
	if state != "" {
		q.Set("state", state)
	}
	return g.authURL + "?" + q.Encode()
}

type googleTokenResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
	Error       string `json:"error"`
	ErrorDesc   string `json:"error_description"`
}

type googleUserInfo struct {
	Sub           string `json:"sub"`
	Email         string `json:"email"`
	EmailVerified bool   `json:"email_verified"`
	Name          string `json:"name"`
}

func (g *googleAuthenticator) ExchangeCode(ctx context.Context, code string) (*UserInfo, error) {
	form := url.Values{}
	form.Set("code", code)
	form.Set("client_id", g.clientID)
	form.Set("client_secret", g.clientSecret)
	form.Set("redirect_uri", g.redirectURL)
	form.Set("grant_type", "authorization_code")

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, g.tokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := g.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	var tok googleTokenResponse
	if err := json.Unmarshal(body, &tok); err != nil {
		return nil, fmt.Errorf("parse google token response: %w", err)
	}
	if tok.Error != "" || tok.AccessToken == "" {
		return nil, fmt.Errorf("google token error: %s %s", tok.Error, tok.ErrorDesc)
	}

	info, err := g.fetchUserInfo(ctx, tok.AccessToken)
	if err != nil {
		return nil, err
	}
	if !info.EmailVerified {
		return nil, fmt.Errorf("google email not verified")
	}
	return &UserInfo{ID: info.Sub, Email: info.Email, Name: info.Name}, nil
}

func (g *googleAuthenticator) fetchUserInfo(ctx context.Context, accessToken string) (*googleUserInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, g.userInfoURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	resp, err := g.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("google userinfo status %d", resp.StatusCode)
	}
	var info googleUserInfo
	if err := json.Unmarshal(body, &info); err != nil {
		return nil, fmt.Errorf("parse google userinfo: %w", err)
	}
	if info.Sub == "" || info.Email == "" {
		return nil, fmt.Errorf("google userinfo missing sub/email")
	}
	return &info, nil
}

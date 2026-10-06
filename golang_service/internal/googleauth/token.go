package googleauth

import (
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

// TokenType discriminates access (short-lived, middleware-authorized) vs
// refresh (long-lived, only accepted by /auth/refresh).
type TokenType string

const (
	TokenTypeAccess  TokenType = "access"
	TokenTypeRefresh TokenType = "refresh"
)

// Claims is the semantic identity carried by a token.
type Claims struct {
	UserID    uuid.UUID
	Email     string
	Name      string
	Role      string
	TokenType TokenType
}

// tokenClaims is the wire format. `sub` is the user id (uuid string) so the
// Python JwtTokenVerifier (which requires a non-empty sub + exp/iat) is
// satisfied.
type tokenClaims struct {
	Issuer    string `json:"iss"`
	Subject   string `json:"sub"`
	Email     string `json:"email"`
	Name      string `json:"name"`
	Role      string `json:"role"`
	TokenType string `json:"token_type"`
	IssuedAt  int64  `json:"iat"`
	ExpiresAt int64  `json:"exp"`
}

func (c tokenClaims) GetExpirationTime() (*jwt.NumericDate, error) {
	if c.ExpiresAt == 0 {
		return nil, nil
	}
	return jwt.NewNumericDate(time.Unix(c.ExpiresAt, 0)), nil
}

func (c tokenClaims) GetIssuedAt() (*jwt.NumericDate, error) {
	if c.IssuedAt == 0 {
		return nil, nil
	}
	return jwt.NewNumericDate(time.Unix(c.IssuedAt, 0)), nil
}

func (c tokenClaims) GetNotBefore() (*jwt.NumericDate, error) { return nil, nil }
func (c tokenClaims) GetIssuer() (string, error)              { return c.Issuer, nil }
func (c tokenClaims) GetSubject() (string, error)             { return c.Subject, nil }
func (c tokenClaims) GetAudience() (jwt.ClaimStrings, error)  { return nil, nil }

var _ jwt.Claims = (*tokenClaims)(nil)

// TokenManager mints and verifies HS256 access and refresh tokens.
type TokenManager struct {
	secret []byte
	issuer string
}

// NewTokenManager validates the shared secret and locks in the issuer.
// The same secret must be configured on the Python side for cross-service
// token verification.
func NewTokenManager(secret string, issuer string) (*TokenManager, error) {
	if issuer == "" {
		issuer = "po-in"
	}
	if len(secret) < 32 {
		return nil, errors.New("JWT secret must be at least 32 bytes")
	}
	return &TokenManager{secret: []byte(secret), issuer: issuer}, nil
}

func (tm *TokenManager) signingMethod() jwt.SigningMethod { return jwt.SigningMethodHS256 }

// IssueAccessToken creates a short-lived access token for the identity.
func (tm *TokenManager) IssueAccessToken(identity Claims, ttl time.Duration) (string, time.Time, error) {
	return tm.issue(identity, TokenTypeAccess, ttl)
}

// IssueRefreshToken creates a long-lived refresh token for the identity.
func (tm *TokenManager) IssueRefreshToken(identity Claims, ttl time.Duration) (string, time.Time, error) {
	return tm.issue(identity, TokenTypeRefresh, ttl)
}

func (tm *TokenManager) issue(identity Claims, typ TokenType, ttl time.Duration) (string, time.Time, error) {
	if identity.UserID == uuid.Nil {
		return "", time.Time{}, errors.New("token requires a user id")
	}
	now := time.Now()
	expiresAt := now.Add(ttl)
	claims := tokenClaims{
		Issuer:    tm.issuer,
		Subject:   identity.UserID.String(),
		Email:     identity.Email,
		Name:      identity.Name,
		Role:      identity.Role,
		TokenType: string(typ),
		IssuedAt:  now.Unix(),
		ExpiresAt: expiresAt.Unix(),
	}
	token := jwt.NewWithClaims(tm.signingMethod(), claims)
	signed, err := token.SignedString(tm.secret)
	if err != nil {
		return "", time.Time{}, err
	}
	return signed, expiresAt, nil
}

// Parse verifies signature, issuer, and expiry, returning the identity.
func (tm *TokenManager) Parse(raw string) (*Claims, error) {
	parsed, err := jwt.ParseWithClaims(raw, &tokenClaims{}, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method %v", t.Header["alg"])
		}
		return tm.secret, nil
	}, jwt.WithIssuer(tm.issuer), jwt.WithIssuedAt(), jwt.WithExpirationRequired())
	if err != nil {
		return nil, err
	}
	claims, ok := parsed.Claims.(*tokenClaims)
	if !ok || !parsed.Valid {
		return nil, errors.New("invalid token claims")
	}
	uid, err := uuid.Parse(claims.Subject)
	if err != nil {
		return nil, errors.New("invalid token subject")
	}
	return &Claims{
		UserID:    uid,
		Email:     claims.Email,
		Name:      claims.Name,
		Role:      claims.Role,
		TokenType: TokenType(claims.TokenType),
	}, nil
}

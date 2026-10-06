package googleauth

import (
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

func newTestManager(t *testing.T) *TokenManager {
	t.Helper()
	tm, err := NewTokenManager("0123456789abcdef0123456789abcdef", "po-in")
	if err != nil {
		t.Fatalf("NewTokenManager: %v", err)
	}
	return tm
}

func TestIssueAndParseAccessToken(t *testing.T) {
	tm := newTestManager(t)
	uid := uuid.New()

	token, _, err := tm.IssueAccessToken(Claims{UserID: uid, Email: "a@b.com", Name: "A", Role: "USER"}, 15*time.Minute)
	if err != nil {
		t.Fatalf("IssueAccessToken: %v", err)
	}

	claims, err := tm.Parse(token)
	if err != nil {
		t.Fatalf("Parse: %v", err)
	}
	if claims.UserID != uid || claims.Email != "a@b.com" || claims.TokenType != TokenTypeAccess {
		t.Fatalf("unexpected claims: %+v", claims)
	}
}

func TestIssuedClaimsArePythonCompatible(t *testing.T) {
	tm := newTestManager(t)
	token, _, err := tm.IssueAccessToken(Claims{UserID: uuid.New(), Email: "x@y.z", Name: "X", Role: "USER"}, 15*time.Minute)
	if err != nil {
		t.Fatalf("issue: %v", err)
	}
	parsed, err := jwt.Parse(token, func(t *jwt.Token) (any, error) { return tm.secret, nil })
	if err != nil {
		t.Fatalf("raw parse: %v", err)
	}
	claims, ok := parsed.Claims.(jwt.MapClaims)
	if !ok {
		t.Fatal("expected map claims")
	}
	// Python's verifier requires non-empty sub and present exp/iat.
	if sub, _ := claims["sub"].(string); sub == "" {
		t.Fatal("missing sub claim")
	}
	if _, ok := claims["exp"]; !ok {
		t.Fatal("missing exp claim")
	}
	if _, ok := claims["iat"]; !ok {
		t.Fatal("missing iat claim")
	}
	if claims["iss"] != "po-in" {
		t.Fatalf("unexpected issuer: %v", claims["iss"])
	}
}

func TestParseRejectsWrongSecret(t *testing.T) {
	tm := newTestManager(t)
	other, _ := NewTokenManager("fedcba9876543210fedcba9876543210", "po-in")

	token, _, _ := tm.IssueAccessToken(Claims{UserID: uuid.New(), Name: "A"}, time.Minute)
	if _, err := other.Parse(token); err == nil {
		t.Fatal("expected error for wrong secret")
	}
}

func TestParseRejectsExpiredToken(t *testing.T) {
	tm := newTestManager(t)
	token, _, err := tm.IssueAccessToken(Claims{UserID: uuid.New()}, -time.Minute)
	if err != nil {
		t.Fatalf("issue: %v", err)
	}
	if _, err := tm.Parse(token); err == nil {
		t.Fatal("expected error for expired token")
	}
}

func TestIssueRejectsNilUser(t *testing.T) {
	tm := newTestManager(t)
	if _, _, err := tm.IssueAccessToken(Claims{}, time.Minute); err == nil {
		t.Fatal("expected error for nil user id")
	}
}

func TestRefreshTokenMintsValidAccessToken(t *testing.T) {
	tm := newTestManager(t)
	uid := uuid.New()
	rt, _, err := tm.IssueRefreshToken(Claims{UserID: uid, Email: "r@t.com", Role: "ADMIN"}, 720*time.Hour)
	if err != nil {
		t.Fatalf("issue refresh: %v", err)
	}
	claims, err := tm.Parse(rt)
	if err != nil {
		t.Fatalf("parse refresh: %v", err)
	}
	if claims.TokenType != TokenTypeRefresh {
		t.Fatalf("expected refresh token type, got %s", claims.TokenType)
	}

	at, _, err := tm.IssueAccessToken(Claims{UserID: claims.UserID, Email: claims.Email, Role: claims.Role}, 15*time.Minute)
	if err != nil {
		t.Fatalf("issue access from refresh identity: %v", err)
	}
	parsed, err := tm.Parse(at)
	if err != nil || parsed.TokenType != TokenTypeAccess {
		t.Fatalf("minted access token invalid: %v", err)
	}
}

func TestNewTokenManagerRequiresLongSecret(t *testing.T) {
	if _, err := NewTokenManager("short", "po-in"); err == nil {
		t.Fatal("expected error for short secret")
	}
}

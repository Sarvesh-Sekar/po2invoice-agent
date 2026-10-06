package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"

	"github.com/po-in/golang-service/internal/googleauth"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func newTestTokenManager(t *testing.T) *googleauth.TokenManager {
	t.Helper()
	tm, err := googleauth.NewTokenManager("0123456789abcdef0123456789abcdef", "po-in")
	if err != nil {
		t.Fatalf("token manager: %v", err)
	}
	return tm
}

func authEngine(t *testing.T) (*gin.Engine, *googleauth.TokenManager) {
	t.Helper()
	tm := newTestTokenManager(t)
	r := gin.New()
	r.GET("/protected", Auth(tm, zap.NewNop()), func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"user_id": CurrentUserID(c)})
	})
	return r, tm
}

func tokenFor(t *testing.T, tm *googleauth.TokenManager, typ googleauth.TokenType) string {
	t.Helper()
	identity := googleauth.Claims{UserID: uuid.New(), Email: "a@b.com", Role: "USER"}
	var raw string
	var err error
	if typ == googleauth.TokenTypeRefresh {
		raw, _, err = tm.IssueRefreshToken(identity, 720*time.Hour)
	} else {
		raw, _, err = tm.IssueAccessToken(identity, 15*time.Minute)
	}
	if err != nil {
		t.Fatalf("issue token: %v", err)
	}
	return raw
}

func doGET(r *gin.Engine, headers map[string]string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/protected", nil)
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)
	return rec
}

func TestAuthAcceptsValidAccessToken(t *testing.T) {
	r, tm := authEngine(t)
	rec := doGET(r, map[string]string{"Authorization": "Bearer " + tokenFor(t, tm, googleauth.TokenTypeAccess)})
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}
}

func TestAuthRejectsMissingHeader(t *testing.T) {
	r, _ := authEngine(t)
	rec := doGET(r, nil)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
}

func TestAuthRejectsMalformedHeader(t *testing.T) {
	r, _ := authEngine(t)
	rec := doGET(r, map[string]string{"Authorization": "Basic abc"})
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
}

func TestAuthRejectsRefreshToken(t *testing.T) {
	r, tm := authEngine(t)
	rec := doGET(r, map[string]string{"Authorization": "Bearer " + tokenFor(t, tm, googleauth.TokenTypeRefresh)})
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for refresh token, got %d", rec.Code)
	}
}

func TestAuthRejectsGarbageToken(t *testing.T) {
	r, _ := authEngine(t)
	rec := doGET(r, map[string]string{"Authorization": "Bearer not.a.jwt"})
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
}

package services

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/googleauth"
	"github.com/po-in/golang-service/internal/models"
)

type fakeUserRepo struct {
	user *models.User
	err  error
}

func (f *fakeUserRepo) ByID(context.Context, uuid.UUID) (*models.User, error) {
	if f.err != nil {
		return nil, f.err
	}
	return f.user, nil
}

func (f *fakeUserRepo) ByEmail(context.Context, string) (*models.User, error) {
	return f.ByID(context.Background(), uuid.Nil)
}

func newAuthServiceForTest(t *testing.T, user *models.User, userErr error) AuthService {
	t.Helper()
	tm, err := googleauth.NewTokenManager("0123456789abcdef0123456789abcdef", "po-in")
	if err != nil {
		t.Fatalf("token manager: %v", err)
	}
	fake := &fakeAuthenticator{}
	return NewAuthService(tm, fake, &fakeUserRepo{user: user, err: userErr}, 15*time.Minute, 720*time.Hour)
}

func newTestUser() *models.User {
	return &models.User{
		ID:       uuid.New(),
		Name:     "Test User",
		Email:    "test@example.com",
		Role:     "USER",
		IsActive: true,
	}
}

func TestHandleGoogleCallbackHappyPath(t *testing.T) {
	svc := newAuthServiceForTest(t, newTestUser(), nil)
	tokens, me, err := svc.HandleGoogleCallback(context.Background(), "good-code")
	if err != nil {
		t.Fatalf("callback: %v", err)
	}
	if tokens.AccessToken == "" || tokens.RefreshToken == "" {
		t.Fatal("expected access and refresh tokens")
	}
	if !me.IsActive || me.Email != "test@example.com" {
		t.Fatalf("unexpected me response: %+v", me)
	}
}

func TestHandleGoogleCallbackInactiveUser(t *testing.T) {
	u := newTestUser()
	u.IsActive = false
	svc := newAuthServiceForTest(t, u, nil)
	if _, _, err := svc.HandleGoogleCallback(context.Background(), "good-code"); !isAppError(err, errorcodes.CodeForbidden) {
		t.Fatalf("expected forbidden, got %v", err)
	}
}

func TestHandleGoogleCallbackUnknownUser(t *testing.T) {
	svc := newAuthServiceForTest(t, nil, errorcodes.NotFound(errorcodes.CodeUserNotFound, "user not found"))
	if _, _, err := svc.HandleGoogleCallback(context.Background(), "good-code"); !isAppError(err, errorcodes.CodeUserNotFound) {
		t.Fatalf("expected user not found, got %v", err)
	}
}

func TestRefreshTokenRejectsAccessToken(t *testing.T) {
	svc := newAuthServiceForTest(t, newTestUser(), nil)
	tokens, _, err := svc.HandleGoogleCallback(context.Background(), "good-code")
	if err != nil {
		t.Fatalf("callback: %v", err)
	}
	if _, err := svc.RefreshToken(context.Background(), tokens.AccessToken); !isAppError(err, errorcodes.CodeUnauthorized) {
		t.Fatalf("expected unauthorized, got %v", err)
	}
}

func TestRefreshTokenHappyPath(t *testing.T) {
	svc := newAuthServiceForTest(t, newTestUser(), nil)
	tokens, _, err := svc.HandleGoogleCallback(context.Background(), "good-code")
	if err != nil {
		t.Fatalf("callback: %v", err)
	}
	refreshed, err := svc.RefreshToken(context.Background(), tokens.RefreshToken)
	if err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if refreshed.AccessToken == "" {
		t.Fatal("expected a fresh access token")
	}
}

func isAppError(err error, want errorcodes.ErrorCode) bool {
	var appErr *errorcodes.AppError
	return errors.As(err, &appErr) && appErr.Code == want
}

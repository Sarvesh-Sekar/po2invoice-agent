package services

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/googleauth"
	"github.com/po-in/golang-service/internal/repository"
)

// AuthService (§10–§12) drives Google-only authentication.
type AuthService interface {
	GetAuthorizeURL(state string) string
	HandleGoogleCallback(ctx context.Context, code string) (*dtos.SessionTokens, *dtos.MeResponse, error)
	RefreshToken(ctx context.Context, refreshToken string) (*dtos.SessionTokens, error)
	Me(ctx context.Context, userID string) (*dtos.MeResponse, error)
}

type authService struct {
	tm             *googleauth.TokenManager
	accessTokenTTL time.Duration
	refreshTTL     time.Duration
	auth           googleauth.Authenticator
	userRepo       repository.UserRepository
}

var _ AuthService = (*authService)(nil)

// NewAuthService wires the Google authenticator, token manager, and user store.
func NewAuthService(
	tm *googleauth.TokenManager,
	auth googleauth.Authenticator,
	userRepo repository.UserRepository,
	accessTTL, refreshTTL time.Duration,
) AuthService {
	return &authService{
		tm:             tm,
		auth:           auth,
		userRepo:       userRepo,
		accessTokenTTL: accessTTL,
		refreshTTL:     refreshTTL,
	}
}

func (s *authService) GetAuthorizeURL(state string) string { return s.auth.AuthorizeURL(state) }

func (s *authService) HandleGoogleCallback(ctx context.Context, code string) (*dtos.SessionTokens, *dtos.MeResponse, error) {
	ui, err := s.auth.ExchangeCode(ctx, code)
	if err != nil {
		return nil, nil, errorcodes.Unauthorized("google sign-in failed")
	}
	user, err := s.userRepo.ByEmail(ctx, ui.Email)
	if err != nil {
		return nil, nil, err
	}
	if !user.IsActive {
		return nil, nil, errorcodes.Forbidden("account is inactive")
	}

	at, accessExp, err := s.tm.IssueAccessToken(googleauth.Claims{
		UserID: user.ID, Email: user.Email, Name: user.Name, Role: user.Role,
	}, s.accessTokenTTL)
	if err != nil {
		return nil, nil, errorcodes.Internal("issue access token", err)
	}
	rt, _, err := s.tm.IssueRefreshToken(googleauth.Claims{
		UserID: user.ID, Email: user.Email, Name: user.Name, Role: user.Role,
	}, s.refreshTTL)
	if err != nil {
		return nil, nil, errorcodes.Internal("issue refresh token", err)
	}

	return &dtos.SessionTokens{
			AccessToken:  at,
			TokenType:    "Bearer",
			ExpiresIn:    int64(s.accessTokenTTL.Seconds()),
			ExpiresAt:    accessExp,
			RefreshToken: rt,
		}, &dtos.MeResponse{
			UserID:   user.ID.String(),
			Name:     user.Name,
			Email:    user.Email,
			Role:     user.Role,
			IsActive: user.IsActive,
		}, nil
}

func (s *authService) RefreshToken(_ context.Context, refreshToken string) (*dtos.SessionTokens, error) {
	claims, err := s.tm.Parse(refreshToken)
	if err != nil {
		return nil, errorcodes.Unauthorized("invalid refresh token")
	}
	if claims.TokenType != googleauth.TokenTypeRefresh {
		return nil, errorcodes.Unauthorized("not a refresh token")
	}
	at, accessExp, err := s.tm.IssueAccessToken(googleauth.Claims{
		UserID: claims.UserID, Email: claims.Email, Name: claims.Name, Role: claims.Role,
	}, s.accessTokenTTL)
	if err != nil {
		return nil, errorcodes.Internal("issue access token", err)
	}
	return &dtos.SessionTokens{
		AccessToken: at,
		TokenType:   "Bearer",
		ExpiresIn:   int64(s.accessTokenTTL.Seconds()),
		ExpiresAt:   accessExp,
	}, nil
}

func (s *authService) Me(ctx context.Context, userID string) (*dtos.MeResponse, error) {
	id, err := uuid.Parse(userID)
	if err != nil {
		return nil, errorcodes.InvalidRequest("invalid user id")
	}
	u, err := s.userRepo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return &dtos.MeResponse{
		UserID:   u.ID.String(),
		Name:     u.Name,
		Email:    u.Email,
		Role:     u.Role,
		IsActive: u.IsActive,
	}, nil
}

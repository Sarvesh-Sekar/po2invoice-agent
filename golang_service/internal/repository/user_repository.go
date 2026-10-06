package repository

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
)

// UserRepository is the (Go-owned) user store used by the auth flow.
type UserRepository interface {
	ByID(ctx context.Context, id uuid.UUID) (*models.User, error)
	ByEmail(ctx context.Context, email string) (*models.User, error)
}

type userRepository struct{ db *gorm.DB }

func NewUserRepository(db *gorm.DB) UserRepository { return &userRepository{db: db} }

func (r *userRepository) ByID(ctx context.Context, id uuid.UUID) (*models.User, error) {
	var u models.User
	err := r.db.WithContext(ctx).First(&u, "id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeUserNotFound, "user not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load user", err)
	}
	return &u, nil
}

func (r *userRepository) ByEmail(ctx context.Context, email string) (*models.User, error) {
	var u models.User
	err := r.db.WithContext(ctx).First(&u, "lower(email) = lower(?)", email).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeUserNotFound, "user not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load user by email", err)
	}
	return &u, nil
}

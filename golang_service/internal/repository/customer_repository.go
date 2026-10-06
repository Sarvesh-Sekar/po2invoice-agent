package repository

import (
	"context"
	"errors"
	"strings"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
)

// CustomerFilter narrows a customer list query.
type CustomerFilter struct {
	Search string
	Limit  int
	Offset int
}

// CustomerRepository provides CRUD over customers (ER2 CUSTOMERS).
type CustomerRepository interface {
	Create(ctx context.Context, c *models.Customer) error
	ByID(ctx context.Context, id uuid.UUID) (*models.Customer, error)
	ByCustomerCode(ctx context.Context, code string) (*models.Customer, error)
	List(ctx context.Context, filter CustomerFilter) ([]models.Customer, int64, error)
	Update(ctx context.Context, c *models.Customer) error
	Delete(ctx context.Context, id uuid.UUID) error
}

type customerRepository struct{ db *gorm.DB }

func NewCustomerRepository(db *gorm.DB) CustomerRepository { return &customerRepository{db: db} }

func (r *customerRepository) Create(ctx context.Context, c *models.Customer) error {
	if err := r.db.WithContext(ctx).Create(c).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "create customer", err)
	}
	return nil
}

func (r *customerRepository) ByID(ctx context.Context, id uuid.UUID) (*models.Customer, error) {
	var c models.Customer
	err := r.db.WithContext(ctx).First(&c, "customer_id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load customer", err)
	}
	return &c, nil
}

func (r *customerRepository) ByCustomerCode(ctx context.Context, code string) (*models.Customer, error) {
	var c models.Customer
	err := r.db.WithContext(ctx).First(&c, "lower(customer_code) = lower(?)", code).Error
	if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load customer by code", err)
	}
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &c, nil
}

func (r *customerRepository) List(ctx context.Context, filter CustomerFilter) ([]models.Customer, int64, error) {
	q := r.db.WithContext(ctx).Model(&models.Customer{})
	if strings.TrimSpace(filter.Search) != "" {
		like := "%" + strings.TrimSpace(filter.Search) + "%"
		q = q.Where("(name ILIKE ? OR customer_code ILIKE ?)", like, like)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "count customers", err)
	}

	var out []models.Customer
	if err := q.Order("created_at DESC").Limit(filter.Limit).Offset(filter.Offset).Find(&out).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "list customers", err)
	}
	return out, total, nil
}

func (r *customerRepository) Update(ctx context.Context, c *models.Customer) error {
	if err := r.db.WithContext(ctx).Save(c).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "update customer", err)
	}
	return nil
}

func (r *customerRepository) Delete(ctx context.Context, id uuid.UUID) error {
	res := r.db.WithContext(ctx).Model(&models.Customer{}).
		Where("customer_id = ? AND status = ?", id, models.CustomerStatusActive).
		Updates(map[string]any{"status": models.CustomerStatusInactive, "modified_at": gorm.Expr("now()")})
	if res.Error != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "deactivate customer", res.Error)
	}
	if res.RowsAffected == 0 {
		return errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
	}
	return nil
}
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

// ProductFilter narrows a product list query.
type ProductFilter struct {
	Search string
	Status string
	Limit  int
	Offset int
}

// ProductRepository provides CRUD over products (ER2 PRODUCTS).
type ProductRepository interface {
	Create(ctx context.Context, p *models.Product) error
	ByID(ctx context.Context, id uuid.UUID) (*models.Product, error)
	BySKU(ctx context.Context, sku string) (*models.Product, error)
	List(ctx context.Context, filter ProductFilter) ([]models.Product, int64, error)
	Update(ctx context.Context, p *models.Product) error
	ExistsForIDs(ctx context.Context, ids []uuid.UUID) (bool, error)
}

type productRepository struct{ db *gorm.DB }

func NewProductRepository(db *gorm.DB) ProductRepository { return &productRepository{db: db} }

func (r *productRepository) Create(ctx context.Context, p *models.Product) error {
	if err := r.db.WithContext(ctx).Create(p).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "create product", err)
	}
	return nil
}

func (r *productRepository) ByID(ctx context.Context, id uuid.UUID) (*models.Product, error) {
	var p models.Product
	err := r.db.WithContext(ctx).First(&p, "product_id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeProductNotFound, "product not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load product", err)
	}
	return &p, nil
}

func (r *productRepository) BySKU(ctx context.Context, sku string) (*models.Product, error) {
	var p models.Product
	err := r.db.WithContext(ctx).First(&p, "lower(sku) = lower(?)", sku).Error
	if err != nil && !errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load product by sku", err)
	}
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, nil
	}
	return &p, nil
}

func (r *productRepository) List(ctx context.Context, filter ProductFilter) ([]models.Product, int64, error) {
	q := r.db.WithContext(ctx).Model(&models.Product{})
	if strings.TrimSpace(filter.Search) != "" {
		like := "%" + strings.TrimSpace(filter.Search) + "%"
		q = q.Where("(name ILIKE ? OR sku ILIKE ?)", like, like)
	}
	if filter.Status != "" {
		q = q.Where("products.status = ?", filter.Status)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "count products", err)
	}

	var out []models.Product
	if err := q.Order("created_at DESC").Limit(filter.Limit).Offset(filter.Offset).Find(&out).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "list products", err)
	}
	return out, total, nil
}

func (r *productRepository) Update(ctx context.Context, p *models.Product) error {
	if err := r.db.WithContext(ctx).Save(p).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "update product", err)
	}
	return nil
}

func (r *productRepository) ExistsForIDs(ctx context.Context, ids []uuid.UUID) (bool, error) {
	if len(ids) == 0 {
		return false, nil
	}
	var count int64
	if err := r.db.WithContext(ctx).Model(&models.Product{}).
		Where("product_id IN ? AND status = ?", ids, models.ProductStatusActive).
		Count(&count).Error; err != nil {
		return false, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "check products exist", err)
	}
	return count == int64(len(ids)), nil
}
package repository

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
)

// SaleFilter narrows a sale list query.
type SaleFilter struct {
	Status     string
	CustomerID string
	POID       string
	Limit      int
	Offset     int
}

// SaleRepository provides sale CRUD + status updates (ER2 SALES, 1:1 with PO).
type SaleRepository interface {
	Create(ctx context.Context, s *models.Sale) error
	ByID(ctx context.Context, id uuid.UUID) (*models.Sale, error)
	ByPOID(ctx context.Context, poID uuid.UUID) (*models.Sale, error)
	List(ctx context.Context, filter SaleFilter) ([]models.Sale, int64, error)
	Update(ctx context.Context, s *models.Sale) error
}

type saleRepository struct{ db *gorm.DB }

func NewSaleRepository(db *gorm.DB) SaleRepository { return &saleRepository{db: db} }

func (r *saleRepository) Create(ctx context.Context, s *models.Sale) error {
	if err := r.db.WithContext(ctx).Create(s).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "create sale", err)
	}
	return nil
}

func (r *saleRepository) ByID(ctx context.Context, id uuid.UUID) (*models.Sale, error) {
	var s models.Sale
	err := r.db.WithContext(ctx).
		Preload("PurchaseOrder.Customer").
		Preload("PurchaseOrder.HeaderFields.FieldDefinition").
		First(&s, "sale_id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load sale", err)
	}
	return &s, nil
}

func (r *saleRepository) ByPOID(ctx context.Context, poID uuid.UUID) (*models.Sale, error) {
	var s models.Sale
	err := r.db.WithContext(ctx).First(&s, "po_id = ?", poID).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load sale by po", err)
	}
	return &s, nil
}

// salePreloads keeps display metadata (PO header fields + customer) present on
// every returned sale so the service can derive po_number / customer_name.
func salePreloads(q *gorm.DB) *gorm.DB {
	return q.
		Preload("PurchaseOrder.Customer").
		Preload("PurchaseOrder.HeaderFields.FieldDefinition")
}

func (r *saleRepository) List(ctx context.Context, filter SaleFilter) ([]models.Sale, int64, error) {
	q := r.db.WithContext(ctx).Model(&models.Sale{}).
		Joins("LEFT JOIN purchase_orders po ON po.po_id = sales.po_id")
	if filter.Status != "" {
		q = q.Where("sales.status = ?", filter.Status)
	}
	if filter.POID != "" {
		q = q.Where("sales.po_id = ?", filter.POID)
	}
	if filter.CustomerID != "" {
		q = q.Where("po.customer_id = ?", filter.CustomerID)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "count sales", err)
	}

	var out []models.Sale
	if err := salePreloads(q).
		Order("sales.created_at DESC").
		Limit(filter.Limit).Offset(filter.Offset).
		Find(&out).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "list sales", err)
	}
	return out, total, nil
}

func (r *saleRepository) Update(ctx context.Context, s *models.Sale) error {
	res := r.db.WithContext(ctx).Model(&models.Sale{}).
		Where("sale_id = ?", s.SaleID).
		Updates(map[string]any{"status": s.Status, "modified_at": gorm.Expr("now()")})
	if res.Error != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "update sale", res.Error)
	}
	if res.RowsAffected == 0 {
		return errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
	}
	return nil
}
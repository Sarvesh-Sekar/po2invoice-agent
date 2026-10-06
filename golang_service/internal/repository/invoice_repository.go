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

// InvoiceFilter narrows an invoice list query.
type InvoiceFilter struct {
	Status     string
	POID       string
	CustomerID string
	Search     string
	Limit      int
	Offset     int
}

// InvoiceRepository provides read/access APIs (ER2 INVOICES). Invoices are
// generated from a purchase order and written by the Python invoice agent.
type InvoiceRepository interface {
	ByID(ctx context.Context, id uuid.UUID) (*models.Invoice, error)
	List(ctx context.Context, filter InvoiceFilter) ([]models.Invoice, int64, error)
}

type invoiceRepository struct{ db *gorm.DB }

func NewInvoiceRepository(db *gorm.DB) InvoiceRepository { return &invoiceRepository{db: db} }

func (r *invoiceRepository) ByID(ctx context.Context, id uuid.UUID) (*models.Invoice, error) {
	var inv models.Invoice
	err := r.db.WithContext(ctx).
		Preload("PurchaseOrder").
		First(&inv, "invoice_id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodeInvoiceNotFound, "invoice not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load invoice", err)
	}
	return &inv, nil
}

func (r *invoiceRepository) List(ctx context.Context, filter InvoiceFilter) ([]models.Invoice, int64, error) {
	q := r.db.WithContext(ctx).Model(&models.Invoice{}).
		Joins("LEFT JOIN purchase_orders po ON po.po_id = invoices.po_id").
		Joins("LEFT JOIN customers c ON c.customer_id = po.customer_id")
	if filter.Status != "" {
		q = q.Where("invoices.status = ?", filter.Status)
	}
	if filter.POID != "" {
		q = q.Where("invoices.po_id = ?", filter.POID)
	}
	if filter.CustomerID != "" {
		q = q.Where("po.customer_id = ?", filter.CustomerID)
	}
	if strings.TrimSpace(filter.Search) != "" {
		like := "%" + strings.TrimSpace(filter.Search) + "%"
		q = q.Where(`(invoices.invoice_number ILIKE ? OR EXISTS (
			SELECT 1 FROM po_header_fields phf
			JOIN field_definitions fd ON fd.field_id = phf.field_id
			WHERE phf.po_id = invoices.po_id AND fd.field_name = 'po_number'
			AND phf.field_value ILIKE ?))`, like, like)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "count invoices", err)
	}

	var out []models.Invoice
	if err := q.Order("invoices.created_at DESC").
		Limit(filter.Limit).Offset(filter.Offset).
		Find(&out).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "list invoices", err)
	}
	return out, total, nil
}

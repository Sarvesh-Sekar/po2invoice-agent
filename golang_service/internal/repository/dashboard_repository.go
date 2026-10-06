package repository

import (
	"context"
	"strings"

	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
)

// poNumberExpr is a scalar subquery resolving the po_number header field.
// {po} must be replaced with the concrete purchase_orders alias.
const poNumberExpr = `(SELECT phf.field_value FROM po_header_fields phf
	JOIN field_definitions fd ON fd.field_id = phf.field_id
	WHERE phf.po_id = {po}.po_id AND fd.field_name = 'po_number'
	ORDER BY phf.created_at ASC LIMIT 1)`

// DashboardRepository aggregates KPI + recency data (§ dashboard API).
type DashboardRepository interface {
	Summary(ctx context.Context) (*dtos.DashboardSummary, error)
	RecentSales(ctx context.Context, limit int) ([]dtos.RecentSaleItem, error)
	RecentOrders(ctx context.Context, limit int) ([]dtos.RecentOrderItem, error)
	RecentInvoices(ctx context.Context, limit int) ([]dtos.RecentInvoiceItem, error)
}

type dashboardRepository struct{ db *gorm.DB }

func NewDashboardRepository(db *gorm.DB) DashboardRepository {
	return &dashboardRepository{db: db}
}

func (r *dashboardRepository) Summary(ctx context.Context) (*dtos.DashboardSummary, error) {
	out := &dtos.DashboardSummary{}
	var tc, tp, tpos, ts, pending int64

	err := r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&models.Customer{}).Where("status = ?", models.CustomerStatusActive).Count(&tc).Error; err != nil {
			return err
		}
		if err := tx.Model(&models.Product{}).Where("status = ?", models.ProductStatusActive).Count(&tp).Error; err != nil {
			return err
		}
		if err := tx.Model(&models.PurchaseOrder{}).Count(&tpos).Error; err != nil {
			return err
		}
		if err := tx.Model(&models.Sale{}).Count(&ts).Error; err != nil {
			return err
		}
		if err := tx.Model(&models.Invoice{}).Where("status <> ?", models.InvoiceStatusSent).Count(&pending).Error; err != nil {
			return err
		}
		// total_revenue = total_amount header field across POs that have an invoice.
		q := `SELECT COALESCE(SUM(CASE WHEN phf.field_value ~ '^-?[0-9]+(\.[0-9]+)?$' THEN phf.field_value::numeric ELSE 0 END), 0)
			FROM po_header_fields phf
			JOIN field_definitions fd ON fd.field_id = phf.field_id
			WHERE fd.field_name = 'total_amount'
			AND EXISTS (SELECT 1 FROM invoices i WHERE i.po_id = phf.po_id)`
		if err := tx.Raw(q).Scan(&out.TotalRevenue).Error; err != nil {
			return err
		}
		return nil
	})
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "dashboard summary", err)
	}
	out.TotalCustomers = int(tc)
	out.TotalProducts = int(tp)
	out.TotalPOs = int(tpos)
	out.TotalSales = int(ts)
	out.PendingInvoices = int(pending)
	return out, nil
}

func (r *dashboardRepository) RecentSales(ctx context.Context, limit int) ([]dtos.RecentSaleItem, error) {
	if limit <= 0 {
		limit = 10
	}
	poNumber := strings.ReplaceAll(poNumberExpr, "{po}", "po")
	var rows []dtos.RecentSaleItem
	err := r.db.WithContext(ctx).
		Model(&models.Sale{}).
		Select("sales.sale_id::text, COALESCE(" + poNumber + ", '') AS po_number, sales.status, sales.created_at").
		Joins("LEFT JOIN purchase_orders po ON po.po_id = sales.po_id").
		Order("sales.created_at DESC").
		Limit(limit).
		Scan(&rows).Error
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "recent sales", err)
	}
	return rows, nil
}

func (r *dashboardRepository) RecentOrders(ctx context.Context, limit int) ([]dtos.RecentOrderItem, error) {
	if limit <= 0 {
		limit = 10
	}
	poNumber := strings.ReplaceAll(poNumberExpr, "{po}", "purchase_orders")
	var rows []dtos.RecentOrderItem
	err := r.db.WithContext(ctx).
		Model(&models.PurchaseOrder{}).
		Select("purchase_orders.po_id::text, COALESCE(" + poNumber + ", '') AS po_number, COALESCE(customers.name, '') AS customer, purchase_orders.created_at").
		Joins("LEFT JOIN customers ON customers.customer_id = purchase_orders.customer_id").
		Order("purchase_orders.created_at DESC").
		Limit(limit).
		Scan(&rows).Error
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "recent orders", err)
	}
	return rows, nil
}

func (r *dashboardRepository) RecentInvoices(ctx context.Context, limit int) ([]dtos.RecentInvoiceItem, error) {
	if limit <= 0 {
		limit = 10
	}
	var rows []dtos.RecentInvoiceItem
	err := r.db.WithContext(ctx).
		Model(&models.Invoice{}).
		Select("invoices.invoice_id::text, invoices.invoice_number, invoices.status, invoices.created_at").
		Order("invoices.created_at DESC").
		Limit(limit).
		Scan(&rows).Error
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "recent invoices", err)
	}
	return rows, nil
}

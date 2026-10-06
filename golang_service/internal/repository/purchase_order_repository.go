package repository

import (
	"context"
	"errors"
	"strings"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
)

// PurchaseOrderFilter narrows a PO list query.
type PurchaseOrderFilter struct {
	CustomerID *uuid.UUID
	Search     string
	Limit      int
	Offset     int
}

// PurchaseOrderRepository handles purchase orders, their field values and
// line items in a transaction (ER2 PURCHASE_ORDERS / PO_HEADER_FIELDS /
// PO_LINE_ITEMS / PO_LINE_ITEM_FIELDS).
type PurchaseOrderRepository interface {
	Create(ctx context.Context, po *models.PurchaseOrder) error
	ByID(ctx context.Context, id uuid.UUID) (*models.PurchaseOrder, error)
	List(ctx context.Context, filter PurchaseOrderFilter) ([]dtos.PurchaseOrderListItem, int64, error)
	Update(ctx context.Context, po *models.PurchaseOrder) error
	ReplaceHeaderFields(ctx context.Context, poID uuid.UUID, fields []models.POHeaderField) error
	UpdateLineItems(ctx context.Context, items []models.POLineItem) error
	DeleteLineItems(ctx context.Context, poID uuid.UUID, keepIDs []uuid.UUID) error
	FieldByNames(ctx context.Context, names []string) (map[string]models.FieldDefinition, error)
}

type purchaseOrderRepository struct{ db *gorm.DB }

func NewPurchaseOrderRepository(db *gorm.DB) PurchaseOrderRepository {
	return &purchaseOrderRepository{db: db}
}

func (r *purchaseOrderRepository) Create(ctx context.Context, po *models.PurchaseOrder) error {
	err := r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		created := *po
		created.Customer = models.Customer{}
		created.HeaderFields = nil
		created.LineItems = nil
		if err := tx.Create(&created).Error; err != nil {
			return err
		}
		po.POID = created.POID

		for i := range po.HeaderFields {
			po.HeaderFields[i].POID = po.POID
			if err := tx.Create(&po.HeaderFields[i]).Error; err != nil {
				return err
			}
		}
		for i := range po.LineItems {
			item := po.LineItems[i]
			item.POID = po.POID
			item.Product = models.Product{}
			item.Fields = nil
			if err := tx.Create(&item).Error; err != nil {
				return err
			}
			po.LineItems[i].POLineItemID = item.POLineItemID
			for j := range po.LineItems[i].Fields {
				po.LineItems[i].Fields[j].POLineItemID = item.POLineItemID
				if err := tx.Create(&po.LineItems[i].Fields[j]).Error; err != nil {
					return err
				}
			}
		}
		return nil
	})
	if err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "create purchase order", err)
	}
	return nil
}

func (r *purchaseOrderRepository) ByID(ctx context.Context, id uuid.UUID) (*models.PurchaseOrder, error) {
	var po models.PurchaseOrder
	err := r.db.WithContext(ctx).
		Preload("Customer").
		Preload("HeaderFields.FieldDefinition").
		Preload("LineItems.Product").
		Preload("LineItems.Fields.FieldDefinition").
		First(&po, "po_id = ?", id).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil, errorcodes.NotFound(errorcodes.CodePONotFound, "purchase order not found")
	}
	if err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load purchase order", err)
	}
	return &po, nil
}

// listSelect exposes the lightweight PO list projection (ER-derived fields).
const listSelect = `purchase_orders.po_id,
	purchase_orders.customer_id,
	COALESCE(c.name, '') AS customer_name,
	COALESCE(purchase_orders.s3_url, '') AS s3_url,
	COALESCE((SELECT phf.field_value FROM po_header_fields phf
		JOIN field_definitions fd ON fd.field_id = phf.field_id
		WHERE phf.po_id = purchase_orders.po_id AND fd.field_name = 'po_number'
		ORDER BY phf.created_at ASC LIMIT 1), '') AS po_number,
	COALESCE((SELECT CASE WHEN phf2.field_value ~ '^-?[0-9]+(\.[0-9]+)?$' THEN phf2.field_value::numeric ELSE 0 END
		FROM po_header_fields phf2
		JOIN field_definitions fd2 ON fd2.field_id = phf2.field_id
		WHERE phf2.po_id = purchase_orders.po_id AND fd2.field_name = 'total_amount'
		ORDER BY phf2.created_at ASC LIMIT 1), 0) AS total_amount,
	purchase_orders.created_at,
	purchase_orders.modified_at`

func (r *purchaseOrderRepository) List(ctx context.Context, filter PurchaseOrderFilter) ([]dtos.PurchaseOrderListItem, int64, error) {
	q := r.db.WithContext(ctx).Model(&models.PurchaseOrder{}).
		Joins("LEFT JOIN customers c ON c.customer_id = purchase_orders.customer_id")
	if filter.CustomerID != nil {
		q = q.Where("purchase_orders.customer_id = ?", *filter.CustomerID)
	}
	if strings.TrimSpace(filter.Search) != "" {
		like := "%" + strings.TrimSpace(filter.Search) + "%"
		q = q.Where(`(c.name ILIKE ? OR EXISTS (
			SELECT 1 FROM po_header_fields phf
			JOIN field_definitions fd ON fd.field_id = phf.field_id
			WHERE phf.po_id = purchase_orders.po_id AND fd.field_name = 'po_number'
			AND phf.field_value ILIKE ?))`, like, like)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "count purchase orders", err)
	}

	var rows []dtos.PurchaseOrderListItem
	if err := q.Select(listSelect).
		Order("purchase_orders.created_at DESC").
		Limit(filter.Limit).Offset(filter.Offset).
		Scan(&rows).Error; err != nil {
		return nil, 0, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "list purchase orders", err)
	}
	return rows, total, nil
}

func (r *purchaseOrderRepository) Update(ctx context.Context, po *models.PurchaseOrder) error {
	res := r.db.WithContext(ctx).Model(&models.PurchaseOrder{}).
		Where("po_id = ?", po.POID).
		Updates(map[string]any{
			"customer_id": po.CustomerID,
			"s3_url":      po.S3URL,
			"modified_by": po.ModifiedBy,
			"modified_at": gorm.Expr("now()"),
		})
	if res.Error != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "update purchase order", res.Error)
	}
	if res.RowsAffected == 0 {
		return errorcodes.NotFound(errorcodes.CodePONotFound, "purchase order not found")
	}
	return nil
}

func (r *purchaseOrderRepository) ReplaceHeaderFields(ctx context.Context, poID uuid.UUID, fields []models.POHeaderField) error {
	err := r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Where("po_id = ?", poID).Delete(&models.POHeaderField{}).Error; err != nil {
			return err
		}
		for i := range fields {
			fields[i].POID = poID
			if err := tx.Create(&fields[i]).Error; err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "replace po header fields", err)
	}
	return nil
}

func (r *purchaseOrderRepository) UpdateLineItems(ctx context.Context, items []models.POLineItem) error {
	if len(items) == 0 {
		return nil
	}
	err := r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		for i := range items {
			if err := tx.Model(&models.POLineItem{}).
				Where("po_line_item_id = ?", items[i].POLineItemID).
				Updates(map[string]any{"product_id": items[i].ProductID, "modified_at": gorm.Expr("now()")}).Error; err != nil {
				return err
			}
			if err := tx.Where("po_line_item_id = ?", items[i].POLineItemID).
				Delete(&models.POLineItemField{}).Error; err != nil {
				return err
			}
			for j := range items[i].Fields {
				items[i].Fields[j].POLineItemID = items[i].POLineItemID
				if err := tx.Create(&items[i].Fields[j]).Error; err != nil {
					return err
				}
			}
		}
		return nil
	})
	if err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "update po line items", err)
	}
	return nil
}

func (r *purchaseOrderRepository) DeleteLineItems(ctx context.Context, poID uuid.UUID, keepIDs []uuid.UUID) error {
	q := r.db.WithContext(ctx).Where("po_id = ?", poID)
	if len(keepIDs) > 0 {
		q = q.Where("po_line_item_id NOT IN ?", keepIDs)
	}
	if err := q.Delete(&models.POLineItem{}).Error; err != nil {
		return errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "delete po line items", err)
	}
	return nil
}

func (r *purchaseOrderRepository) FieldByNames(ctx context.Context, names []string) (map[string]models.FieldDefinition, error) {
	out := make(map[string]models.FieldDefinition, len(names))
	if len(names) == 0 {
		return out, nil
	}
	uniq := make([]string, 0, len(names))
	seen := make(map[string]bool, len(names))
	for _, n := range names {
		if n == "" || seen[n] {
			continue
		}
		seen[n] = true
		uniq = append(uniq, n)
	}
	var defs []models.FieldDefinition
	if err := r.db.WithContext(ctx).Where("field_name IN ?", uniq).Find(&defs).Error; err != nil {
		return nil, errorcodes.Wrap(errorcodes.CodeDatabaseError, 500, "load field definitions", err)
	}
	for _, d := range defs {
		out[d.FieldName] = d
	}
	return out, nil
}

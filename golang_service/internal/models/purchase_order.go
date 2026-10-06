package models

import (
	"time"

	"github.com/google/uuid"
)

// PurchaseOrder represents an order placed by a customer (ER2: PURCHASE_ORDERS).
// PO-level extracted attributes live in PO_HEADER_FIELDS keyed by
// FIELD_DEFINITIONS rather than as fixed columns.
type PurchaseOrder struct {
	POID         uuid.UUID       `gorm:"column:po_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	CustomerID   uuid.UUID       `gorm:"column:customer_id;type:uuid"`
	Customer     Customer        `gorm:"foreignKey:CustomerID;references:CustomerID;belongsTo"`
	S3URL        string          `gorm:"column:s3_url;type:text"`
	CreatedBy    *uuid.UUID      `gorm:"column:created_by;type:uuid"`
	ModifiedBy   *uuid.UUID      `gorm:"column:modified_by;type:uuid"`
	HeaderFields []POHeaderField `gorm:"foreignKey:POID;references:POID"`
	LineItems    []POLineItem    `gorm:"foreignKey:POID;references:POID"`
	CreatedAt    time.Time       `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt   time.Time       `gorm:"column:modified_at;autoUpdateTime"`
}

func (PurchaseOrder) TableName() string { return "purchase_orders" }

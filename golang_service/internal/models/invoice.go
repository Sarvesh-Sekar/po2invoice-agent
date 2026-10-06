package models

import (
	"time"

	"github.com/google/uuid"
)

// Invoice represents a generated GST/e-invoice (ER2: INVOICES).
// Invoices are generated directly from a purchase order (whether one is
// produced is owned by the Python Agent Service). Golang only exposes
// read/access APIs. Status values: GENERATED, SENT.
type Invoice struct {
	InvoiceID     uuid.UUID     `gorm:"column:invoice_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	POID          uuid.UUID     `gorm:"column:po_id;type:uuid"`
	PurchaseOrder PurchaseOrder `gorm:"foreignKey:POID;references:POID;belongsTo"`
	InvoiceNumber string        `gorm:"column:invoice_number;size:128;index"`
	Status        string        `gorm:"size:32;not null;default:'DRAFT';index"`
	GSTIRN        string        `gorm:"column:gst_irn;size:128"`
	S3URL         string        `gorm:"column:s3_url;type:text"`
	CreatedAt     time.Time     `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt    time.Time     `gorm:"column:modified_at;autoUpdateTime"`
}

func (Invoice) TableName() string { return "invoices" }

// Invoice status values.
const (
	InvoiceStatusGenerated = "GENERATED"
	InvoiceStatusSent      = "SENT"
)

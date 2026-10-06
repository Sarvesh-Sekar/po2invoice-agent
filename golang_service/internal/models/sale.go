package models

import (
	"time"

	"github.com/google/uuid"
)

// Sale represents a sale derived from a purchase order (ER2: SALES).
// A purchase order creates at most one sale. Customer context is resolved
// through the purchase order.
type Sale struct {
	SaleID        uuid.UUID     `gorm:"column:sale_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	POID          uuid.UUID     `gorm:"column:po_id;type:uuid"`
	PurchaseOrder PurchaseOrder `gorm:"foreignKey:POID;references:POID;belongsTo"`
	Status        string        `gorm:"size:32;not null;default:'CREATED';index"`
	CreatedAt     time.Time     `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt    time.Time     `gorm:"column:modified_at;autoUpdateTime"`
}

func (Sale) TableName() string { return "sales" }

// Sale status values.
const (
	SaleStatusCreated    = "CREATED"
	SaleStatusConfirmed  = "CONFIRMED"
	SaleStatusProcessing = "PROCESSING"
	SaleStatusShipped    = "SHIPPED"
	SaleStatusDelivered  = "DELIVERED"
)

// SaleStatuses lists every valid sale status in transition order.
var SaleStatuses = []string{
	SaleStatusCreated,
	SaleStatusConfirmed,
	SaleStatusProcessing,
	SaleStatusShipped,
	SaleStatusDelivered,
}

// ValidSaleStatus reports whether s is a known sale status.
func ValidSaleStatus(s string) bool {
	for _, status := range SaleStatuses {
		if status == s {
			return true
		}
	}
	return false
}

// AllowedSaleTransition reports whether the transition from → to is permitted.
// Only sequential forward transitions are allowed (no skipping, no reversal).
func AllowedSaleTransition(from, to string) bool {
	var fromIdx, toIdx int = -1, -1
	for i, status := range SaleStatuses {
		if status == from {
			fromIdx = i
		}
		if status == to {
			toIdx = i
		}
	}
	if fromIdx < 0 || toIdx < 0 {
		return false
	}
	return toIdx == fromIdx+1
}

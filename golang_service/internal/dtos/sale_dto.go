package dtos

import (
	"time"

	"github.com/google/uuid"
)

// Sale DTOs (§ sales API). A sale is created from a purchase order; statuses
// transition sequentially (no skips, no reversals). Display-only fields
// (po_number, customer_name) are resolved through the purchase order.

type SaleRequest struct {
	POID uuid.UUID `json:"po_id" binding:"required"`
}

type SaleStatusUpdateRequest struct {
	Status string `json:"status" binding:"required,oneof=CONFIRMED PROCESSING SHIPPED DELIVERED"`
}

type SaleResponse struct {
	SaleID       uuid.UUID `json:"sale_id"`
	POID         uuid.UUID `json:"po_id"`
	Status       string    `json:"status"`
	PONumber     string    `json:"po_number,omitempty"`
	CustomerName string    `json:"customer_name,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
	ModifiedAt   time.Time `json:"modified_at"`
}
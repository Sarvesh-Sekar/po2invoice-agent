package dtos

import (
	"time"

	"github.com/google/uuid"
)

// Purchase order DTOs (§ purchase-orders API). PO data is normalized into
// PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS keyed by FIELD_DEFINITIONS, so
// create/update payloads carry field name/value pairs rather than fixed
// columns.

type POFieldRequest struct {
	FieldName  string `json:"field_name" binding:"required,max=128"`
	FieldValue string `json:"field_value"`
}

type POLineItemRequest struct {
	ProductID uuid.UUID       `json:"product_id" binding:"required"`
	Fields    []POFieldRequest `json:"fields"`
}

// PurchaseOrderRequest is the create payload.
type PurchaseOrderRequest struct {
	CustomerID   uuid.UUID           `json:"customer_id" binding:"required"`
	S3URL        string              `json:"s3_url" binding:"omitempty,max=2048"`
	HeaderFields []POFieldRequest    `json:"header_fields"`
	LineItems    []POLineItemRequest `json:"line_items" binding:"min=1"`
}

// PurchaseOrderUpdateRequest patches PO-level fields; address-type attributes
// are reconciled through header_fields.
type PurchaseOrderUpdateRequest struct {
	CustomerID   *uuid.UUID         `json:"customer_id" binding:"omitempty"`
	S3URL        *string            `json:"s3_url" binding:"omitempty,max=2048"`
	HeaderFields []POFieldRequest   `json:"header_fields"`
}

// POLineItemUpdateRequest patches the extracted attributes of one line item.
type POLineItemUpdateRequest struct {
	ProductID *uuid.UUID       `json:"product_id" binding:"omitempty"`
	Fields    []POFieldRequest `json:"fields"`
}

type POFieldResponse struct {
	FieldID    uuid.UUID `json:"field_id,omitempty"`
	FieldName  string    `json:"field_name"`
	FieldValue string    `json:"field_value"`
}

type POLineItemResponse struct {
	POLineItemID uuid.UUID         `json:"po_line_item_id"`
	ProductID    uuid.UUID         `json:"product_id"`
	Product      ProductResponse   `json:"product,omitempty"`
	Fields       []POFieldResponse `json:"fields"`
}

type PurchaseOrderResponse struct {
	POID         uuid.UUID            `json:"po_id"`
	CustomerID   uuid.UUID            `json:"customer_id"`
	Customer     CustomerResponse     `json:"customer,omitempty"`
	S3URL        string               `json:"s3_url"`
	HeaderFields []POFieldResponse    `json:"header_fields"`
	LineItems    []POLineItemResponse `json:"line_items"`
	CreatedBy    *uuid.UUID           `json:"created_by,omitempty"`
	ModifiedBy   *uuid.UUID           `json:"modified_by,omitempty"`
	CreatedAt    time.Time            `json:"created_at"`
	ModifiedAt   time.Time            `json:"modified_at"`
}

// PurchaseOrderListItem is the lightweight list shape.
type PurchaseOrderListItem struct {
	POID          uuid.UUID `json:"po_id"`
	CustomerID    uuid.UUID `json:"customer_id"`
	CustomerName  string    `json:"customer_name,omitempty"`
	S3URL         string    `json:"s3_url"`
	PONumber      string    `json:"po_number,omitempty"`
	TotalAmount   float64   `json:"total_amount,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
	ModifiedAt    time.Time `json:"modified_at"`
}

// PurchaseOrderFilters drives the PO list query.
type PurchaseOrderFilters struct {
	CustomerID *uuid.UUID `json:"customer_id,omitempty"`
	Search     string     `json:"search,omitempty"`
	Limit      int        `json:"limit,omitempty"`
	Offset     int        `json:"offset,omitempty"`
}
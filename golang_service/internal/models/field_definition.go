package models

import (
	"time"

	"github.com/google/uuid"
)

// FieldDefinition is the canonical descriptor of a PO attribute
// (ER2: FIELD_DEFINITIONS). Rows are seeded from field_definitions.yaml,
// which is the single source of truth for field names.
type FieldDefinition struct {
	FieldID          uuid.UUID `gorm:"column:field_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	FieldName        string    `gorm:"column:field_name;size:128;uniqueIndex"`
	FieldDescription string    `gorm:"column:field_description;size:255"`
	FieldType        string    `gorm:"column:field_type;size:32;not null;default:'string'"`
	CreatedAt        time.Time `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt       time.Time `gorm:"column:modified_at;autoUpdateTime"`
}

func (FieldDefinition) TableName() string { return "field_definitions" }

// Canonical PO header field names (mirrors python_service field_definitions.yaml).
const (
	HeaderFieldPONumber    = "po_number"
	HeaderFieldCustomer    = "customer"
	HeaderFieldGSTNo       = "gst_no"
	HeaderFieldPODate      = "po_date"
	HeaderFieldCurrency    = "currency"
	HeaderFieldShipTo      = "ship_to"
	HeaderFieldAddress1    = "address_1"
	HeaderFieldAddress2    = "address_2"
	HeaderFieldCity        = "city"
	HeaderFieldState       = "state"
	HeaderFieldCountry     = "country"
	HeaderFieldZip         = "zip"
	HeaderFieldTotalAmount = "total_amount"
)

// Canonical PO line-item field names.
const (
	LineItemFieldProductName = "product_name"
	LineItemFieldSKU         = "sku"
	LineItemFieldQuantity    = "quantity"
	LineItemFieldUnitPrice   = "unit_price"
	LineItemFieldTotalPrice  = "total_price"
)

// CanonicalHeaderFieldNames lists every canonical PO header field name.
var CanonicalHeaderFieldNames = []string{
	HeaderFieldPONumber,
	HeaderFieldCustomer,
	HeaderFieldGSTNo,
	HeaderFieldPODate,
	HeaderFieldCurrency,
	HeaderFieldShipTo,
	HeaderFieldAddress1,
	HeaderFieldAddress2,
	HeaderFieldCity,
	HeaderFieldState,
	HeaderFieldCountry,
	HeaderFieldZip,
	HeaderFieldTotalAmount,
}

// CanonicalLineItemFieldNames lists every canonical PO line-item field name.
var CanonicalLineItemFieldNames = []string{
	LineItemFieldProductName,
	LineItemFieldSKU,
	LineItemFieldQuantity,
	LineItemFieldUnitPrice,
	LineItemFieldTotalPrice,
}

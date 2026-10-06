package models

import (
	"time"

	"github.com/google/uuid"
)

// POLineItem is a single line on a purchase order (ER2: PO_LINE_ITEMS).
// Extracted line attributes live in PO_LINE_ITEM_FIELDS.
type POLineItem struct {
	POLineItemID uuid.UUID         `gorm:"column:po_line_item_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	POID         uuid.UUID         `gorm:"column:po_id;type:uuid;not null;index"`
	ProductID    uuid.UUID         `gorm:"column:product_id;type:uuid"`
	Product      Product           `gorm:"foreignKey:ProductID;references:ProductID;belongsTo"`
	Fields       []POLineItemField `gorm:"foreignKey:POLineItemID;references:POLineItemID"`
	CreatedAt    time.Time         `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt   time.Time         `gorm:"column:modified_at;autoUpdateTime"`
}

func (POLineItem) TableName() string { return "po_line_items" }

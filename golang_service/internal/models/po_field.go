package models

import (
	"time"

	"github.com/google/uuid"
)

// POHeaderField is an extracted PO-level attribute (ER2: PO_HEADER_FIELDS).
type POHeaderField struct {
	ID              uuid.UUID       `gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	POID            uuid.UUID       `gorm:"column:po_id;type:uuid;not null;index"`
	FieldID         uuid.UUID       `gorm:"column:field_id;type:uuid;not null;index"`
	FieldDefinition FieldDefinition `gorm:"foreignKey:FieldID;references:FieldID;belongsTo"`
	FieldValue      string          `gorm:"column:field_value;type:text"`
	CreatedAt       time.Time       `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt      time.Time       `gorm:"column:modified_at;autoUpdateTime"`
}

func (POHeaderField) TableName() string { return "po_header_fields" }

// POLineItemField is an extracted line-item attribute (ER2: PO_LINE_ITEM_FIELDS).
type POLineItemField struct {
	ID              uuid.UUID       `gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	POLineItemID    uuid.UUID       `gorm:"column:po_line_item_id;type:uuid;not null;index"`
	FieldID         uuid.UUID       `gorm:"column:field_id;type:uuid;not null;index"`
	FieldDefinition FieldDefinition `gorm:"foreignKey:FieldID;references:FieldID;belongsTo"`
	FieldValue      string          `gorm:"column:field_value;type:text"`
	CreatedAt       time.Time       `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt      time.Time       `gorm:"column:modified_at;autoUpdateTime"`
}

func (POLineItemField) TableName() string { return "po_line_item_fields" }

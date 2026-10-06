package models

import (
	"time"

	"github.com/google/uuid"
)

// Product represents an inventory item (ER2: PRODUCTS).
type Product struct {
	ProductID    uuid.UUID `gorm:"column:product_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	SKU          string    `gorm:"column:sku;size:128;uniqueIndex"`
	Name         string    `gorm:"size:255;not null;index"`
	CatalogPrice float64   `gorm:"column:catalog_price;type:numeric(14,2);not null;default:0"`
	Status       string    `gorm:"size:32;not null;default:'ACTIVE';index"`
	CreatedAt    time.Time `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt   time.Time `gorm:"column:modified_at;autoUpdateTime"`
}

func (Product) TableName() string { return "products" }

// Product status values.
const (
	ProductStatusActive   = "ACTIVE"
	ProductStatusInactive = "INACTIVE"
)
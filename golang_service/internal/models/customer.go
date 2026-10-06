package models

import (
	"time"

	"github.com/google/uuid"
)

// Customer represents a customer in the updated Order-to-Invoice architecture
// (ER2: CUSTOMERS). The physical primary key remains customer_id so the
// column matches the foreign keys used across the shared schema.
type Customer struct {
	CustomerID   uuid.UUID `gorm:"column:customer_id;type:uuid;primaryKey;default:gen_random_uuid()"`
	CustomerCode string    `gorm:"column:customer_code;size:64;uniqueIndex"`
	Name         string    `gorm:"size:255;not null;index"`
	Status       string    `gorm:"size:32;not null;default:'ACTIVE';index"`
	CreatedAt    time.Time `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt   time.Time `gorm:"column:modified_at;autoUpdateTime"`
}

func (Customer) TableName() string { return "customers" }

// Customer status values.
const (
	CustomerStatusActive   = "ACTIVE"
	CustomerStatusInactive = "INACTIVE"
)
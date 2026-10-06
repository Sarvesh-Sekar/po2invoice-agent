package models

import (
	"time"

	"github.com/google/uuid"
)

// EpisodicMemory records a learned extraction pattern for a customer/field
// pair (ER2: EPISODIC_MEMORY). Owned by the Python Agent Service; the Golang
// service only needs the model for schema fidelity and shared access.
type EpisodicMemory struct {
	ID              uuid.UUID  `gorm:"type:uuid;primaryKey;default:gen_random_uuid()"`
	CustomerID      uuid.UUID  `gorm:"column:customer_id;type:uuid;not null;index"`
	FieldID         uuid.UUID  `gorm:"column:field_id;type:uuid;not null;index"`
	LocationHint    string     `gorm:"column:location_hint;size:255"`
	DocumentPattern string     `gorm:"column:document_pattern;size:255"`
	Instruction     string     `gorm:"column:instruction;type:text"`
	Confidence      float64    `gorm:"type:numeric(5,4)"`
	UsageCount      int        `gorm:"column:usage_count;not null;default:0"`
	SuccessCount    int        `gorm:"column:success_count;not null;default:0"`
	FailureCount    int        `gorm:"column:failure_count;not null;default:0"`
	LastUsedAt      *time.Time `gorm:"column:last_used_at"`
	CreatedAt       time.Time  `gorm:"column:created_at;autoCreateTime"`
	ModifiedAt      time.Time  `gorm:"column:modified_at;autoUpdateTime"`
}

func (EpisodicMemory) TableName() string { return "episodic_memory" }
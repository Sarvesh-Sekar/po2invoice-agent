package dtos

import (
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/models"
)

// Customer DTOs (§ customers API).

type CustomerRequest struct {
	CustomerCode string `json:"customer_code" binding:"required,max=64"`
	Name         string `json:"name" binding:"required,max=255"`
	Status       string `json:"status" binding:"omitempty,oneof=ACTIVE INACTIVE"`
}

type CustomerUpdateRequest struct {
	CustomerCode *string `json:"customer_code" binding:"omitempty,max=64"`
	Name         *string `json:"name" binding:"omitempty,max=255"`
	Status       *string `json:"status" binding:"omitempty,oneof=ACTIVE INACTIVE"`
}

type CustomerResponse struct {
	CustomerID   uuid.UUID `json:"customer_id"`
	CustomerCode string    `json:"customer_code"`
	Name         string    `json:"name"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
	ModifiedAt   time.Time `json:"modified_at"`
}

func CustomerToResponse(c models.Customer) CustomerResponse {
	return CustomerResponse{
		CustomerID:   c.CustomerID,
		CustomerCode: c.CustomerCode,
		Name:         c.Name,
		Status:       c.Status,
		CreatedAt:    c.CreatedAt,
		ModifiedAt:   c.ModifiedAt,
	}
}

func CustomersToResponse(list []models.Customer) []CustomerResponse {
	out := make([]CustomerResponse, 0, len(list))
	for _, c := range list {
		out = append(out, CustomerToResponse(c))
	}
	return out
}
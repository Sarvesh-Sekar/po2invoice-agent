package dtos

import (
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/models"
)

// Product DTOs (§ products API).

type ProductRequest struct {
	Name         string  `json:"name" binding:"required,max=255"`
	SKU          string  `json:"sku" binding:"required,max=128"`
	CatalogPrice float64 `json:"catalog_price" binding:"omitempty,min=0"`
	Status       string  `json:"status" binding:"omitempty,oneof=ACTIVE INACTIVE"`
}

type ProductUpdateRequest struct {
	Name         *string  `json:"name" binding:"omitempty,max=255"`
	SKU          *string  `json:"sku" binding:"omitempty,max=128"`
	CatalogPrice *float64 `json:"catalog_price" binding:"omitempty,min=0"`
	Status       *string  `json:"status" binding:"omitempty,oneof=ACTIVE INACTIVE"`
}

type ProductResponse struct {
	ProductID    uuid.UUID `json:"product_id"`
	Name         string    `json:"name"`
	SKU          string    `json:"sku"`
	CatalogPrice float64   `json:"catalog_price"`
	Status       string    `json:"status"`
	CreatedAt    time.Time `json:"created_at"`
	ModifiedAt   time.Time `json:"modified_at"`
}

func ProductToResponse(p models.Product) ProductResponse {
	return ProductResponse{
		ProductID:    p.ProductID,
		Name:         p.Name,
		SKU:          p.SKU,
		CatalogPrice: p.CatalogPrice,
		Status:       p.Status,
		CreatedAt:    p.CreatedAt,
		ModifiedAt:   p.ModifiedAt,
	}
}

func ProductsToResponse(list []models.Product) []ProductResponse {
	out := make([]ProductResponse, 0, len(list))
	for _, p := range list {
		out = append(out, ProductToResponse(p))
	}
	return out
}
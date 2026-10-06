package services

import (
	"context"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
)

// ProductService (§ product API).
type ProductService interface {
	Create(ctx context.Context, req dtos.ProductRequest) (*dtos.ProductResponse, error)
	GetByID(ctx context.Context, id uuid.UUID) (*dtos.ProductResponse, error)
	List(ctx context.Context, search string, limit, offset int) ([]dtos.ProductResponse, int64, error)
	Update(ctx context.Context, id uuid.UUID, req dtos.ProductUpdateRequest) (*dtos.ProductResponse, error)
}

type productService struct{ repo repository.ProductRepository }

func NewProductService(repo repository.ProductRepository) ProductService {
	return &productService{repo: repo}
}

func (s *productService) Create(ctx context.Context, req dtos.ProductRequest) (*dtos.ProductResponse, error) {
	if existing, _ := s.repo.BySKU(ctx, req.SKU); existing != nil {
		return nil, errorcodes.Conflict(errorcodes.CodeProductExists, "product with this SKU already exists")
	}
	status := req.Status
	if status == "" {
		status = models.ProductStatusActive
	}
	p := &models.Product{
		SKU:          req.SKU,
		Name:         req.Name,
		CatalogPrice: req.CatalogPrice,
		Status:       status,
	}
	if err := s.repo.Create(ctx, p); err != nil {
		return nil, err
	}
	out := dtos.ProductToResponse(*p)
	return &out, nil
}

func (s *productService) GetByID(ctx context.Context, id uuid.UUID) (*dtos.ProductResponse, error) {
	p, err := s.repo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	out := dtos.ProductToResponse(*p)
	return &out, nil
}

func (s *productService) List(ctx context.Context, search string, limit, offset int) ([]dtos.ProductResponse, int64, error) {
	products, total, err := s.repo.List(ctx, repository.ProductFilter{
		Search: search, Limit: limit, Offset: offset,
	})
	if err != nil {
		return nil, 0, err
	}
	return dtos.ProductsToResponse(products), total, nil
}

func (s *productService) Update(ctx context.Context, id uuid.UUID, req dtos.ProductUpdateRequest) (*dtos.ProductResponse, error) {
	p, err := s.repo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if req.SKU != nil {
		if existing, _ := s.repo.BySKU(ctx, *req.SKU); existing != nil && existing.ProductID != id {
			return nil, errorcodes.Conflict(errorcodes.CodeProductExists, "product with this SKU already exists")
		}
		p.SKU = *req.SKU
	}
	if req.Name != nil {
		p.Name = *req.Name
	}
	if req.CatalogPrice != nil {
		p.CatalogPrice = *req.CatalogPrice
	}
	if req.Status != nil {
		p.Status = *req.Status
	}
	if err := s.repo.Update(ctx, p); err != nil {
		return nil, err
	}
	out := dtos.ProductToResponse(*p)
	return &out, nil
}
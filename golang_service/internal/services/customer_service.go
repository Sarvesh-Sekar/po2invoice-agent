package services

import (
	"context"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
)

// CustomerService (§ customer API).
type CustomerService interface {
	Create(ctx context.Context, req dtos.CustomerRequest) (*dtos.CustomerResponse, error)
	GetByID(ctx context.Context, id uuid.UUID) (*dtos.CustomerResponse, error)
	List(ctx context.Context, search string, limit, offset int) ([]dtos.CustomerResponse, int64, error)
	Update(ctx context.Context, id uuid.UUID, req dtos.CustomerUpdateRequest) (*dtos.CustomerResponse, error)
	Delete(ctx context.Context, id uuid.UUID) error
}

type customerService struct{ repo repository.CustomerRepository }

func NewCustomerService(repo repository.CustomerRepository) CustomerService {
	return &customerService{repo: repo}
}

func (s *customerService) Create(ctx context.Context, req dtos.CustomerRequest) (*dtos.CustomerResponse, error) {
	if existing, _ := s.repo.ByCustomerCode(ctx, req.CustomerCode); existing != nil {
		return nil, errorcodes.Conflict(errorcodes.CodeCustomerExists, "customer with this code already exists")
	}
	status := req.Status
	if status == "" {
		status = models.CustomerStatusActive
	}
	c := &models.Customer{
		CustomerCode: req.CustomerCode,
		Name:         req.Name,
		Status:       status,
	}
	if err := s.repo.Create(ctx, c); err != nil {
		return nil, err
	}
	out := dtos.CustomerToResponse(*c)
	return &out, nil
}

func (s *customerService) GetByID(ctx context.Context, id uuid.UUID) (*dtos.CustomerResponse, error) {
	c, err := s.repo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	out := dtos.CustomerToResponse(*c)
	return &out, nil
}

func (s *customerService) List(ctx context.Context, search string, limit, offset int) ([]dtos.CustomerResponse, int64, error) {
	customers, total, err := s.repo.List(ctx, repository.CustomerFilter{
		Search: search, Limit: limit, Offset: offset,
	})
	if err != nil {
		return nil, 0, err
	}
	return dtos.CustomersToResponse(customers), total, nil
}

func (s *customerService) Update(ctx context.Context, id uuid.UUID, req dtos.CustomerUpdateRequest) (*dtos.CustomerResponse, error) {
	c, err := s.repo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if req.CustomerCode != nil {
		if existing, _ := s.repo.ByCustomerCode(ctx, *req.CustomerCode); existing != nil && existing.CustomerID != id {
			return nil, errorcodes.Conflict(errorcodes.CodeCustomerExists, "customer with this code already exists")
		}
		c.CustomerCode = *req.CustomerCode
	}
	if req.Name != nil {
		c.Name = *req.Name
	}
	if req.Status != nil {
		c.Status = *req.Status
	}
	if err := s.repo.Update(ctx, c); err != nil {
		return nil, err
	}
	out := dtos.CustomerToResponse(*c)
	return &out, nil
}

func (s *customerService) Delete(ctx context.Context, id uuid.UUID) error {
	return s.repo.Delete(ctx, id)
}
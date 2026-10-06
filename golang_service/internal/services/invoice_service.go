package services

import (
	"context"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/repository"
)

// InvoiceService exposes read/download APIs over invoices written by the
// Python service (§ invoices API).
type InvoiceService interface {
	GetByID(ctx context.Context, id uuid.UUID) (*dtos.InvoiceResponse, error)
	List(ctx context.Context, status, poID, customerID, search string, limit, offset int) ([]dtos.InvoiceResponse, int64, error)
}

type invoiceService struct{ repo repository.InvoiceRepository }

func NewInvoiceService(repo repository.InvoiceRepository) InvoiceService {
	return &invoiceService{repo: repo}
}

func (s *invoiceService) GetByID(ctx context.Context, id uuid.UUID) (*dtos.InvoiceResponse, error) {
	inv, err := s.repo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return toInvoiceResponse(inv), nil
}

func (s *invoiceService) List(ctx context.Context, status, poID, customerID, search string, limit, offset int) ([]dtos.InvoiceResponse, int64, error) {
	invs, total, err := s.repo.List(ctx, repository.InvoiceFilter{
		Status: status, POID: poID, CustomerID: customerID,
		Search: search, Limit: limit, Offset: offset,
	})
	if err != nil {
		return nil, 0, err
	}
	out := make([]dtos.InvoiceResponse, 0, len(invs))
	for _, inv := range invs {
		out = append(out, *toInvoiceResponse(&inv))
	}
	return out, total, nil
}
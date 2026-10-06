package services

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/agentclient"
	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
)

// SaleService (§ sales API). A sale derives from a purchase order (single
// sale per PO), statuses advance sequentially, and DELIVERED fires the
// SALE_DELIVERED event to the Python agent service.
type SaleService interface {
	Create(ctx context.Context, req dtos.SaleRequest) (*dtos.SaleResponse, error)
	GetByID(ctx context.Context, id uuid.UUID) (*dtos.SaleResponse, error)
	List(ctx context.Context, status, customerID string, limit, offset int) ([]dtos.SaleResponse, int64, error)
	UpdateStatus(ctx context.Context, id uuid.UUID, status string) (*dtos.SaleResponse, error)
}

// saleEventNotifier abstracts the Go→Python SALE_DELIVERED dispatch so unit
// tests can stub it.
type saleEventNotifier interface {
	NotifySaleDelivered(ctx context.Context, saleID string, occurredAt time.Time, idempotencyKey string) error
}

type saleService struct {
	saleRepo      repository.SaleRepository
	poRepo        repository.PurchaseOrderRepository
	eventNotifier saleEventNotifier
}

func NewSaleService(
	saleRepo repository.SaleRepository,
	poRepo repository.PurchaseOrderRepository,
	client *agentclient.AgentEventClient,
) SaleService {
	return &saleService{saleRepo: saleRepo, poRepo: poRepo, eventNotifier: client}
}

func (s *saleService) Create(ctx context.Context, req dtos.SaleRequest) (*dtos.SaleResponse, error) {
	if existing, err := s.saleRepo.ByPOID(ctx, req.POID); err == nil && existing != nil {
		return nil, errorcodes.Conflict(errorcodes.CodeDuplicateSale, "a sale already exists for this purchase order")
	}
	if _, err := s.poRepo.ByID(ctx, req.POID); err != nil {
		return nil, errorcodes.NotFound(errorcodes.CodePONotFound, "purchase order not found")
	}

	sale := &models.Sale{
		POID:   req.POID,
		Status: models.SaleStatusCreated,
	}
	if err := s.saleRepo.Create(ctx, sale); err != nil {
		return nil, err
	}
	return s.toResponse(sale), nil
}

func (s *saleService) GetByID(ctx context.Context, id uuid.UUID) (*dtos.SaleResponse, error) {
	sale, err := s.saleRepo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return s.toResponse(sale), nil
}

func (s *saleService) List(ctx context.Context, status, customerID string, limit, offset int) ([]dtos.SaleResponse, int64, error) {
	sales, total, err := s.saleRepo.List(ctx, repository.SaleFilter{
		Status: status, CustomerID: customerID, Limit: limit, Offset: offset,
	})
	if err != nil {
		return nil, 0, err
	}
	out := make([]dtos.SaleResponse, 0, len(sales))
	for _, sale := range sales {
		out = append(out, *s.toResponse(&sale))
	}
	return out, total, nil
}

func (s *saleService) UpdateStatus(ctx context.Context, id uuid.UUID, status string) (*dtos.SaleResponse, error) {
	if !models.ValidSaleStatus(status) || status == models.SaleStatusCreated {
		return nil, errorcodes.InvalidRequest("invalid sale status")
	}
	sale, err := s.saleRepo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if !models.AllowedSaleTransition(sale.Status, status) {
		return nil, errorcodes.Conflict(errorcodes.CodeInvalidSaleStatus,
			"invalid status transition from "+sale.Status+" to "+status)
	}
	sale.Status = status
	if err := s.saleRepo.Update(ctx, sale); err != nil {
		return nil, err
	}

	if status == models.SaleStatusDelivered {
		eventCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = s.eventNotifier.NotifySaleDelivered(
			eventCtx,
			sale.SaleID.String(),
			time.Now(),
			"sale-"+sale.SaleID.String(),
		)
	}
	return s.toResponse(sale), nil
}

func (s *saleService) toResponse(sale *models.Sale) *dtos.SaleResponse {
	resp := &dtos.SaleResponse{
		SaleID:     sale.SaleID,
		POID:       sale.POID,
		Status:     sale.Status,
		CreatedAt:  sale.CreatedAt,
		ModifiedAt: sale.ModifiedAt,
	}
	po := sale.PurchaseOrder
	if po.POID != uuid.Nil {
		resp.PONumber = headerFieldValue(po.HeaderFields, models.HeaderFieldPONumber)
		if po.Customer.CustomerID != uuid.Nil {
			resp.CustomerName = po.Customer.Name
		}
	}
	return resp
}

// headerFieldValue returns the value of the named header field, if present.
func headerFieldValue(fields []models.POHeaderField, name string) string {
	for _, f := range fields {
		if f.FieldDefinition.FieldName == name {
			return f.FieldValue
		}
	}
	return ""
}
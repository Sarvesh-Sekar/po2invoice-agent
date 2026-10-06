package services

import (
	"context"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
)

// PurchaseOrderService (§ purchase-orders API). PO data is normalized into
// PO_HEADER_FIELDS / PO_LINE_ITEM_FIELDS keyed by FIELD_DEFINITIONS; manual
// create/update validates customer, product references and field names before
// persisting in a transaction.
type PurchaseOrderService interface {
	Create(ctx context.Context, req dtos.PurchaseOrderRequest) (*dtos.PurchaseOrderResponse, error)
	GetByID(ctx context.Context, id uuid.UUID) (*dtos.PurchaseOrderResponse, error)
	List(ctx context.Context, customerID string, search string, limit, offset int) ([]dtos.PurchaseOrderListItem, int64, error)
	Update(ctx context.Context, id uuid.UUID, req dtos.PurchaseOrderUpdateRequest) (*dtos.PurchaseOrderResponse, error)
	UpdateLineItem(ctx context.Context, poID, lineItemID uuid.UUID, req dtos.POLineItemUpdateRequest) (*dtos.PurchaseOrderResponse, error)
}

type purchaseOrderService struct {
	poRepo       repository.PurchaseOrderRepository
	customerRepo repository.CustomerRepository
	productRepo  repository.ProductRepository
}

func NewPurchaseOrderService(
	poRepo repository.PurchaseOrderRepository,
	customerRepo repository.CustomerRepository,
	productRepo repository.ProductRepository,
) PurchaseOrderService {
	return &purchaseOrderService{poRepo: poRepo, customerRepo: customerRepo, productRepo: productRepo}
}

func (s *purchaseOrderService) Create(ctx context.Context, req dtos.PurchaseOrderRequest) (*dtos.PurchaseOrderResponse, error) {
	if _, err := s.customerRepo.ByID(ctx, req.CustomerID); err != nil {
		return nil, errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
	}

	productIDs := make([]uuid.UUID, 0, len(req.LineItems))
	for _, item := range req.LineItems {
		productIDs = append(productIDs, item.ProductID)
	}
	ok, err := s.productRepo.ExistsForIDs(ctx, productIDs)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, errorcodes.NotFound(errorcodes.CodeProductNotFound, "one or more products not found")
	}

	defs, err := s.collectFieldDefinitions(ctx, req)
	if err != nil {
		return nil, err
	}

	headerFields := make([]models.POHeaderField, 0, len(req.HeaderFields))
	for _, f := range req.HeaderFields {
		headerFields = append(headerFields, models.POHeaderField{
			FieldID: defs[f.FieldName].FieldID, FieldValue: f.FieldValue,
		})
	}

	lineItems := make([]models.POLineItem, 0, len(req.LineItems))
	for _, item := range req.LineItems {
		fields := make([]models.POLineItemField, 0, len(item.Fields))
		for _, f := range item.Fields {
			fields = append(fields, models.POLineItemField{
				FieldID: defs[f.FieldName].FieldID, FieldValue: f.FieldValue,
			})
		}
		lineItems = append(lineItems, models.POLineItem{ProductID: item.ProductID, Fields: fields})
	}

	po := &models.PurchaseOrder{
		CustomerID:   req.CustomerID,
		S3URL:        req.S3URL,
		HeaderFields: headerFields,
		LineItems:    lineItems,
	}
	if err := s.poRepo.Create(ctx, po); err != nil {
		return nil, err
	}
	return s.GetByID(ctx, po.POID)
}

func (s *purchaseOrderService) GetByID(ctx context.Context, id uuid.UUID) (*dtos.PurchaseOrderResponse, error) {
	po, err := s.poRepo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return s.poToResponse(po), nil
}

func (s *purchaseOrderService) List(ctx context.Context, customerID string, search string, limit, offset int) ([]dtos.PurchaseOrderListItem, int64, error) {
	filter := repository.PurchaseOrderFilter{Search: search, Limit: limit, Offset: offset}
	if customerID != "" {
		id, err := uuid.Parse(customerID)
		if err != nil {
			return nil, 0, errorcodes.InvalidRequest("invalid customer_id")
		}
		filter.CustomerID = &id
	}
	return s.poRepo.List(ctx, filter)
}

func (s *purchaseOrderService) Update(ctx context.Context, id uuid.UUID, req dtos.PurchaseOrderUpdateRequest) (*dtos.PurchaseOrderResponse, error) {
	po, err := s.poRepo.ByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if req.CustomerID != nil {
		if _, err := s.customerRepo.ByID(ctx, *req.CustomerID); err != nil {
			return nil, errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
		}
		po.CustomerID = *req.CustomerID
	}
	if req.S3URL != nil {
		po.S3URL = *req.S3URL
	}
	if err := s.poRepo.Update(ctx, po); err != nil {
		return nil, err
	}

	if len(req.HeaderFields) > 0 {
		names := make([]string, 0, len(req.HeaderFields))
		for _, f := range req.HeaderFields {
			names = append(names, f.FieldName)
		}
		defs, err := s.poRepo.FieldByNames(ctx, names)
		if err != nil {
			return nil, err
		}
		for _, n := range names {
			if _, ok := defs[n]; !ok {
				return nil, errorcodes.InvalidRequest("unknown field definition: " + n)
			}
		}
		fields := make([]models.POHeaderField, 0, len(req.HeaderFields))
		for _, f := range req.HeaderFields {
			fields = append(fields, models.POHeaderField{
				FieldID: defs[f.FieldName].FieldID, FieldValue: f.FieldValue,
			})
		}
		if err := s.poRepo.ReplaceHeaderFields(ctx, id, fields); err != nil {
			return nil, err
		}
	}
	return s.GetByID(ctx, id)
}

func (s *purchaseOrderService) UpdateLineItem(ctx context.Context, poID, lineItemID uuid.UUID, req dtos.POLineItemUpdateRequest) (*dtos.PurchaseOrderResponse, error) {
	po, err := s.poRepo.ByID(ctx, poID)
	if err != nil {
		return nil, err
	}

	next := models.POLineItem{POLineItemID: lineItemID}
	found := false
	for _, item := range po.LineItems {
		if item.POLineItemID == lineItemID {
			found = true
			next.ProductID = item.ProductID
			break
		}
	}
	if !found {
		return nil, errorcodes.NotFound(errorcodes.CodePONotFound, "line item not found on this purchase order")
	}
	if req.ProductID != nil {
		next.ProductID = *req.ProductID
	}

	if len(req.Fields) > 0 {
		names := make([]string, 0, len(req.Fields))
		for _, f := range req.Fields {
			names = append(names, f.FieldName)
		}
		defs, err := s.poRepo.FieldByNames(ctx, names)
		if err != nil {
			return nil, err
		}
		for _, n := range names {
			if _, ok := defs[n]; !ok {
				return nil, errorcodes.InvalidRequest("unknown field definition: " + n)
			}
		}
		fields := make([]models.POLineItemField, 0, len(req.Fields))
		for _, f := range req.Fields {
			fields = append(fields, models.POLineItemField{
				FieldID: defs[f.FieldName].FieldID, FieldValue: f.FieldValue,
			})
		}
		next.Fields = fields
	}

	if err := s.poRepo.UpdateLineItems(ctx, []models.POLineItem{next}); err != nil {
		return nil, err
	}
	return s.GetByID(ctx, poID)
}

// collectFieldDefinitions resolves every field name referenced by a create
// payload against FIELD_DEFINITIONS and rejects unknown names.
func (s *purchaseOrderService) collectFieldDefinitions(ctx context.Context, req dtos.PurchaseOrderRequest) (map[string]models.FieldDefinition, error) {
	names := make([]string, 0, len(req.HeaderFields))
	for _, f := range req.HeaderFields {
		names = append(names, f.FieldName)
	}
	for _, item := range req.LineItems {
		for _, f := range item.Fields {
			names = append(names, f.FieldName)
		}
	}
	if len(names) == 0 {
		return map[string]models.FieldDefinition{}, nil
	}
	defs, err := s.poRepo.FieldByNames(ctx, names)
	if err != nil {
		return nil, err
	}
	for _, n := range names {
		if _, ok := defs[n]; !ok {
			return nil, errorcodes.InvalidRequest("unknown field definition: " + n)
		}
	}
	return defs, nil
}

func (s *purchaseOrderService) poToResponse(po *models.PurchaseOrder) *dtos.PurchaseOrderResponse {
	headerFields := make([]dtos.POFieldResponse, 0, len(po.HeaderFields))
	for _, hf := range po.HeaderFields {
		name := ""
		if hf.FieldDefinition.FieldID != uuid.Nil {
			name = hf.FieldDefinition.FieldName
		}
		headerFields = append(headerFields, dtos.POFieldResponse{
			FieldID: hf.FieldID, FieldName: name, FieldValue: hf.FieldValue,
		})
	}

	items := make([]dtos.POLineItemResponse, 0, len(po.LineItems))
	for _, item := range po.LineItems {
		fields := make([]dtos.POFieldResponse, 0, len(item.Fields))
		for _, f := range item.Fields {
			name := ""
			if f.FieldDefinition.FieldID != uuid.Nil {
				name = f.FieldDefinition.FieldName
			}
			fields = append(fields, dtos.POFieldResponse{
				FieldID: f.FieldID, FieldName: name, FieldValue: f.FieldValue,
			})
		}
		var prod dtos.ProductResponse
		if item.Product.ProductID != uuid.Nil {
			prod = dtos.ProductToResponse(item.Product)
		}
		items = append(items, dtos.POLineItemResponse{
			POLineItemID: item.POLineItemID,
			ProductID:    item.ProductID,
			Product:      prod,
			Fields:       fields,
		})
	}

	var cust dtos.CustomerResponse
	if po.Customer.CustomerID != uuid.Nil {
		cust = dtos.CustomerToResponse(po.Customer)
	}

	return &dtos.PurchaseOrderResponse{
		POID:         po.POID,
		CustomerID:   po.CustomerID,
		Customer:     cust,
		S3URL:        po.S3URL,
		HeaderFields: headerFields,
		LineItems:    items,
		CreatedBy:    po.CreatedBy,
		ModifiedBy:   po.ModifiedBy,
		CreatedAt:    po.CreatedAt,
		ModifiedAt:   po.ModifiedAt,
	}
}
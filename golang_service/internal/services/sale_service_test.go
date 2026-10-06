package services

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/googleauth"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
)

type fakeAuthenticator struct{}

func (f *fakeAuthenticator) AuthorizeURL(state string) string {
	return "https://accounts.google.com/" + state
}

func (f *fakeAuthenticator) ExchangeCode(_ context.Context, _ string) (*googleauth.UserInfo, error) {
	return &googleauth.UserInfo{ID: "google-1", Email: "test@example.com", Name: "Test User"}, nil
}

// ---------------------------------------------------------------------------
// fakeSaleRepo implements repository.SaleRepository over an in-memory map.
// ---------------------------------------------------------------------------

type fakeSaleRepo struct {
	sales       map[uuid.UUID]*models.Sale
	byPOIDHits  []uuid.UUID
	createErr   error
	updateErr   error
	notFoundErr bool
}

func newFakeSaleRepo() *fakeSaleRepo {
	return &fakeSaleRepo{sales: map[uuid.UUID]*models.Sale{}}
}

func (f *fakeSaleRepo) Create(_ context.Context, s *models.Sale) error {
	if f.createErr != nil {
		return f.createErr
	}
	if s.SaleID == uuid.Nil {
		s.SaleID = uuid.New()
	}
	f.sales[s.SaleID] = s
	return nil
}

func (f *fakeSaleRepo) ByID(_ context.Context, id uuid.UUID) (*models.Sale, error) {
	if s, ok := f.sales[id]; ok {
		return s, nil
	}
	return nil, errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
}

func (f *fakeSaleRepo) ByPOID(_ context.Context, poID uuid.UUID) (*models.Sale, error) {
	f.byPOIDHits = append(f.byPOIDHits, poID)
	for _, s := range f.sales {
		if s.POID == poID {
			return s, nil
		}
	}
	return nil, errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
}

func (f *fakeSaleRepo) List(_ context.Context, _ repository.SaleFilter) ([]models.Sale, int64, error) {
	return nil, 0, nil
}

func (f *fakeSaleRepo) Update(_ context.Context, s *models.Sale) error {
	if f.updateErr != nil {
		return f.updateErr
	}
	stored, ok := f.sales[s.SaleID]
	if !ok {
		return errorcodes.NotFound(errorcodes.CodeSaleNotFound, "sale not found")
	}
	stored.Status = s.Status
	return nil
}

// ---------------------------------------------------------------------------
// fakePORepo implements repository.PurchaseOrderRepository (ByID is enough for
// sale creation/transition tests).
// ---------------------------------------------------------------------------

type fakePORepo struct {
	order *models.PurchaseOrder
}

func (f *fakePORepo) Create(context.Context, *models.PurchaseOrder) error { return nil }
func (f *fakePORepo) ByID(_ context.Context, _ uuid.UUID) (*models.PurchaseOrder, error) {
	if f.order == nil {
		return nil, errorcodes.NotFound(errorcodes.CodePONotFound, "purchase order not found")
	}
	return f.order, nil
}
func (f *fakePORepo) List(context.Context, repository.PurchaseOrderFilter) ([]dtos.PurchaseOrderListItem, int64, error) {
	return nil, 0, nil
}
func (f *fakePORepo) Update(context.Context, *models.PurchaseOrder) error { return nil }
func (f *fakePORepo) ReplaceHeaderFields(context.Context, uuid.UUID, []models.POHeaderField) error {
	return nil
}
func (f *fakePORepo) UpdateLineItems(context.Context, []models.POLineItem) error    { return nil }
func (f *fakePORepo) DeleteLineItems(context.Context, uuid.UUID, []uuid.UUID) error { return nil }
func (f *fakePORepo) FieldByNames(context.Context, []string) (map[string]models.FieldDefinition, error) {
	return map[string]models.FieldDefinition{}, nil
}

type fakeNotifier struct {
	calls []saleDeliveryCall
	fail  error
}

type saleDeliveryCall struct {
	saleID string
	key    string
}

func (f *fakeNotifier) NotifySaleDelivered(_ context.Context, saleID string, _ time.Time, idempotencyKey string) error {
	if f.fail != nil {
		return f.fail
	}
	f.calls = append(f.calls, saleDeliveryCall{saleID: saleID, key: idempotencyKey})
	return nil
}

func newSaleServiceForTest(sr *fakeSaleRepo, po *fakePORepo, n *fakeNotifier) SaleService {
	return &saleService{saleRepo: sr, poRepo: po, eventNotifier: n}
}

func existingPO() *fakePORepo {
	return &fakePORepo{order: &models.PurchaseOrder{POID: uuid.New()}}
}

func TestCreateSaleRequiresExistingPO(t *testing.T) {
	sales := newFakeSaleRepo()
	svc := newSaleServiceForTest(sales, &fakePORepo{}, &fakeNotifier{})

	if _, err := svc.Create(context.Background(), dtosSaleRequest(uuid.New())); !isAppError(err, errorcodes.CodePONotFound) {
		t.Fatalf("expected purchase order not found, got %v", err)
	}
}

func TestCreateSaleDuplicatePO(t *testing.T) {
	sales := newFakeSaleRepo()
	po := existingPO()
	existing := &models.Sale{SaleID: uuid.New(), POID: po.order.POID, Status: models.SaleStatusCreated}
	sales.sales[existing.SaleID] = existing

	svc := newSaleServiceForTest(sales, po, &fakeNotifier{})
	if _, err := svc.Create(context.Background(), dtosSaleRequest(po.order.POID)); !isAppError(err, errorcodes.CodeDuplicateSale) {
		t.Fatalf("expected duplicate sale, got %v", err)
	}
}

func TestCreateSaleSuccess(t *testing.T) {
	sales := newFakeSaleRepo()
	po := existingPO()
	svc := newSaleServiceForTest(sales, po, &fakeNotifier{})

	out, err := svc.Create(context.Background(), dtosSaleRequest(po.order.POID))
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if out.Status != models.SaleStatusCreated || out.POID != po.order.POID {
		t.Fatalf("unexpected sale: %+v", out)
	}
	if len(sales.byPOIDHits) == 0 {
		t.Fatal("duplicate check should hit ByPOID")
	}
}

func TestUpdateStatusRejectsSkippedTransition(t *testing.T) {
	sales := newFakeSaleRepo()
	sale := &models.Sale{SaleID: uuid.New(), POID: uuid.New(), Status: models.SaleStatusCreated}
	sales.sales[sale.SaleID] = sale
	svc := newSaleServiceForTest(sales, &fakePORepo{}, &fakeNotifier{})

	if _, err := svc.UpdateStatus(context.Background(), sale.SaleID, models.SaleStatusDelivered); !isAppError(err, errorcodes.CodeInvalidSaleStatus) {
		t.Fatalf("expected invalid transition, got %v", err)
	}
}

func TestUpdateStatusWalkToDeliveredFiresEvent(t *testing.T) {
	sales := newFakeSaleRepo()
	sale := &models.Sale{SaleID: uuid.New(), POID: uuid.New(), Status: models.SaleStatusCreated}
	sales.sales[sale.SaleID] = sale
	notifier := &fakeNotifier{}
	svc := newSaleServiceForTest(sales, &fakePORepo{}, notifier)

	steps := []string{models.SaleStatusConfirmed, models.SaleStatusProcessing, models.SaleStatusShipped, models.SaleStatusDelivered}
	for _, st := range steps {
		if _, err := svc.UpdateStatus(context.Background(), sale.SaleID, st); err != nil {
			t.Fatalf("transition to %s: %v", st, err)
		}
	}
	if len(notifier.calls) != 1 {
		t.Fatalf("expected exactly one delivery event, got %d", len(notifier.calls))
	}
	if notifier.calls[0].saleID != sale.SaleID.String() {
		t.Fatalf("unexpected sale id in event: %s", notifier.calls[0].saleID)
	}
}

func TestUpdateStatusNonDeliveryDoesNotFireEvent(t *testing.T) {
	sales := newFakeSaleRepo()
	sale := &models.Sale{SaleID: uuid.New(), POID: uuid.New(), Status: models.SaleStatusCreated}
	sales.sales[sale.SaleID] = sale
	notifier := &fakeNotifier{}
	svc := newSaleServiceForTest(sales, &fakePORepo{}, notifier)

	if _, err := svc.UpdateStatus(context.Background(), sale.SaleID, models.SaleStatusConfirmed); err != nil {
		t.Fatalf("transition: %v", err)
	}
	if len(notifier.calls) != 0 {
		t.Fatal("no event expected before DELIVERED")
	}
}

func dtosSaleRequest(poID uuid.UUID) dtos.SaleRequest {
	return dtos.SaleRequest{POID: poID}
}

// keep compiler honest that concrete fakes satisfy the interfaces.
var (
	_ repository.SaleRepository          = (*fakeSaleRepo)(nil)
	_ repository.PurchaseOrderRepository = (*fakePORepo)(nil)
)
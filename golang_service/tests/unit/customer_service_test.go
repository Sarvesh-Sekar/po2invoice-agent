// Package unit holds service-layer unit tests driven by an in-memory fake
// repository — no database, no network, fast and CI-safe.
package unit

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/internal/repository"
	"github.com/po-in/golang-service/internal/services"
)

// fakeCustomerRepo implements repository.CustomerRepository in memory.
type fakeCustomerRepo struct {
	byID   uuidToCustomer
	byCode map[string]*models.Customer
	rows   []models.Customer
}

type uuidToCustomer map[uuid.UUID]*models.Customer

func newFakeCustomerRepo() *fakeCustomerRepo {
	return &fakeCustomerRepo{byID: uuidToCustomer{}, byCode: map[string]*models.Customer{}}
}

func (f *fakeCustomerRepo) Create(_ context.Context, c *models.Customer) error {
	c.CustomerID = uuid.New()
	c.CreatedAt = time.Now()
	c.ModifiedAt = time.Now()
	f.byID[c.CustomerID] = c
	f.byCode[strings.ToLower(c.CustomerCode)] = c
	f.rows = append(f.rows, *c)
	return nil
}

func (f *fakeCustomerRepo) ByID(_ context.Context, id uuid.UUID) (*models.Customer, error) {
	if c, ok := f.byID[id]; ok {
		return c, nil
	}
	return nil, errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
}

func (f *fakeCustomerRepo) ByCustomerCode(_ context.Context, code string) (*models.Customer, error) {
	return f.byCode[strings.ToLower(code)], nil
}

func (f *fakeCustomerRepo) List(_ context.Context, filter repository.CustomerFilter) ([]models.Customer, int64, error) {
	search := strings.ToLower(filter.Search)
	var out []models.Customer
	for _, c := range f.rows {
		if search == "" || strings.Contains(strings.ToLower(c.Name), search) || strings.Contains(strings.ToLower(c.CustomerCode), search) {
			out = append(out, c)
		}
	}
	total := int64(len(out))

	lo := filter.Offset
	if lo > len(out) {
		lo = len(out)
	}
	hi := lo + filter.Limit
	if hi > len(out) {
		hi = len(out)
	}
	return append([]models.Customer{}, out[lo:hi]...), total, nil
}

func (f *fakeCustomerRepo) Update(_ context.Context, c *models.Customer) error {
	if _, ok := f.byID[c.CustomerID]; !ok {
		return errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
	}
	c.ModifiedAt = time.Now()
	f.byID[c.CustomerID] = c
	f.byCode[strings.ToLower(c.CustomerCode)] = c
	for i := range f.rows {
		if f.rows[i].CustomerID == c.CustomerID {
			f.rows[i] = *c
		}
	}
	return nil
}

func (f *fakeCustomerRepo) Delete(_ context.Context, id uuid.UUID) error {
	if _, ok := f.byID[id]; !ok {
		return errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "customer not found")
	}
	delete(f.byID, id)
	return nil
}

func TestCustomerCreateAndDuplicateCode(t *testing.T) {
	ctx := context.Background()
	svc := services.NewCustomerService(newFakeCustomerRepo())

	created, err := svc.Create(ctx, dtos.CustomerRequest{
		CustomerCode: "CUST-0001", Name: "Acme Corp",
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.Name != "Acme Corp" || created.CustomerCode != "CUST-0001" || created.CustomerID == uuid.Nil {
		t.Fatalf("unexpected customer: %+v", created)
	}
	if created.Status != models.CustomerStatusActive {
		t.Fatalf("expected default ACTIVE status, got %s", created.Status)
	}

	_, err = svc.Create(ctx, dtos.CustomerRequest{CustomerCode: "cust-0001", Name: "Acme 2"})
	if err == nil || errorcodes.HTTPStatus(err) != 409 {
		t.Fatalf("expected 409 duplicate-code conflict, got %v", err)
	}
}

func TestCustomerNotFoundAndUpdate(t *testing.T) {
	ctx := context.Background()
	svc := services.NewCustomerService(newFakeCustomerRepo())

	if _, err := svc.GetByID(ctx, uuid.New()); err == nil || errorcodes.HTTPStatus(err) != 404 {
		t.Fatalf("expected 404, got %v", err)
	}

	created, err := svc.Create(ctx, dtos.CustomerRequest{CustomerCode: "SHIP-001", Name: "Ship Inc"})
	if err != nil {
		t.Fatalf("create: %v", err)
	}

	id, err := uuid.Parse(created.CustomerID.String())
	if err != nil {
		t.Fatalf("parse id: %v", err)
	}
	name := "Ship Inc Ltd"
	updated, err := svc.Update(ctx, id, dtos.CustomerUpdateRequest{Name: &name})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if updated.Name != name {
		t.Fatalf("expected renamed customer, got %s", updated.Name)
	}

	if err := svc.Delete(ctx, id); err != nil {
		t.Fatalf("delete: %v", err)
	}
	if _, err := svc.GetByID(ctx, id); err == nil || errorcodes.HTTPStatus(err) != 404 {
		t.Fatalf("expected 404 after delete, got %v", err)
	}
}

func TestCustomerSearchAndPaging(t *testing.T) {
	ctx := context.Background()
	svc := services.NewCustomerService(newFakeCustomerRepo())

	for _, req := range []dtos.CustomerRequest{
		{CustomerCode: "ALPHA-1", Name: "Alpha Corp"},
		{CustomerCode: "BETA-1", Name: "Beta GmbH"},
		{CustomerCode: "GAMMA-1", Name: "Gamma LLC"},
	} {
		if _, err := svc.Create(ctx, req); err != nil {
			t.Fatalf("seed %s: %v", req.Name, err)
		}
	}

	list, total, err := svc.List(ctx, "gmbh", 10, 0)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if total != 1 || len(list) != 1 || list[0].Name != "Beta GmbH" {
		t.Fatalf("search: total=%d rows=%d %+v", total, len(list), list)
	}

	list, total, err = svc.List(ctx, "", 2, 0)
	if err != nil {
		t.Fatalf("page 1: %v", err)
	}
	if total != 3 || len(list) != 2 {
		t.Fatalf("page 1: total=%d rows=%d", total, len(list))
	}

	list, total, err = svc.List(ctx, "", 2, 2)
	if err != nil {
		t.Fatalf("page 2: %v", err)
	}
	if total != 3 || len(list) != 1 {
		t.Fatalf("page 2: total=%d rows=%d", total, len(list))
	}
}

func TestErrorCodeContract(t *testing.T) {
	nf := errorcodes.NotFound(errorcodes.CodeCustomerNotFound, "nope")
	if errorcodes.HTTPStatus(nf) != 404 {
		t.Fatalf("notfound status: %d", errorcodes.HTTPStatus(nf))
	}
	code, _ := errorcodes.ToResponseBody(nf)
	if code != string(errorcodes.CodeCustomerNotFound) {
		t.Fatalf("code: %s", code)
	}

	dup := errorcodes.Conflict(errorcodes.CodeCustomerExists, "dup")
	if errorcodes.HTTPStatus(dup) != 409 {
		t.Fatalf("conflict status: %d", errorcodes.HTTPStatus(dup))
	}
}
// Package integration exercises the full HTTP surface against a real
// PostgreSQL database and the shared schema. Tests are skipped when the
// database is unreachable (set DATABASE_URL to run).
package integration

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"go.uber.org/zap"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"

	"github.com/po-in/golang-service/internal/config"
	"github.com/po-in/golang-service/internal/googleauth"
	"github.com/po-in/golang-service/internal/models"
	"github.com/po-in/golang-service/pkg/database"
	"github.com/po-in/golang-service/pkg/server"
)

func setupTestEnv(t *testing.T) (dbURL string) {
	t.Helper()
	dbURL = os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://postgres:postgres@localhost:5433/poin?sslmode=disable"
	}
	return dbURL
}

func cfgFor(url string) *config.Config {
	cfg, _ := config.Load()
	cfg.DatabaseURL = url
	cfg.AppEnv = "test"
	cfg.JWTSecret = "change-me-32-chars-long-secret-placeholder"
	cfg.JWTIssuer = "po-in"
	cfg.FrontendRedirectURL = "http://localhost:5173"
	cfg.AccessTokenTTL = 15 * time.Minute
	cfg.RefreshTokenTTL = 720 * time.Hour
	return cfg
}

func startServer(t *testing.T) (*httptest.Server, *gorm.DB, *googleauth.TokenManager) {
	t.Helper()
	url := setupTestEnv(t)

	cfg := cfgFor(url)
	db, err := database.Open(cfg)
	if err != nil {
		t.Skipf("postgres unreachable, skipping integration: %v", err)
	}

	log := zap.NewNop()

	// AutoMigrate is additive; the canonical field_definitions needed by the
	// PO flow are seeded idempotently for the test harness.
	if err := database.AutoMigrate(db); err != nil {
		t.Fatalf("auto migrate: %v", err)
	}
	seedFieldDefinitions(t, db)

	tm, err := googleauth.NewTokenManager(cfg.JWTSecret, "po-in")
	if err != nil {
		t.Fatalf("token manager: %v", err)
	}

	gin.SetMode(gin.TestMode)
	router, err := server.NewRouter(cfg, log, db)
	if err != nil {
		t.Fatalf("router: %v", err)
	}
	srv := httptest.NewServer(router)

	t.Cleanup(func() {
		srv.Close()
		sqlDB, _ := db.DB()
		_ = sqlDB.Close()
	})
	return srv, db, tm
}

// seedFieldDefinitions inserts the canonical field catalogue used by the PO
// flow. It mirrors the idempotent seed owned by python_service (data
// field_definitions.yaml) so integration tests are self-contained.
func seedFieldDefinitions(t *testing.T, db *gorm.DB) {
	t.Helper()
	numberFields := map[string]bool{
		models.HeaderFieldTotalAmount:  true,
		models.LineItemFieldQuantity:   true,
		models.LineItemFieldUnitPrice:  true,
		models.LineItemFieldTotalPrice: true,
	}
	names := append(append([]string{}, models.CanonicalHeaderFieldNames...), models.CanonicalLineItemFieldNames...)
	defs := make([]models.FieldDefinition, 0, len(names))
	for _, name := range names {
		fieldType := "string"
		if numberFields[name] {
			fieldType = "number"
		}
		defs = append(defs, models.FieldDefinition{FieldName: name, FieldType: fieldType})
	}
	if err := db.Clauses(clause.OnConflict{DoNothing: true}).Create(&defs).Error; err != nil {
		t.Fatalf("seed field definitions: %v", err)
	}
}

func newTestUser(t *testing.T, db *gorm.DB, tm *googleauth.TokenManager) (userID string, token string) {
	t.Helper()
	u := models.User{Name: "Integration User", Email: "it@" + uuid.NewString()[:8] + ".example.com", Role: "USER", IsActive: true}
	if err := db.Create(&u).Error; err != nil {
		t.Fatalf("create user: %v", err)
	}
	tok, _, err := tm.IssueAccessToken(googleauth.Claims{
		UserID: u.ID, Email: u.Email, Name: u.Name, Role: u.Role,
	}, 15*time.Minute)
	if err != nil {
		t.Fatalf("mint token: %v", err)
	}
	return u.ID.String(), tok
}

func parseJSON(t *testing.T, body []byte, out any) {
	t.Helper()
	if err := json.Unmarshal(body, out); err != nil {
		t.Fatalf("parse json: %v (%s)", err, string(body))
	}
}

func req(t *testing.T, srv *httptest.Server, method, path, token string, body any) (*http.Response, []byte) {
	t.Helper()
	var reader *bytes.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		reader = bytes.NewReader(b)
	} else {
		reader = bytes.NewReader(nil)
	}
	req, err := http.NewRequest(method, srv.URL+path, reader)
	if err != nil {
		t.Fatalf("build request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("do request %s %s: %v", method, path, err)
	}
	defer resp.Body.Close()
	buf := new(bytes.Buffer)
	_, _ = buf.ReadFrom(resp.Body)
	return resp, buf.Bytes()
}

func TestHappyPathAndAuth(t *testing.T) {
	srv, db, tm := startServer(t)
	userID, token := newTestUser(t, db, tm)
	t.Logf("user=%s", userID)

	t.Run("unauthenticated is rejected", func(t *testing.T) {
		resp, body := req(t, srv, http.MethodGet, "/api/v1/customers", "", nil)
		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("expected 401, got %d (%s)", resp.StatusCode, body)
		}
	})

	t.Run("me resolves the signed-in user", func(t *testing.T) {
		resp, body := req(t, srv, http.MethodGet, "/api/v1/auth/me", token, nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d (%s)", resp.StatusCode, body)
		}
		var me struct {
			UserID string `json:"user_id"`
			Email  string `json:"email"`
		}
		parseJSON(t, body, &me)
		if me.UserID == "" || me.Email == "" {
			t.Fatalf("me incomplete: %s", body)
		}
	})

	t.Run("customer lifecycle", func(t *testing.T) {
		resp, body := req(t, srv, http.MethodPost, "/api/v1/customers", token, map[string]string{
			"customer_code": "CUST-" + uuid.NewString()[:8], "name": "Acme Corp",
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create customer: %d (%s)", resp.StatusCode, body)
		}
		var c struct {
			CustomerID string `json:"customer_id"`
		}
		parseJSON(t, body, &c)
		if c.CustomerID == "" {
			t.Fatalf("no customer id: %s", body)
		}

		resp, body = req(t, srv, http.MethodGet, "/api/v1/customers", token, nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("list customers: %d (%s)", resp.StatusCode, body)
		}
		var page struct {
			Data []map[string]any `json:"data"`
			Meta struct {
				Total float64 `json:"total"`
			} `json:"meta"`
		}
		parseJSON(t, body, &page)
		if page.Meta.Total < 1 || len(page.Data) < 1 {
			t.Fatalf("expected customers in list: %s", body)
		}
	})

	t.Run("product lifecycle", func(t *testing.T) {
		resp, body := req(t, srv, http.MethodPost, "/api/v1/products", token, map[string]any{
			"name": "Widget", "sku": "SKU-" + uuid.NewString()[:8], "catalog_price": 99.50,
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create product: %d (%s)", resp.StatusCode, body)
		}
		var p struct {
			ProductID string `json:"product_id"`
		}
		parseJSON(t, body, &p)
		if p.ProductID == "" {
			t.Fatalf("no product id: %s", body)
		}
	})

	t.Run("dashboard summary works", func(t *testing.T) {
		resp, body := req(t, srv, http.MethodGet, "/api/v1/dashboard/summary", token, nil)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("expected 200, got %d (%s)", resp.StatusCode, body)
		}
		var s struct {
			TotalCustomers int `json:"total_customers"`
		}
		parseJSON(t, body, &s)
		if s.TotalCustomers < 1 {
			t.Fatalf("expected customers counted: %s", body)
		}
	})
}

func TestPurchaseOrderToSaleFlow(t *testing.T) {
	srv, db, tm := startServer(t)
	_, token := newTestUser(t, db, tm)

	resp, body := req(t, srv, http.MethodPost, "/api/v1/customers", token, map[string]string{
		"customer_code": "CUST-" + uuid.NewString()[:8], "name": "Buyer Inc",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create customer: %d (%s)", resp.StatusCode, body)
	}
	var c struct {
		CustomerID string `json:"customer_id"`
	}
	parseJSON(t, body, &c)

	sku := "GDG-" + uuid.NewString()[:8]
	resp, body = req(t, srv, http.MethodPost, "/api/v1/products", token, map[string]any{
		"name": "Gadget", "sku": sku, "catalog_price": 50,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create product: %d (%s)", resp.StatusCode, body)
	}
	var p struct {
		ProductID string `json:"product_id"`
	}
	parseJSON(t, body, &p)

	poNumber := "PO-" + uuid.NewString()[:8]
	resp, body = req(t, srv, http.MethodPost, "/api/v1/purchase-orders", token, map[string]any{
		"customer_id": c.CustomerID,
		"header_fields": []map[string]string{
			{"field_name": "po_number", "field_value": poNumber},
			{"field_name": "customer", "field_value": "Buyer Inc"},
			{"field_name": "total_amount", "field_value": "100"},
		},
		"line_items": []map[string]any{
			{
				"product_id": p.ProductID,
				"fields": []map[string]string{
					{"field_name": "sku", "field_value": sku},
					{"field_name": "quantity", "field_value": "2"},
					{"field_name": "unit_price", "field_value": "50"},
					{"field_name": "total_price", "field_value": "100"},
				},
			},
		},
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create po: %d (%s)", resp.StatusCode, body)
	}
	var po struct {
		POID         string `json:"po_id"`
		HeaderFields []struct {
			FieldName  string `json:"field_name"`
			FieldValue string `json:"field_value"`
		} `json:"header_fields"`
		LineItems []struct {
			POLineItemID string `json:"po_line_item_id"`
			ProductID    string `json:"product_id"`
		} `json:"line_items"`
	}
	parseJSON(t, body, &po)
	if po.POID == "" || len(po.LineItems) != 1 || po.LineItems[0].ProductID != p.ProductID {
		t.Fatalf("unexpected po: %s", body)
	}
	var gotPONumber string
	for _, hf := range po.HeaderFields {
		if hf.FieldName == "po_number" {
			gotPONumber = hf.FieldValue
		}
	}
	if gotPONumber != poNumber {
		t.Fatalf("expected po_number %q, got %q (%s)", poNumber, gotPONumber, body)
	}

	// PO list projection surfaces derived fields (po_number / total_amount).
	resp, body = req(t, srv, http.MethodGet, "/api/v1/purchase-orders", token, nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("list po: %d (%s)", resp.StatusCode, body)
	}
	var page struct {
		Data []struct {
			POID        string  `json:"po_id"`
			PONumber    string  `json:"po_number"`
			TotalAmount float64 `json:"total_amount"`
		} `json:"data"`
	}
	parseJSON(t, body, &page)
	found := false
	for _, item := range page.Data {
		if item.POID == po.POID {
			found = true
			if item.PONumber != poNumber || item.TotalAmount != 100 {
				t.Fatalf("unexpected list projection: %+v", item)
			}
		}
	}
	if !found {
		t.Fatalf("po %s missing from list: %s", po.POID, body)
	}

	// Sales derive directly from the PO (no approval step).
	resp, body = req(t, srv, http.MethodPost, "/api/v1/sales", token, map[string]string{"po_id": po.POID})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create sale: %d (%s)", resp.StatusCode, body)
	}
	var sale struct {
		SaleID string `json:"sale_id"`
		Status string `json:"status"`
	}
	parseJSON(t, body, &sale)
	if sale.Status != models.SaleStatusCreated {
		t.Fatalf("unexpected sale: %s", body)
	}

	// Duplicate sale for the same PO is rejected.
	resp, body = req(t, srv, http.MethodPost, "/api/v1/sales", token, map[string]string{"po_id": po.POID})
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("expected 409 duplicate, got %d (%s)", resp.StatusCode, body)
	}

	// Walk statuses; DELIVERED attempts the Python event (not running here,
	// the error is swallowed), but the status still persists.
	for _, st := range []string{"CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"} {
		resp, body = req(t, srv, http.MethodPatch, "/api/v1/sales/"+sale.SaleID+"/status", token, map[string]string{"status": st})
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("transition to %s: %d (%s)", st, resp.StatusCode, body)
		}
	}

	resp, body = req(t, srv, http.MethodGet, "/api/v1/sales/"+sale.SaleID, token, nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("get sale: %d (%s)", resp.StatusCode, body)
	}
	var got struct {
		Status string `json:"status"`
	}
	parseJSON(t, body, &got)
	if got.Status != models.SaleStatusDelivered {
		t.Fatalf("expected DELIVERED, got %s", got.Status)
	}
}

func TestRefreshTokenEndpoint(t *testing.T) {
	srv, db, tm := startServer(t)
	user := models.User{Name: "R", Email: "r@" + uuid.NewString()[:8] + ".com", Role: "USER", IsActive: true}
	if err := db.Create(&user).Error; err != nil {
		t.Fatalf("create user: %v", err)
	}
	rt, _, err := tm.IssueRefreshToken(googleauth.Claims{UserID: user.ID, Email: user.Email, Name: user.Name, Role: user.Role}, 720*time.Hour)
	if err != nil {
		t.Fatalf("mint refresh: %v", err)
	}

	resp, body := req(t, srv, http.MethodPost, "/api/v1/auth/refresh", "", map[string]string{"refresh_token": rt})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("refresh: %d (%s)", resp.StatusCode, body)
	}
	var out struct {
		AccessToken string `json:"access_token"`
		TokenType   string `json:"token_type"`
	}
	parseJSON(t, body, &out)
	if out.AccessToken == "" || out.TokenType != "Bearer" {
		t.Fatalf("unexpected refresh response: %s", body)
	}
}

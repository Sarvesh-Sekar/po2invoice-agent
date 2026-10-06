// Package server wires the Gin router, middleware stack, and all
// handler/service/repository factories into a runnable HTTP server.
package server

import (
	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
	"gorm.io/gorm"

	"github.com/po-in/golang-service/internal/agentclient"
	"github.com/po-in/golang-service/internal/config"
	"github.com/po-in/golang-service/internal/googleauth"
	"github.com/po-in/golang-service/internal/handlers"
	"github.com/po-in/golang-service/internal/middleware"
	"github.com/po-in/golang-service/internal/repository"
	"github.com/po-in/golang-service/internal/services"
)

// Run boots the Gin server on cfg.ServerPort. It is expected to be called
// after database.Open and database.AutoMigrate have run.
func Run(cfg *config.Config, log *zap.Logger, db *gorm.DB) error {
	r, err := NewRouter(cfg, log, db)
	if err != nil {
		return err
	}
	return r.Run(":" + cfg.ServerPort)
}

// NewRouter wires middleware, handlers, services, and repositories into a Gin
// engine. It is used by Run and by integration tests (httptest).
func NewRouter(cfg *config.Config, log *zap.Logger, db *gorm.DB) (*gin.Engine, error) {
	if cfg.AppEnv == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// --- googleauth --------------------------------------------------------
	tm, err := googleauth.NewTokenManager(cfg.JWTSecret, cfg.JWTIssuer)
	if err != nil {
		return nil, err
	}
	authn := googleauth.NewGoogleAuthenticator(
		cfg.GoogleOAuthCfg, cfg.GoogleAuthURL, cfg.GoogleTokenURL, cfg.GoogleUserURL,
	)

	// --- repositories -------------------------------------------------------
	userRepo := repository.NewUserRepository(db)
	customerRepo := repository.NewCustomerRepository(db)
	productRepo := repository.NewProductRepository(db)
	poRepo := repository.NewPurchaseOrderRepository(db)
	saleRepo := repository.NewSaleRepository(db)
	invoiceRepo := repository.NewInvoiceRepository(db)
	dashRepo := repository.NewDashboardRepository(db)

	// --- services -----------------------------------------------------------
	authSvc := services.NewAuthService(tm, authn, userRepo, cfg.AccessTokenTTL, cfg.RefreshTokenTTL)
	customerSvc := services.NewCustomerService(customerRepo)
	productSvc := services.NewProductService(productRepo)
	poSvc := services.NewPurchaseOrderService(poRepo, customerRepo, productRepo)
	saleSvc := services.NewSaleService(saleRepo, poRepo, agentclient.NewAgentEventClient(cfg.PythonServiceURL, cfg.InternalAPIKey))
	invoiceSvc := services.NewInvoiceService(invoiceRepo)
	dashSvc := services.NewDashboardService(dashRepo)

	// --- gin ---------------------------------------------------------------
	r := gin.New()
	r.Use(middleware.Recovery(log))
	r.Use(middleware.RequestID())
	r.Use(middleware.Logging(log))

	v1 := r.Group("/api/v1")

	// Public (no auth)
	authH := handlers.NewAuthHandler(authSvc, *cfg, log, middleware.Auth(tm, log))
	authH.Register(v1.Group("/auth"))

	// Protected
	protected := v1.Group("")
	protected.Use(middleware.Auth(tm, log))
	handlers.NewCustomerHandler(customerSvc).Register(protected.Group("/customers"))
	handlers.NewProductHandler(productSvc).Register(protected.Group("/products"))
	handlers.NewPurchaseOrderHandler(poSvc).Register(protected.Group("/purchase-orders"))
	handlers.NewSaleHandler(saleSvc).Register(protected.Group("/sales"))
	handlers.NewInvoiceHandler(invoiceSvc).Register(protected.Group("/invoices"))
	handlers.NewDashboardHandler(dashSvc).Register(protected.Group("/dashboard"))

	return r, nil
}

package services

import (
	"context"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/repository"
)

// DashboardService (§ dashboard API).
type DashboardService interface {
	Summary(ctx context.Context) (*dtos.DashboardSummary, error)
	RecentSales(ctx context.Context, limit int) ([]dtos.RecentSaleItem, error)
	RecentOrders(ctx context.Context, limit int) ([]dtos.RecentOrderItem, error)
	RecentInvoices(ctx context.Context, limit int) ([]dtos.RecentInvoiceItem, error)
}

type dashboardService struct {
	repo repository.DashboardRepository
}

func NewDashboardService(repo repository.DashboardRepository) DashboardService {
	return &dashboardService{repo: repo}
}

func (s *dashboardService) Summary(ctx context.Context) (*dtos.DashboardSummary, error) {
	return s.repo.Summary(ctx)
}

func (s *dashboardService) RecentSales(ctx context.Context, limit int) ([]dtos.RecentSaleItem, error) {
	return s.repo.RecentSales(ctx, limit)
}

func (s *dashboardService) RecentOrders(ctx context.Context, limit int) ([]dtos.RecentOrderItem, error) {
	return s.repo.RecentOrders(ctx, limit)
}

func (s *dashboardService) RecentInvoices(ctx context.Context, limit int) ([]dtos.RecentInvoiceItem, error) {
	return s.repo.RecentInvoices(ctx, limit)
}

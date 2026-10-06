package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/po-in/golang-service/internal/services"
)

type DashboardHandler struct {
	svc services.DashboardService
}

func NewDashboardHandler(svc services.DashboardService) *DashboardHandler {
	return &DashboardHandler{svc: svc}
}

func (h *DashboardHandler) Register(r *gin.RouterGroup) {
	r.GET("/summary", h.Summary)
	r.GET("/recent-sales", h.RecentSales)
	r.GET("/recent-orders", h.RecentOrders)
	r.GET("/recent-invoices", h.RecentInvoices)
}

func (h *DashboardHandler) Summary(c *gin.Context) {
	out, err := h.svc.Summary(c.Request.Context())
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func recentLimit(c *gin.Context) int {
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "5"))
	if limit <= 0 || limit > 50 {
		return 5
	}
	return limit
}

func (h *DashboardHandler) RecentSales(c *gin.Context) {
	rows, err := h.svc.RecentSales(c.Request.Context(), recentLimit(c))
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, rows)
}

func (h *DashboardHandler) RecentOrders(c *gin.Context) {
	rows, err := h.svc.RecentOrders(c.Request.Context(), recentLimit(c))
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, rows)
}

func (h *DashboardHandler) RecentInvoices(c *gin.Context) {
	rows, err := h.svc.RecentInvoices(c.Request.Context(), recentLimit(c))
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, rows)
}

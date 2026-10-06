package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/services"
)

type SaleHandler struct {
	svc services.SaleService
}

func NewSaleHandler(svc services.SaleService) *SaleHandler {
	return &SaleHandler{svc: svc}
}

func (h *SaleHandler) Register(r *gin.RouterGroup) {
	r.GET("", h.List)
	r.POST("", h.Create)
	r.GET("/:id", h.GetByID)
	r.GET("/:id/history", h.History)
	r.PATCH("/:id/status", h.UpdateStatus)
}

func (h *SaleHandler) List(c *gin.Context) {
	page, pageSize := pageParams(c)
	items, total, err := h.svc.List(
		c.Request.Context(),
		c.Query("status"), c.Query("customer_id"),
		pageSize, offsetFor(page, pageSize),
	)
	if err != nil {
		writeError(c, err)
		return
	}
	paginated(c, items, total)
}

func (h *SaleHandler) Create(c *gin.Context) {
	var req dtos.SaleRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid sale payload: "+err.Error()))
		return
	}
	out, err := h.svc.Create(c.Request.Context(), req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusCreated, out)
}

func (h *SaleHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid sale id"))
		return
	}
	out, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *SaleHandler) UpdateStatus(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid sale id"))
		return
	}
	var req dtos.SaleStatusUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid status payload: "+err.Error()))
		return
	}
	out, err := h.svc.UpdateStatus(c.Request.Context(), id, req.Status)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

// History is a placeholder until a sale status-history table is introduced.
func (h *SaleHandler) History(c *gin.Context) {
	c.JSON(http.StatusOK, []any{})
}

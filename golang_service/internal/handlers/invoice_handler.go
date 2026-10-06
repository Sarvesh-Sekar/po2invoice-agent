package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/services"
)

type InvoiceHandler struct {
	svc services.InvoiceService
}

func NewInvoiceHandler(svc services.InvoiceService) *InvoiceHandler {
	return &InvoiceHandler{svc: svc}
}

func (h *InvoiceHandler) Register(r *gin.RouterGroup) {
	r.GET("", h.List)
	r.GET("/:id", h.GetByID)
	r.GET("/:id/download", h.Download)
}

func (h *InvoiceHandler) List(c *gin.Context) {
	page, pageSize := pageParams(c)
	items, total, err := h.svc.List(
		c.Request.Context(),
		c.Query("status"), c.Query("po_id"),
		c.Query("customer_id"), c.Query("search"),
		pageSize, offsetFor(page, pageSize),
	)
	if err != nil {
		writeError(c, err)
		return
	}
	paginated(c, items, total)
}

func (h *InvoiceHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid invoice id"))
		return
	}
	out, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *InvoiceHandler) Download(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid invoice id"))
		return
	}
	inv, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	if inv.S3URL == "" {
		writeError(c, errorcodes.NotFound(errorcodes.CodeInvoiceNotFound, "invoice file not available yet"))
		return
	}
	c.JSON(http.StatusOK, dtos.InvoiceDownloadResponse{URL: inv.S3URL})
}

package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/services"
)

type PurchaseOrderHandler struct {
	svc services.PurchaseOrderService
}

func NewPurchaseOrderHandler(svc services.PurchaseOrderService) *PurchaseOrderHandler {
	return &PurchaseOrderHandler{svc: svc}
}

func (h *PurchaseOrderHandler) Register(r *gin.RouterGroup) {
	r.GET("", h.List)
	r.POST("", h.Create)
	r.GET("/:id", h.GetByID)
	r.PATCH("/:id", h.Update)
	r.GET("/:id/history", h.History)
	r.GET("/:id/line-items", h.LineItems)
	r.PATCH("/:id/line-items/:lineItemId", h.UpdateLineItem)
}

func (h *PurchaseOrderHandler) List(c *gin.Context) {
	page, pageSize := pageParams(c)
	items, total, err := h.svc.List(
		c.Request.Context(),
		c.Query("customer_id"), c.Query("search"),
		pageSize, offsetFor(page, pageSize),
	)
	if err != nil {
		writeError(c, err)
		return
	}
	paginated(c, items, total)
}

func (h *PurchaseOrderHandler) Create(c *gin.Context) {
	var req dtos.PurchaseOrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order payload: "+err.Error()))
		return
	}
	out, err := h.svc.Create(c.Request.Context(), req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusCreated, out)
}

func (h *PurchaseOrderHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order id"))
		return
	}
	out, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *PurchaseOrderHandler) Update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order id"))
		return
	}
	var req dtos.PurchaseOrderUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order payload: "+err.Error()))
		return
	}
	out, err := h.svc.Update(c.Request.Context(), id, req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

// History is a placeholder until a PO status-history table is introduced.
func (h *PurchaseOrderHandler) History(c *gin.Context) {
	c.JSON(http.StatusOK, []any{})
}

func (h *PurchaseOrderHandler) LineItems(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order id"))
		return
	}
	po, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, po.LineItems)
}

func (h *PurchaseOrderHandler) UpdateLineItem(c *gin.Context) {
	poID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid purchase order id"))
		return
	}
	lineItemID, err := uuid.Parse(c.Param("lineItemId"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid line item id"))
		return
	}
	var req dtos.POLineItemUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid line item payload: "+err.Error()))
		return
	}
	out, err := h.svc.UpdateLineItem(c.Request.Context(), poID, lineItemID, req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}
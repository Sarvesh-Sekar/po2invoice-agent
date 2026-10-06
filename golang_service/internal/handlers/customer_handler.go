package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/services"
)

type CustomerHandler struct {
	svc services.CustomerService
}

func NewCustomerHandler(svc services.CustomerService) *CustomerHandler {
	return &CustomerHandler{svc: svc}
}

func (h *CustomerHandler) Register(r *gin.RouterGroup) {
	r.GET("", h.List)
	r.POST("", h.Create)
	r.GET("/:id", h.GetByID)
	r.PATCH("/:id", h.Update)
	r.DELETE("/:id", h.Delete)
}

func (h *CustomerHandler) List(c *gin.Context) {
	page, pageSize := pageParams(c)
	items, total, err := h.svc.List(c.Request.Context(), c.Query("search"), pageSize, offsetFor(page, pageSize))
	if err != nil {
		writeError(c, err)
		return
	}
	paginated(c, items, total)
}

func (h *CustomerHandler) Create(c *gin.Context) {
	var req dtos.CustomerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid customer payload: "+err.Error()))
		return
	}
	out, err := h.svc.Create(c.Request.Context(), req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusCreated, out)
}

func (h *CustomerHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid customer id"))
		return
	}
	out, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *CustomerHandler) Update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid customer id"))
		return
	}
	var req dtos.CustomerUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid customer payload: "+err.Error()))
		return
	}
	out, err := h.svc.Update(c.Request.Context(), id, req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *CustomerHandler) Delete(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid customer id"))
		return
	}
	if err := h.svc.Delete(c.Request.Context(), id); err != nil {
		writeError(c, err)
		return
	}
	c.Status(http.StatusNoContent)
}

package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"

	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/errorcodes"
	"github.com/po-in/golang-service/internal/services"
)

type ProductHandler struct {
	svc services.ProductService
}

func NewProductHandler(svc services.ProductService) *ProductHandler {
	return &ProductHandler{svc: svc}
}

func (h *ProductHandler) Register(r *gin.RouterGroup) {
	r.GET("", h.List)
	r.POST("", h.Create)
	r.GET("/:id", h.GetByID)
	r.PATCH("/:id", h.Update)
}

func (h *ProductHandler) List(c *gin.Context) {
	page, pageSize := pageParams(c)
	items, total, err := h.svc.List(c.Request.Context(), c.Query("search"), pageSize, offsetFor(page, pageSize))
	if err != nil {
		writeError(c, err)
		return
	}
	paginated(c, items, total)
}

func (h *ProductHandler) Create(c *gin.Context) {
	var req dtos.ProductRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid product payload: "+err.Error()))
		return
	}
	out, err := h.svc.Create(c.Request.Context(), req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusCreated, out)
}

func (h *ProductHandler) GetByID(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid product id"))
		return
	}
	out, err := h.svc.GetByID(c.Request.Context(), id)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

func (h *ProductHandler) Update(c *gin.Context) {
	id, err := uuid.Parse(c.Param("id"))
	if err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid product id"))
		return
	}
	var req dtos.ProductUpdateRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		writeError(c, errorcodes.InvalidRequest("invalid product payload: "+err.Error()))
		return
	}
	out, err := h.svc.Update(c.Request.Context(), id, req)
	if err != nil {
		writeError(c, err)
		return
	}
	c.JSON(http.StatusOK, out)
}

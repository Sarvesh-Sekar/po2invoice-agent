package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"github.com/po-in/golang-service/internal/errorcodes"
)

const (
	defaultPageSize = 20
	maxPageSize     = 100
)

// writeError renders the stable {code, message} body for any error.
func writeError(c *gin.Context, err error) {
	status := errorcodes.HTTPStatus(err)
	code, msg := errorcodes.ToResponseBody(err)
	if code == "" {
		code = string(errorcodes.CodeInternalError)
	}
	if msg == "" {
		msg = "internal server error"
	}
	c.AbortWithStatusJSON(status, gin.H{"code": code, "message": msg})
}

func pageParams(c *gin.Context) (page, pageSize int) {
	page, _ = strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ = strconv.Atoi(c.DefaultQuery("per_page", strconv.Itoa(defaultPageSize)))
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = defaultPageSize
	}
	if pageSize > maxPageSize {
		pageSize = maxPageSize
	}
	return page, pageSize
}

func offsetFor(page, pageSize int) int { return (page - 1) * pageSize }

func paginated(c *gin.Context, items any, total int64) {
	page, pageSize := pageParams(c)
	totalPages := (int(total) + pageSize - 1) / pageSize
	if totalPages < 1 {
		totalPages = 1
	}
	c.JSON(http.StatusOK, gin.H{
		"data": items,
		"meta": gin.H{
			"page":        page,
			"per_page":    pageSize,
			"total":       total,
			"total_pages": totalPages,
		},
	})
}

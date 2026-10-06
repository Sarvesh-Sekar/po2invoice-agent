package services

import (
	"github.com/po-in/golang-service/internal/dtos"
	"github.com/po-in/golang-service/internal/models"
)

func toInvoiceResponse(inv *models.Invoice) *dtos.InvoiceResponse {
	return &dtos.InvoiceResponse{
		InvoiceID:     inv.InvoiceID,
		POID:          inv.POID,
		InvoiceNumber: inv.InvoiceNumber,
		Status:        inv.Status,
		GSTIRN:        inv.GSTIRN,
		S3URL:         inv.S3URL,
		CreatedAt:     inv.CreatedAt,
		ModifiedAt:    inv.ModifiedAt,
	}
}
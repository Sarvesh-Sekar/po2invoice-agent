package dtos

import (
	"time"

	"github.com/google/uuid"
)

// Invoice DTOs (§ invoices API). Invoices are generated from a purchase order
// and persisted by the Python service; Go exposes read/download + dashboard
// aggregation only.

type InvoiceResponse struct {
	InvoiceID     uuid.UUID `json:"invoice_id"`
	POID          uuid.UUID `json:"po_id"`
	InvoiceNumber string    `json:"invoice_number"`
	Status        string    `json:"status"`
	GSTIRN        string    `json:"gst_irn"`
	S3URL         string    `json:"s3_url"`
	CreatedAt     time.Time `json:"created_at"`
	ModifiedAt    time.Time `json:"modified_at"`
}

type InvoiceDownloadResponse struct {
	URL string `json:"url"`
}
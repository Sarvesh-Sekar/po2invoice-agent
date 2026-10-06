package dtos

import "time"

// Dashboard DTOs (§ dashboard API).

type DashboardSummary struct {
	TotalCustomers  int     `json:"total_customers"`
	TotalProducts   int     `json:"total_products"`
	TotalPOs        int     `json:"total_pos"`
	TotalSales      int     `json:"total_sales"`
	TotalRevenue    float64 `json:"total_revenue"`
	PendingInvoices int     `json:"pending_invoices"`
}

type RecentSaleItem struct {
	SaleID    string    `json:"sale_id"`
	PONumber  string    `json:"po_number"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
}

type RecentOrderItem struct {
	POID      string    `json:"po_id"`
	PONumber  string    `json:"po_number"`
	Customer  string    `json:"customer"`
	CreatedAt time.Time `json:"created_at"`
}

type RecentInvoiceItem struct {
	InvoiceID     string    `json:"invoice_id"`
	InvoiceNumber string    `json:"invoice_number"`
	Status        string    `json:"status"`
	CreatedAt     time.Time `json:"created_at"`
}
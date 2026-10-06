import type {
  InvoiceFilters,
  PurchaseOrderFilters,
  SaleFilters,
} from "@/types/api";

export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  dashboard: {
    summary: ["dashboard", "summary"] as const,
    recentOrders: ["dashboard", "recent-orders"] as const,
    recentInvoices: ["dashboard", "recent-invoices"] as const,
    recentSales: ["dashboard", "recent-sales"] as const,
  },
  customers: {
    all: ["customers"] as const,
    list: (search?: string) => ["customers", "list", search ?? ""] as const,
    detail: (id: string) => ["customers", "detail", id] as const,
    history: (id: string) => ["customers", "history", id] as const,
  },
  products: {
    all: ["products"] as const,
    list: (search?: string) => ["products", "list", search ?? ""] as const,
    detail: (id: string) => ["products", "detail", id] as const,
  },
  purchaseOrders: {
    all: ["purchase-orders"] as const,
    list: (filters: PurchaseOrderFilters) =>
      ["purchase-orders", "list", filters] as const,
    detail: (id: string) => ["purchase-orders", "detail", id] as const,
    lineItems: (id: string) => ["purchase-orders", "line-items", id] as const,
    history: (id: string) => ["purchase-orders", "history", id] as const,
  },
  sales: {
    all: ["sales"] as const,
    list: (filters: SaleFilters) => ["sales", "list", filters] as const,
    detail: (id: string) => ["sales", "detail", id] as const,
    history: (id: string) => ["sales", "history", id] as const,
  },
  invoices: {
    all: ["invoices"] as const,
    list: (filters: InvoiceFilters) => ["invoices", "list", filters] as const,
    detail: (id: string) => ["invoices", "detail", id] as const,
    history: (id: string) => ["invoices", "history", id] as const,
  },
  agentRuns: {
    all: ["agent-runs"] as const,
    detail: (runId: string) => ["agent-runs", "detail", runId] as const,
  },
} as const;
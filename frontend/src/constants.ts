export const API_BASE_URLS = {
  GO: import.meta.env.VITE_GO_API_BASE_URL ?? "http://localhost:8080",
  PYTHON: import.meta.env.VITE_PYTHON_API_BASE_URL ?? "http://localhost:8000",
} as const;

export const API_PREFIX = import.meta.env.VITE_API_PREFIX ?? "/api/v1";

export const ROUTES = {
  LOGIN: "/login",
  AUTH_CALLBACK: "/auth/callback",
  DASHBOARD: "/dashboard",
  PURCHASE_ORDERS: "/purchase-orders",
  PURCHASE_ORDER_UPLOAD: "/purchase-orders/upload",
  PURCHASE_ORDER_REVIEW: "/purchase-orders/:runId/review",
  SALES: "/sales",
  INVOICES: "/invoices",
  CUSTOMERS: "/customers",
  PRODUCTS: "/products",
  AI_PROCESSING: "/ai-processing",
} as const;

export const PO_FILE_LIMIT_MB = 20;
export const PO_ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".xls"] as const;

export const SALE_STATUSES = [
  "CREATED",
  "CONFIRMED",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
] as const;

export const INVOICE_STATUS = {
  GENERATED: "GENERATED",
  SENT: "SENT",
} as const;

export const AGENT_RUN_STATUSES = [
  "QUEUED",
  "RUNNING",
  "WAITING_FOR_HUMAN",
  "COMPLETED",
  "FAILED",
] as const;

export const SALE_DELIVERY_STATUSES = ["PENDING", "DELIVERED", "RETRY_DELIVERY"] as const;

export const GST_STATUSES = ["PROCESSING", "REGISTERED"] as const;

export const CURRENCY = "₹" as const;

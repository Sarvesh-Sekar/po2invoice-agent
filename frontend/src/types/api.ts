import type {
  AgentRunStatus,
  AgentWorkflow,
  DeliveryStatus,
  GSTStatus,
  HITLDecision,
  InvoiceStatus,
  PaginatedResponse,
  PurchaseOrderStatus,
  SaleStatus,
  UUID,
} from "@/types/common";

export interface User {
  id: UUID;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type?: string;
}

export interface AuthResponse extends AuthTokens {
  user?: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

/* --------------------------------- Customers ------------------------------ */

export interface Customer {
  customer_id: UUID;
  name: string;
  email: string;
  phone: string;
  address: string;
  gst_no: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreate {
  name: string;
  email: string;
  phone?: string;
  address?: string;
  gst_no?: string;
}

export interface CustomerUpdate {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  gst_no?: string;
}

export interface CustomerHistoryEntry {
  type: string;
  ref_id: UUID;
  po_number?: string;
  total_amount?: number;
  status: string;
  created_at: string;
  [key: string]: unknown;
}

export interface CustomerDetail extends Customer {
  total_orders: number;
  lifetime_value: number;
  payment_score?: number;
  order_history?: CustomerHistoryEntry[];
  contacts?: Array<{ name: string; phone: string; email: string }>;
  shipping_addresses?: Array<{ label: string; value: string }>;
}

/* --------------------------------- Products ------------------------------ */

export interface Product {
  product_id: UUID;
  name: string;
  sku: string;
  price: number;
  stock: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  name: string;
  sku: string;
  price?: number;
  stock?: number;
}

export interface ProductUpdate {
  name?: string;
  sku?: string;
  price?: number;
  stock?: number;
}

/* ------------------------------ Purchase orders -------------------------- */

export interface POLineItem {
  po_line_item_id: UUID;
  product_id: UUID;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface PurchaseOrder {
  po_id: UUID;
  customer_id: UUID;
  po_number: string;
  status: PurchaseOrderStatus;
  ship_to: string;
  address_1: string;
  address_2: string;
  city: string;
  state: string;
  country: string;
  zip: string;
  total_amount: number;
  source_file_url: string;
  line_items: POLineItem[];
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderListItem {
  po_id: UUID;
  po_number: string;
  customer_id: UUID;
  customer_name?: string;
  status?: PurchaseOrderStatus;
  total_amount: number;
  source_file_url: string;
  created_at: string;
  updated_at: string;
  ai_confidence?: number;
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  customer?: Customer;
  ai_confidence?: number;
  verification?: VerificationPayload;
}

export interface PurchaseOrderUpdate {
  ship_to?: string;
  address_1?: string;
  address_2?: string;
  city?: string;
  state?: string;
  country?: string;
  zip?: string;
}

export interface POLineItemUpdate {
  quantity?: number;
  unit_price?: number;
}

export interface PurchaseOrderFilters {
  search?: string;
  status?: PurchaseOrderStatus;
  date_from?: string;
  date_to?: string;
  min_confidence?: number;
  page?: number;
  per_page?: number;
}

export type PurchaseOrderListResponse = PaginatedResponse<PurchaseOrderListItem>;

export interface PurchaseOrderHistoryEntry {
  id?: string;
  action: string;
  actor?: string;
  note?: string;
  created_at: string;
  [key: string]: unknown;
}

/* ---------------------------------- Sales -------------------------------- */

export interface Sale {
  sale_id: UUID;
  po_id: UUID;
  status: SaleStatus;
  total_amount: number;
  created_at: string;
  updated_at: string;
}

export interface SaleListItem extends Sale {
  po_number?: string;
  customer_name?: string;
}

export interface SaleRequest {
  po_id: UUID;
}

export interface SaleStatusUpdate {
  status: SaleStatus;
}

export interface SaleFilters {
  search?: string;
  status?: SaleStatus;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}

export type SaleListResponse = PaginatedResponse<SaleListItem>;

export interface SaleHistoryEntry {
  id?: string;
  from_status?: string;
  to_status: string;
  note?: string;
  created_at: string;
  [key: string]: unknown;
}

/* -------------------------------- Invoices ------------------------------- */

export interface Invoice {
  invoice_id: UUID;
  po_id: UUID;
  sale_id: UUID;
  invoice_number: string;
  status: InvoiceStatus;
  gst_irn: string;
  s3_url: string;
  total_amount: number;
  created_at: string;
  updated_at: string;
  gst_status?: GSTStatus;
  delivery_status?: DeliveryStatus;
}

export interface InvoiceFilters {
  search?: string;
  status?: InvoiceStatus;
  page?: number;
  per_page?: number;
}

export type InvoiceListResponse = PaginatedResponse<Invoice>;

export interface InvoiceDownloadResponse {
  url: string;
}

export interface InvoiceHistoryEntry {
  id?: string;
  event: string;
  note?: string;
  created_at: string;
  [key: string]: unknown;
}

/* -------------------------------- Dashboard ------------------------------ */

export interface DashboardSummary {
  total_customers: number;
  total_products: number;
  total_pos?: number;
  total_purchase_orders?: number;
  total_sales: number;
  total_revenue: number;
  open_pos: number;
  pending_invoices: number;
  generated_invoices?: number;
  sent_invoices?: number;
  ai_success_rate?: number;
}

export interface RecentOrderItem {
  po_id: UUID;
  po_number: string;
  customer: string;
  status: PurchaseOrderStatus;
  total_amount: number;
  created_at: string;
}

export interface RecentSaleItem {
  sale_id: UUID;
  po_number: string;
  status: SaleStatus;
  total_amount: number;
  created_at: string;
}

export interface RecentInvoiceItem {
  invoice_id: UUID;
  invoice_number: string;
  status: InvoiceStatus;
  total_amount: number;
  created_at: string;
}

/* ----------------------------- Agent / workflow -------------------------- */

export interface HitlContext {
  message: string;
  options: HITLDecision[];
  question?: string | null;
  context: Record<string, unknown>;
}

export interface CreateCustomerContext {
  run_id: string;
  message: string;
  customer_name: string;
  customer_gst_no?: string | null;
  customer_code?: string | null;
  candidates?: unknown[];
}

export interface AgentRun {
  run_id: UUID;
  workflow: AgentWorkflow;
  status: AgentRunStatus;
  current_step: string | null;
  po_id: UUID | null;
  sale_id: UUID | null;
  invoice_id: UUID | null;
  hitl: HitlContext | null;
}

export interface HITLDecisionRequest {
  decision: HITLDecision;
  changes?: Record<string, unknown>;
  reason?: string;
}

export interface VerificationIssue {
  code: string;
  message: string;
  severity: "error" | "warning";
  details: Record<string, unknown>;
}

export interface VerificationPayload {
  has_blocking_issues: boolean;
  issues: VerificationIssue[];
  customer_verified: boolean;
  customer_id: UUID | null;
  products_verified: number;
  products_total: number;
  policy_applied: string[];
  checks: Record<string, unknown>;
}

export interface ExtractedLineItem {
  line_item_id?: string;
  product_name?: string;
  sku?: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface ExtractedPO {
  po_number?: string;
  customer?: string;
  gst_no?: string;
  ship_to?: string;
  address_1?: string;
  address_2?: string;
  city?: string;
  state?: string;
  country?: string;
  zip?: string;
  line_items: ExtractedLineItem[];
  total_amount: number;
}

export interface HitlReviewContext {
  run_id: UUID;
  po_number?: string;
  customer?: string;
  issues: VerificationIssue[];
  total_amount: number;
}

/* -------------------------------- Uploader ------------------------------- */

export interface ProcessedUpload {
  run: AgentRun;
  po_id?: UUID;
  sale_id?: UUID;
}

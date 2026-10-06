export type ISOString = string;

export type UUID = string;

export interface Address {
  shipTo: string;
  address1: string;
  address2: string;
  city: string;
  state: string;
  country: string;
  zip: string;
}

export type PurchaseOrderStatus = "DRAFT" | "APPROVED" | "REJECTED";

export type SaleStatus =
  | "CREATED"
  | "CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED";

export type InvoiceStatus = "GENERATED" | "SENT";

export type AgentRunStatus =
  | "QUEUED"
  | "RUNNING"
  | "WAITING_FOR_HUMAN"
  | "COMPLETED"
  | "FAILED";

export type AgentWorkflow = "PURCHASE_ORDER" | "INVOICE";

export type HITLDecision = "APPROVE" | "REJECT" | "EDIT";

export type DeliveryStatus = "PENDING" | "DELIVERED" | "RETRY_DELIVERY";

export type GSTStatus = "PROCESSING" | "REGISTERED";

export interface PaginatedMeta {
  page: number;
  perPage: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginatedMeta;
}
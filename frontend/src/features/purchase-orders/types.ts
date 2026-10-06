export type {
  POLineItem,
  POLineItemUpdate,
  PurchaseOrder,
  PurchaseOrderDetail,
  PurchaseOrderFilters,
  PurchaseOrderHistoryEntry,
  PurchaseOrderListItem,
  PurchaseOrderListResponse,
  PurchaseOrderUpdate,
} from "@/types/api";

export interface PurchaseOrderFilterForm {
  search: string;
  status: string;
  date_from: string;
  date_to: string;
  min_confidence: string;
}

export const EMPTY_PO_FILTERS: PurchaseOrderFilterForm = {
  search: "",
  status: "",
  date_from: "",
  date_to: "",
  min_confidence: "",
};
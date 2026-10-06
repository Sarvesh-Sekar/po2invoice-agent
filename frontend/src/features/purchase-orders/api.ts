import { goHttpClient, pythonHttpClient, LONG_TIMEOUT_MS } from "@/lib/httpClient";
import { normalizePaginated } from "@/lib/normalize";
import type {
  AgentRun,
  HITLDecisionRequest,
  POLineItem,
  POLineItemUpdate,
  PurchaseOrder,
  PurchaseOrderDetail,
  PurchaseOrderFilters,
  PurchaseOrderHistoryEntry,
  PurchaseOrderListResponse,
  PurchaseOrderUpdate,
} from "@/types/api";

function toFilterParams(filters: PurchaseOrderFilters) {
  return {
    search: filters.search,
    status: filters.status,
    date_from: filters.date_from,
    date_to: filters.date_to,
    min_confidence: filters.min_confidence,
    page: filters.page,
    per_page: filters.per_page,
  };
}

export const purchaseOrderApi = {
  async getPurchaseOrders(filters: PurchaseOrderFilters = {}): Promise<PurchaseOrderListResponse> {
    const payload = await goHttpClient.get<unknown>("/purchase-orders", {
      params: toFilterParams(filters),
    });
    return normalizePaginated(payload, {
      page: filters.page ?? 1,
      perPage: filters.per_page ?? 20,
    });
  },

  async getPurchaseOrder(id: string): Promise<PurchaseOrderDetail> {
    return goHttpClient.get<PurchaseOrderDetail>(`/purchase-orders/${id}`);
  },

  async updatePurchaseOrder(id: string, payload: PurchaseOrderUpdate): Promise<PurchaseOrder> {
    return goHttpClient.patch<PurchaseOrder>(`/purchase-orders/${id}`, payload);
  },

  async getLineItems(id: string): Promise<POLineItem[]> {
    const payload = await goHttpClient.get<unknown>(`/purchase-orders/${id}/line-items`);
    if (Array.isArray(payload)) return payload as POLineItem[];
    const nested = (payload as { data?: POLineItem[]; line_items?: POLineItem[] }) ?? {};
    return nested.line_items ?? nested.data ?? [];
  },

  async updateLineItem(
    poId: string,
    lineItemId: string,
    payload: POLineItemUpdate
  ): Promise<POLineItem> {
    return goHttpClient.patch<POLineItem>(
      `/purchase-orders/${poId}/line-items/${lineItemId}`,
      payload
    );
  },

  async getHistory(id: string): Promise<PurchaseOrderHistoryEntry[]> {
    const payload = await goHttpClient.get<unknown>(`/purchase-orders/${id}/history`);
    if (Array.isArray(payload)) return payload as PurchaseOrderHistoryEntry[];
    const nested = (payload as { data?: PurchaseOrderHistoryEntry[] }) ?? {};
    return nested.data ?? [];
  },

  async approve(poId: string): Promise<PurchaseOrder> {
    return goHttpClient.post<PurchaseOrder>(`/purchase-orders/${poId}/approve`);
  },

  async reject(poId: string, reason?: string): Promise<PurchaseOrder> {
    return goHttpClient.post<PurchaseOrder>(
      `/purchase-orders/${poId}/reject`,
      reason ? { reason } : undefined
    );
  },

  async uploadAndProcess(file: File): Promise<AgentRun> {
    const formData = new FormData();
    formData.append("file", file);
    return pythonHttpClient.post<AgentRun>("/agents/purchase-orders/process", formData, {
      timeout: LONG_TIMEOUT_MS,
    });
  },

  async submitDecision(runId: string, payload: HITLDecisionRequest): Promise<AgentRun> {
    return pythonHttpClient.post<AgentRun>(`/agents/purchase-orders/${runId}/decision`, payload, {
      timeout: LONG_TIMEOUT_MS,
    });
  },

  async getRun(runId: string): Promise<AgentRun> {
    return pythonHttpClient.get<AgentRun>(`/agents/runs/${runId}`);
  },
};

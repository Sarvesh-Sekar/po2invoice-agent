import { goHttpClient } from "@/lib/httpClient";
import { normalizePaginated } from "@/lib/normalize";
import type {
  Sale,
  SaleFilters,
  SaleHistoryEntry,
  SaleListResponse,
  SaleStatusUpdate,
} from "@/types/api";

export const saleApi = {
  async getSales(filters: SaleFilters = {}): Promise<SaleListResponse> {
    const payload = await goHttpClient.get<unknown>("/sales", {
      params: {
        search: filters.search,
        status: filters.status,
        date_from: filters.date_from,
        date_to: filters.date_to,
        page: filters.page,
        per_page: filters.per_page,
      },
    });
    return normalizePaginated(payload, {
      page: filters.page ?? 1,
      perPage: filters.per_page ?? 20,
    });
  },

  async getSale(id: string): Promise<Sale> {
    return goHttpClient.get<Sale>(`/sales/${id}`);
  },

  async updateSaleStatus(id: string, payload: SaleStatusUpdate): Promise<Sale> {
    return goHttpClient.patch<Sale>(`/sales/${id}/status`, payload);
  },

  async getHistory(id: string): Promise<SaleHistoryEntry[]> {
    const payload = await goHttpClient.get<unknown>(`/sales/${id}/history`);
    if (Array.isArray(payload)) return payload as SaleHistoryEntry[];
    const nested = (payload as { data?: SaleHistoryEntry[] }) ?? {};
    return nested.data ?? [];
  },
};
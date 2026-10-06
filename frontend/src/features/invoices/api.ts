import { goHttpClient } from "@/lib/httpClient";
import { normalizePaginated } from "@/lib/normalize";
import type {
  Invoice,
  InvoiceFilters,
  InvoiceHistoryEntry,
  InvoiceListResponse,
} from "@/types/api";

export const invoiceApi = {
  async getInvoices(filters: InvoiceFilters = {}): Promise<InvoiceListResponse> {
    const payload = await goHttpClient.get<unknown>("/invoices", {
      params: {
        search: filters.search,
        status: filters.status,
        page: filters.page,
        per_page: filters.per_page,
      },
    });
    return normalizePaginated(payload, {
      page: filters.page ?? 1,
      perPage: filters.per_page ?? 20,
    });
  },

  async getInvoice(id: string): Promise<Invoice> {
    return goHttpClient.get<Invoice>(`/invoices/${id}`);
  },

  async getHistory(id: string): Promise<InvoiceHistoryEntry[]> {
    const payload = await goHttpClient.get<unknown>(`/invoices/${id}/history`);
    if (Array.isArray(payload)) return payload as InvoiceHistoryEntry[];
    const nested = (payload as { data?: InvoiceHistoryEntry[] }) ?? {};
    return nested.data ?? [];
  },
};

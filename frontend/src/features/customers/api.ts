import { goHttpClient } from "@/lib/httpClient";
import { normalizePaginated } from "@/lib/normalize";
import type { Customer, CustomerDetail, CustomerHistoryEntry } from "@/types/api";
import type { PaginatedResponse } from "@/types/common";

export const customerApi = {
  async getCustomers(
    search?: string,
    page: number = 1,
    perPage: number = 20
  ): Promise<PaginatedResponse<Customer>> {
    const payload = await goHttpClient.get<unknown>("/customers", {
      params: { search, page, per_page: perPage },
    });
    return normalizePaginated(payload, { page, perPage });
  },

  async getCustomer(id: string): Promise<CustomerDetail> {
    return goHttpClient.get<CustomerDetail>(`/customers/${id}`);
  },

  async getHistory(id: string): Promise<CustomerHistoryEntry[]> {
    const payload = await goHttpClient.get<unknown>(`/customers/${id}/history`);
    if (Array.isArray(payload)) return payload as CustomerHistoryEntry[];
    const nested = (payload as { data?: CustomerHistoryEntry[] }) ?? {};
    return nested.data ?? [];
  },
};

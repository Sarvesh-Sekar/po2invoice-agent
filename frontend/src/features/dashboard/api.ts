import { goHttpClient } from "@/lib/httpClient";
import type {
  DashboardSummary,
  RecentInvoiceItem,
  RecentSaleItem,
} from "@/types/api";

export const dashboardApi = {
  async getSummary(): Promise<DashboardSummary> {
    return goHttpClient.get<DashboardSummary>("/dashboard/summary");
  },

  async getRecentSales(limit = 5): Promise<RecentSaleItem[]> {
    return goHttpClient.get<RecentSaleItem[]>("/dashboard/recent-sales", {
      params: { limit },
    });
  },

  async getRecentInvoices(limit = 5): Promise<RecentInvoiceItem[]> {
    return goHttpClient.get<RecentInvoiceItem[]>("/dashboard/recent-invoices", {
      params: { limit },
    });
  },
};
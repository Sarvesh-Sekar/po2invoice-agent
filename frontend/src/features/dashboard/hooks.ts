import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/features/dashboard/api";
import { queryKeys } from "@/lib/queryKeys";

export function useDashboardSummary() {
  return useQuery({
    queryKey: queryKeys.dashboard.summary,
    queryFn: dashboardApi.getSummary,
    staleTime: 60_000,
  });
}

export function useRecentSales(limit = 5) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.recentSales, limit],
    queryFn: () => dashboardApi.getRecentSales(limit),
    staleTime: 60_000,
  });
}

export function useRecentInvoices(limit = 5) {
  return useQuery({
    queryKey: [...queryKeys.dashboard.recentInvoices, limit],
    queryFn: () => dashboardApi.getRecentInvoices(limit),
    staleTime: 60_000,
  });
}
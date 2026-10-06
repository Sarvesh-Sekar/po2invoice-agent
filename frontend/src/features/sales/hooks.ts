import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { saleApi } from "@/features/sales/api";
import { queryKeys } from "@/lib/queryKeys";
import { useUIStore } from "@/stores/uiStore";
import type { SaleFilters, SaleStatusUpdate } from "@/types/api";

export function useSales(filters: SaleFilters) {
  return useQuery({
    queryKey: queryKeys.sales.list(filters),
    queryFn: () => saleApi.getSales(filters),
    placeholderData: (previous) => previous,
  });
}

export function useSale(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.sales.detail(id ?? ""),
    queryFn: () => saleApi.getSale(id as string),
    enabled: Boolean(id),
  });
}

export function useSaleHistory(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.sales.history(id ?? ""),
    queryFn: () => saleApi.getHistory(id as string),
    enabled: Boolean(id),
  });
}

export function useUpdateSaleStatus() {
  const queryClient = useQueryClient();
  const pushToast = useUIStore((state) => state.pushToast);

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SaleStatusUpdate }) =>
      saleApi.updateSaleStatus(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sales.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.invoices.all });
      pushToast("success", "Sale status updated.");
    },
    onError: () => pushToast("error", "Unable to update sale status."),
  });
}
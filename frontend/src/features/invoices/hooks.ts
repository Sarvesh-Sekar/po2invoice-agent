import { useQuery } from "@tanstack/react-query";
import { invoiceApi } from "@/features/invoices/api";
import { queryKeys } from "@/lib/queryKeys";
import type { InvoiceFilters } from "@/types/api";

export function useInvoices(filters: InvoiceFilters) {
  return useQuery({
    queryKey: queryKeys.invoices.list(filters),
    queryFn: () => invoiceApi.getInvoices(filters),
    placeholderData: (previous) => previous,
  });
}

export function useInvoice(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.invoices.detail(id ?? ""),
    queryFn: () => invoiceApi.getInvoice(id as string),
    enabled: Boolean(id),
  });
}

export function useInvoiceHistory(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.invoices.history(id ?? ""),
    queryFn: () => invoiceApi.getHistory(id as string),
    enabled: Boolean(id),
  });
}

import { useQuery } from "@tanstack/react-query";
import { customerApi } from "@/features/customers/api";
import { queryKeys } from "@/lib/queryKeys";

export function useCustomers(search?: string, page: number = 1) {
  return useQuery({
    queryKey: [...queryKeys.customers.list(search), "page", page] as const,
    queryFn: () => customerApi.getCustomers(search, page),
    placeholderData: (previous) => previous,
  });
}

export function useCustomer(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.customers.detail(id ?? ""),
    queryFn: () => customerApi.getCustomer(id as string),
    enabled: Boolean(id),
  });
}

export function useCustomerHistory(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.customers.history(id ?? ""),
    queryFn: () => customerApi.getHistory(id as string),
    enabled: Boolean(id),
  });
}

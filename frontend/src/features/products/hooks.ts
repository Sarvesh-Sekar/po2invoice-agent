import { useQuery } from "@tanstack/react-query";
import { productApi } from "@/features/products/api";
import { queryKeys } from "@/lib/queryKeys";

export function useProducts(search?: string, page: number = 1) {
  return useQuery({
    queryKey: [...queryKeys.products.list(search), "page", page] as const,
    queryFn: () => productApi.getProducts(search, page),
    placeholderData: (previous) => previous,
  });
}

export function useProduct(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.products.detail(id ?? ""),
    queryFn: () => productApi.getProduct(id as string),
    enabled: Boolean(id),
  });
}

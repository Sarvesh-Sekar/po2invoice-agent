import { goHttpClient } from "@/lib/httpClient";
import { normalizePaginated } from "@/lib/normalize";
import type { Product } from "@/types/api";
import type { PaginatedResponse } from "@/types/common";

export const productApi = {
  async getProducts(
    search?: string,
    page: number = 1,
    perPage: number = 20
  ): Promise<PaginatedResponse<Product>> {
    const payload = await goHttpClient.get<unknown>("/products", {
      params: { search, page, per_page: perPage },
    });
    return normalizePaginated(payload, { page, perPage });
  },

  async getProduct(id: string): Promise<Product> {
    return goHttpClient.get<Product>(`/products/${id}`);
  },
};

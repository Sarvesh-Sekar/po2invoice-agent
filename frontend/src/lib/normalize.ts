import type { PaginatedMeta, PaginatedResponse } from "@/types/common";

interface PaginatedLike<T> {
  data?: T[];
  items?: T[];
  results?: T[];
  meta?: Partial<PaginatedMeta> & {
    total?: number;
    page?: number;
    per_page?: number;
    perPage?: number;
  };
  total?: number;
  page?: number;
  per_page?: number;
  perPage?: number;
}

export function normalizePaginated<T>(
  payload: unknown,
  defaults: { page: number; perPage: number }
): PaginatedResponse<T> {
  if (Array.isArray(payload)) {
    return {
      data: payload as T[],
      meta: {
        page: defaults.page,
        perPage: defaults.perPage,
        total: payload.length,
        totalPages: 1,
      },
    };
  }

  const value = (payload ?? {}) as PaginatedLike<T>;
  const data = value.data ?? value.items ?? value.results ?? [];
  const metaSource = value.meta ?? value;
  const page = Number(metaSource.page ?? defaults.page) || defaults.page;
  const perPage =
    Number(metaSource.per_page ?? metaSource.perPage ?? defaults.perPage) || defaults.perPage;
  const total = Number(metaSource.total ?? data.length) || 0;
  const totalPages =
    Number(
      (metaSource as { total_pages?: number }).total_pages ??
        (metaSource as { totalPages?: number }).totalPages
    ) || Math.max(1, Math.ceil(total / perPage));

  return {
    data,
    meta: { page, perPage, total, totalPages },
  };
}
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { Pagination } from "@/components/common/DataTable";
import { PurchaseOrderFilters } from "@/features/purchase-orders/components/PurchaseOrderFilters";
import { PurchaseOrderTable } from "@/features/purchase-orders/components/PurchaseOrderTable";
import { usePurchaseOrders } from "@/features/purchase-orders/hooks";
import { EMPTY_PO_FILTERS } from "@/features/purchase-orders/types";
import type { PurchaseOrderFilterForm } from "@/features/purchase-orders/types";
import { ROUTES } from "@/constants";
import type { PurchaseOrderFilters as PurchaseOrderFiltersType } from "@/types/api";

function formFromParams(params: URLSearchParams): PurchaseOrderFilterForm {
  return {
    search: params.get("search") ?? "",
    status: params.get("status") ?? "",
    date_from: params.get("date_from") ?? "",
    date_to: params.get("date_to") ?? "",
    min_confidence: params.get("min_confidence") ?? "",
  };
}

export function PurchaseOrdersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form, setForm] = useState<PurchaseOrderFilterForm>(() => formFromParams(searchParams));

  const page = Number(searchParams.get("page") ?? "1") || 1;

  const filters: PurchaseOrderFiltersType = useMemo(() => {
    const applied = formFromParams(searchParams);
    return {
      search: applied.search || undefined,
      status: (applied.status || undefined) as PurchaseOrderFiltersType["status"],
      date_from: applied.date_from || undefined,
      date_to: applied.date_to || undefined,
      min_confidence: applied.min_confidence ? Number(applied.min_confidence) : undefined,
      page,
      per_page: 20,
    };
  }, [searchParams, page]);

  const query = usePurchaseOrders(filters);

  function applyFilters() {
    const next = new URLSearchParams();
    if (form.search) next.set("search", form.search);
    if (form.status) next.set("status", form.status);
    if (form.date_from) next.set("date_from", form.date_from);
    if (form.date_to) next.set("date_to", form.date_to);
    if (form.min_confidence) next.set("min_confidence", form.min_confidence);
    next.set("page", "1");
    setSearchParams(next);
  }

  function clearFilters() {
    setForm(EMPTY_PO_FILTERS);
    setSearchParams(new URLSearchParams());
  }

  function changePage(nextPage: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    setSearchParams(next);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Purchase Orders"
        description="Extract, verify and review customer purchase orders"
        actions={
          <Link to={ROUTES.PURCHASE_ORDER_UPLOAD}>
            <Button>Upload PO</Button>
          </Link>
        }
      />

      <PurchaseOrderFilters
        value={form}
        onChange={setForm}
        onApply={applyFilters}
        onClear={clearFilters}
      />

      {query.isLoading ? (
        <SkeletonTable rows={8} cols={7} />
      ) : query.isError ? (
        <ErrorState
          message="Unable to load purchase orders."
          onRetry={() => query.refetch()}
        />
      ) : !query.data || query.data.data.length === 0 ? (
        <EmptyState
          title="No purchase orders found"
          description="Try changing your filters or upload a new purchase order."
          action={
            <Link to={ROUTES.PURCHASE_ORDER_UPLOAD}>
              <Button>Upload PO</Button>
            </Link>
          }
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <PurchaseOrderTable
              rows={query.data.data}
              onRowClick={(row) => navigate(`${ROUTES.PURCHASE_ORDERS}/${row.po_id}`)}
            />
          </div>
          <Pagination meta={query.data.meta} onPageChange={changePage} />
        </>
      )}
    </div>
  );
}
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { Pagination } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Table, type Column } from "@/components/ui/Table";
import { ROUTES, SALE_STATUSES } from "@/constants";
import { useSales } from "@/features/sales/hooks";
import type { SaleFilters, SaleListItem } from "@/types/api";
import { formatCurrency, formatDate, titleCase } from "@/lib/utils";

export function SalesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get("search") ?? "";
  const status = searchParams.get("status") ?? "";
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const [searchInput, setSearchInput] = useState(search);
  const [statusInput, setStatusInput] = useState(status);

  const filters: SaleFilters = useMemo(
    () => ({
      search: search || undefined,
      status: (status || undefined) as SaleFilters["status"],
      page,
      per_page: 20,
    }),
    [search, status, page]
  );

  const query = useSales(filters);

  const columns: Array<Column<SaleListItem>> = [
    {
      key: "sale_id",
      header: "Sale ID",
      cell: (row) => <span className="font-medium text-gray-900">{row.sale_id.slice(0, 8)}…</span>,
    },
    {
      key: "po_number",
      header: "PO Reference",
      cell: (row) =>
        row.po_number ? (
          <span className="text-gray-700">{row.po_number}</span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: "customer_name",
      header: "Customer",
      cell: (row) => row.customer_name ?? "—",
    },
    {
      key: "total_amount",
      header: "Amount",
      align: "right",
      cell: (row) => formatCurrency(row.total_amount),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status} label={titleCase(row.status)} />,
    },
    {
      key: "created_at",
      header: "Created",
      cell: (row) => formatDate(row.created_at),
    },
  ];

  function apply() {
    const next = new URLSearchParams();
    if (searchInput) next.set("search", searchInput);
    if (statusInput) next.set("status", statusInput);
    next.set("page", "1");
    setSearchParams(next);
  }

  function clear() {
    setSearchInput("");
    setStatusInput("");
    setSearchParams(new URLSearchParams());
  }

  function changePage(page: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(page));
    setSearchParams(next);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Sales"
        description="Track sales from confirmation through delivery."
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate(ROUTES.DASHBOARD)}>
            Back
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-12">
        <div className="sm:col-span-7">
          <Input
            placeholder="Search by sale ID, PO reference or customer"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") apply();
            }}
          />
        </div>
        <div className="sm:col-span-2">
          <Select
            aria-label="Status"
            value={statusInput}
            onChange={(event) => setStatusInput(event.target.value)}
            options={[
              { value: "", label: "All statuses" },
              ...SALE_STATUSES.map((statusValue) => ({
                value: statusValue,
                label: titleCase(statusValue),
              })),
            ]}
          />
        </div>
        <div className="flex items-end gap-2 sm:col-span-3">
          <Button size="md" onClick={apply} className="w-full">
            Apply
          </Button>
          <Button variant="secondary" size="md" onClick={clear}>
            Clear
          </Button>
        </div>
      </div>

      {query.isLoading ? (
        <SkeletonTable rows={8} cols={6} />
      ) : query.isError ? (
        <ErrorState message="Unable to load sales." onRetry={() => query.refetch()} />
      ) : !query.data || query.data.data.length === 0 ? (
        <EmptyState
          title="No sales found"
          description="Create a sale by approving a purchase order, or adjust your filters."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <Table
              columns={columns}
              rows={query.data.data}
              rowKey={(row) => row.sale_id}
              onRowClick={(row) => navigate(`${ROUTES.SALES}/${row.sale_id}`)}
            />
          </div>
          <Pagination
            meta={query.data.meta}
            onPageChange={changePage}
          />
        </>
      )}
    </div>
  );
}
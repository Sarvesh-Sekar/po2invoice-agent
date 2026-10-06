import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SkeletonTable } from "@/components/ui/Skeleton";
import { Pagination } from "@/components/common/DataTable";
import { Table, type Column } from "@/components/ui/Table";
import { ROUTES } from "@/constants";
import { useProducts } from "@/features/products/hooks";
import type { Product } from "@/types/api";
import { formatCurrency, formatDate, formatNumber } from "@/lib/utils";

export function ProductsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get("search") ?? "";
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const [searchInput, setSearchInput] = useState(search);

  const query = useProducts(search || undefined, page);

  const columns: Array<Column<Product>> = [
    {
      key: "name",
      header: "Name",
      cell: (row) => <span className="font-medium text-gray-900">{row.name}</span>,
    },
    {
      key: "sku",
      header: "SKU",
      cell: (row) => <span className="font-mono text-xs text-gray-600">{row.sku}</span>,
    },
    {
      key: "price",
      header: "Price",
      align: "right",
      cell: (row) => formatCurrency(row.price),
    },
    {
      key: "stock",
      header: "Stock",
      align: "right",
      cell: (row) => (
        <span className={row.stock <= 0 ? "text-red-600" : "text-gray-700"}>
          {formatNumber(row.stock)}
        </span>
      ),
    },
    {
      key: "is_active",
      header: "Status",
      cell: (row) => (
        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
            row.is_active ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
          }`}
        >
          {row.is_active ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Added",
      cell: (row) => formatDate(row.created_at),
    },
  ];

  function apply() {
    const next = new URLSearchParams();
    if (searchInput) next.set("search", searchInput);
    next.set("page", "1");
    setSearchParams(next);
  }

  function clear() {
    setSearchInput("");
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
        title="Products"
        description="Manage your product catalog and stock levels."
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate(ROUTES.DASHBOARD)}>
            Back
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-12">
        <div className="sm:col-span-7">
          <Input
            placeholder="Search by name or SKU"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") apply();
            }}
          />
        </div>
        <div className="flex items-end gap-2 sm:col-span-5">
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
        <ErrorState message="Unable to load products." onRetry={() => query.refetch()} />
      ) : !query.data || query.data.data.length === 0 ? (
        <EmptyState
          title="No products found"
          description="Products are added when purchase orders are processed. Adjust your search to see more."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <Table
              columns={columns}
              rows={query.data.data}
              rowKey={(row) => row.product_id}
              onRowClick={(row) => navigate(`${ROUTES.PRODUCTS}/${row.product_id}`)}
            />
          </div>
          <Pagination meta={query.data.meta} onPageChange={changePage} />
        </>
      )}
    </div>
  );
}

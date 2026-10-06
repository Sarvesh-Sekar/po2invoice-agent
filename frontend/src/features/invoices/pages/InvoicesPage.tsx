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
import { ROUTES } from "@/constants";
import { useInvoices } from "@/features/invoices/hooks";
import type { Invoice, InvoiceFilters } from "@/types/api";
import { formatCurrency, formatDate, titleCase } from "@/lib/utils";

const INVOICE_STATUS_OPTIONS = ["GENERATED", "SENT"];

export function InvoicesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const search = searchParams.get("search") ?? "";
  const status = searchParams.get("status") ?? "";
  const page = Number(searchParams.get("page") ?? "1") || 1;

  const [searchInput, setSearchInput] = useState(search);
  const [statusInput, setStatusInput] = useState(status);

  const filters: InvoiceFilters = useMemo(
    () => ({
      search: search || undefined,
      status: (status || undefined) as InvoiceFilters["status"],
      page,
      per_page: 20,
    }),
    [search, status, page]
  );

  const query = useInvoices(filters);

  const columns: Array<Column<Invoice>> = [
    {
      key: "invoice_number",
      header: "Invoice",
      cell: (row) => <span className="font-medium text-gray-900">{row.invoice_number}</span>,
    },
    {
      key: "invoice_id",
      header: "Invoice ID",
      cell: (row) => <span className="text-gray-500">{row.invoice_id.slice(0, 8)}…</span>,
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status} label={titleCase(row.status)} />,
    },
    {
      key: "gst_status",
      header: "GST",
      cell: (row) =>
        row.gst_status ? (
          <StatusBadge status={row.gst_status} label={titleCase(row.gst_status)} />
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: "delivery_status",
      header: "Delivery",
      cell: (row) =>
        row.delivery_status ? (
          <StatusBadge status={row.delivery_status} label={titleCase(row.delivery_status)} />
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: "total_amount",
      header: "Amount",
      align: "right",
      cell: (row) => formatCurrency(row.total_amount),
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

  function changePage(nextPage: number) {
    const next = new URLSearchParams(searchParams);
    next.set("page", String(nextPage));
    setSearchParams(next);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Invoices"
        description="Manage generated invoices and track their delivery status."
        actions={
          <Button variant="secondary" size="sm" onClick={() => navigate(ROUTES.DASHBOARD)}>
            Back
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-12">
        <div className="sm:col-span-7">
          <Input
            placeholder="Search by invoice number"
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
              ...INVOICE_STATUS_OPTIONS.map((statusValue) => ({
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
        <SkeletonTable rows={8} cols={7} />
      ) : query.isError ? (
        <ErrorState message="Unable to load invoices." onRetry={() => query.refetch()} />
      ) : !query.data || query.data.data.length === 0 ? (
        <EmptyState
          title="No invoices found"
          description="Invoices are generated automatically when a sale is processed. Adjust your filters to see more."
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <Table columns={columns} rows={query.data.data} rowKey={(row) => row.invoice_id} />
          </div>
          <Pagination meta={query.data.meta} onPageChange={changePage} />
        </>
      )}
    </div>
  );
}

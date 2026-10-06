import { Link } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { KpiCard } from "@/features/dashboard/components/KpiCard";
import { ListCard, SectionCard } from "@/features/dashboard/components/SectionCard";
import {
  useDashboardSummary,
  useRecentInvoices,
  useRecentSales,
} from "@/features/dashboard/hooks";
import { useAuthStore } from "@/stores/authStore";
import { ROUTES } from "@/constants";
import { formatCurrency, relativeTime, titleCase } from "@/lib/utils";
import { StatusBadge } from "@/components/common/StatusBadge";
import type { DashboardSummary } from "@/types/api";

const icon = {
  sales: (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
    </svg>
  ),
  review: (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  revenue: (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  invoice: (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2Z" />
    </svg>
  ),
  ai: (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
    </svg>
  ),
};

function SummarySkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton key={index} className="h-[92px] rounded-lg" />
      ))}
    </div>
  );
}

function totalOrders(summary: DashboardSummary): number {
  return summary.total_pos ?? summary.total_purchase_orders ?? 0;
}

export function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const summary = useDashboardSummary();
  const recentSales = useRecentSales(5);
  const recentInvoices = useRecentInvoices(5);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back${user?.name ? `, ${user.name.split(" ")[0]}` : ""}`}
        description="Overview of your order-to-invoice pipeline"
        actions={
          <Link
            to={ROUTES.PURCHASE_ORDER_UPLOAD}
            className="inline-flex h-9 items-center justify-center rounded-md bg-indigo-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-indigo-700"
          >
            Upload PO
          </Link>
        }
      />

      {summary.isLoading ? (
        <SummarySkeleton />
      ) : summary.isError ? (
        <ErrorState
          message="Unable to load dashboard summary."
          onRetry={() => summary.refetch()}
        />
      ) : summary.data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Total Sales"
            value={formatCurrency(summary.data.total_revenue)}
            hint={`${summary.data.total_sales} sales created`}
            tone="indigo"
            icon={icon.sales}
          />
          <KpiCard
            label="Pending Review"
            value={summary.data.open_pos}
            hint={`${totalOrders(summary.data)} purchase orders`}
            tone="amber"
            icon={icon.review}
          />
          <KpiCard
            label="AI Success Rate"
            value={
              typeof summary.data.ai_success_rate === "number"
                ? `${Math.round(summary.data.ai_success_rate)}%`
                : "—"
            }
            hint={
              typeof summary.data.ai_success_rate === "number"
                ? "Auto-verified by AI agent"
                : "Not reported by backend"
            }
            tone="green"
            icon={icon.ai}
          />
          <KpiCard
            label="Invoices Sent"
            value={summary.data.sent_invoices ?? summary.data.pending_invoices}
            hint={
              summary.data.sent_invoices !== undefined
                ? `${summary.data.pending_invoices} pending`
                : "Pending invoices"
            }
            tone="blue"
            icon={icon.invoice}
          />
        </div>
      ) : null}

      <SectionCard
        title="Attention Required"
        action={
          <Link
            to={ROUTES.PURCHASE_ORDERS}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
          >
            Review queue
          </Link>
        }
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-gray-600">
            {summary.data && summary.data.open_pos > 0
              ? `${summary.data.open_pos} purchase order${summary.data.open_pos === 1 ? "" : "s"} require human review before sale creation.`
              : "No purchase orders currently require attention."}
          </p>
          <Link
            to={ROUTES.PURCHASE_ORDERS}
            className="inline-flex h-8 items-center justify-center rounded-md border border-indigo-300 px-3 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
          >
            Go to Purchase Orders
          </Link>
        </div>
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <ListCard
          title="Recent Sales"
          viewAllTo={ROUTES.SALES}
          isLoading={recentSales.isLoading}
          isError={recentSales.isError}
          errorMessage="Unable to load recent sales."
          onRetry={() => recentSales.refetch()}
          items={recentSales.data}
          getKey={(item) => item.sale_id}
          emptyTitle="No sales yet"
          emptyDescription="Approved purchase orders will appear here as sales."
          renderItem={(sale) => (
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900">
                  {sale.po_number ?? sale.sale_id.slice(0, 8)}
                </p>
                <p className="text-xs text-gray-500">{relativeTime(sale.created_at)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-sm font-medium text-gray-800">
                  {formatCurrency(sale.total_amount)}
                </span>
                <StatusBadge status={sale.status} label={titleCase(sale.status)} />
              </div>
            </div>
          )}
        />

        <ListCard
          title="Recent Invoices"
          viewAllTo={ROUTES.INVOICES}
          isLoading={recentInvoices.isLoading}
          isError={recentInvoices.isError}
          errorMessage="Unable to load recent invoices."
          onRetry={() => recentInvoices.refetch()}
          items={recentInvoices.data}
          getKey={(item) => item.invoice_id}
          emptyTitle="No invoices yet"
          emptyDescription="Invoices are generated automatically once sales are delivered."
          renderItem={(invoice) => (
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-gray-900">{invoice.invoice_number}</p>
                <p className="text-xs text-gray-500">{relativeTime(invoice.created_at)}</p>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-sm font-medium text-gray-800">
                  {formatCurrency(invoice.total_amount)}
                </span>
                <StatusBadge status={invoice.status} label={titleCase(invoice.status)} />
              </div>
            </div>
          )}
        />
      </div>
    </div>
  );
}
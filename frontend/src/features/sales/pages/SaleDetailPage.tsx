import { Link, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { SaleTimeline } from "@/features/sales/components/SaleTimeline";
import { useSale, useSaleHistory, useUpdateSaleStatus } from "@/features/sales/hooks";
import { ROUTES } from "@/constants";
import { formatCurrency, formatDate, formatDateTime, titleCase } from "@/lib/utils";

export function SaleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const query = useSale(id);
  const historyQuery = useSaleHistory(id);
  const updateStatus = useUpdateSaleStatus();

  if (query.isLoading) {
    return <LoadingState title="Loading sale" />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message="Unable to load sale." onRetry={() => query.refetch()} />;
  }

  const sale = query.data;

  function advance() {
    if (sale.status === "CREATED") {
      updateStatus.mutate({ id: sale.sale_id, payload: { status: "CONFIRMED" } });
    } else if (sale.status === "CONFIRMED") {
      updateStatus.mutate({ id: sale.sale_id, payload: { status: "PROCESSING" } });
    } else if (sale.status === "PROCESSING") {
      updateStatus.mutate({ id: sale.sale_id, payload: { status: "SHIPPED" } });
    } else if (sale.status === "SHIPPED") {
      updateStatus.mutate({ id: sale.sale_id, payload: { status: "DELIVERED" } });
    }
  }

  const nextLabel =
    sale.status === "CREATED"
      ? "Confirm"
      : sale.status === "CONFIRMED"
        ? "Start Processing"
        : sale.status === "PROCESSING"
          ? "Ship"
          : sale.status === "SHIPPED"
            ? "Mark Delivered"
            : null;

  return (
    <div className="space-y-5">
      <PageHeader
        title={`Sale ${sale.sale_id.slice(0, 8).toUpperCase()}`}
        description={`Created ${formatDate(sale.created_at)}`}
        actions={
          <>
            <Link to={ROUTES.SALES}>
              <Button variant="ghost" size="sm">
                Back
              </Button>
            </Link>
            <StatusBadge status={sale.status} label={titleCase(sale.status)} />
          </>
        }
      />

      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <SaleTimeline
          status={sale.status}
          onAdvance={advance}
          advancing={updateStatus.isPending}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">Details</h2>
          <dl className="space-y-2 text-sm">
            <DetailRow label="Sale ID" value={sale.sale_id} />
            <DetailRow label="PO Reference" value={sale.po_id} />
            <DetailRow label="Amount" value={formatCurrency(sale.total_amount)} />
            <DetailRow label="Status" value={titleCase(sale.status)} />
            <DetailRow label="Created" value={formatDateTime(sale.created_at)} />
            <DetailRow label="Updated" value={formatDateTime(sale.updated_at)} />
          </dl>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-900">History</h2>
          {historyQuery.isLoading ? (
            <p className="text-sm text-gray-400">Loading history…</p>
          ) : historyQuery.data && historyQuery.data.length > 0 ? (
            <ul className="space-y-3">
              {historyQuery.data.map((entry, index) => (
                <li key={entry.id ?? `${entry.to_status}-${index}`} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{titleCase(entry.to_status)}</p>
                    {entry.note && <p className="text-xs text-gray-500">{entry.note}</p>}
                    <p className="text-xs text-gray-400">{formatDateTime(entry.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">No history recorded.</p>
          )}
        </div>
      </div>

      {nextLabel && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <p>
            Next step: <span className="font-semibold">{nextLabel}</span>. When the sale becomes
            DELIVERED, invoice generation is triggered automatically by the backend.
          </p>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-900">{value}</dd>
    </div>
  );
}
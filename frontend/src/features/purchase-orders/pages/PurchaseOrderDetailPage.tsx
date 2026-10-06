import { Link, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { StatusBadge } from "@/components/common/StatusBadge";
import { VerificationPanel } from "@/features/purchase-orders/components/VerificationPanel";
import { ReviewDocumentPanel } from "@/features/purchase-orders/components/ReviewDocumentPanel";
import { Table, type Column } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import {
  usePurchaseOrder,
  usePurchaseOrderHistory,
} from "@/features/purchase-orders/hooks";
import { ROUTES } from "@/constants";
import { formatCurrency, formatDate, formatDateTime, titleCase } from "@/lib/utils";
import type { POLineItem } from "@/types/api";

export function PurchaseOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const query = usePurchaseOrder(id);
  const historyQuery = usePurchaseOrderHistory(id);

  if (query.isLoading) {
    return <LoadingState title="Loading purchase order" />;
  }

  if (query.isError || !query.data) {
    return <ErrorState message="Unable to load purchase order." onRetry={() => query.refetch()} />;
  }

  const po = query.data;

  const lineItemColumns: Array<Column<POLineItem>> = [
    {
      key: "product",
      header: "Product",
      cell: (row) => <span className="font-medium text-gray-900">{row.product_id.slice(0, 8)}…</span>,
    },
    { key: "quantity", header: "Qty", align: "right" },
    {
      key: "unit_price",
      header: "Unit Price",
      align: "right",
      cell: (row) => formatCurrency(row.unit_price),
    },
    {
      key: "total_price",
      header: "Total",
      align: "right",
      cell: (row) => formatCurrency(row.total_price),
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title={po.po_number}
        description={`Created ${formatDate(po.created_at)} · Customer ${po.customer_id.slice(0, 8)}…`}
        actions={
          <>
            <Link to={ROUTES.PURCHASE_ORDERS}>
              <Button variant="ghost" size="sm">
                Back
              </Button>
            </Link>
            <StatusBadge status={po.status} label={titleCase(po.status)} />
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Customer & Shipping</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Customer" value={po.customer?.name ?? po.customer_id} />
              <Field label="GST Number" value={po.customer?.gst_no ?? "—"} />
              <Field label="Ship To" value={po.ship_to || "—"} />
              <Field label="Address 1" value={po.address_1 || "—"} />
              <Field label="Address 2" value={po.address_2 || "—"} />
              <Field
                label="City / State"
                value={[po.city, po.state].filter(Boolean).join(", ") || "—"}
              />
              <Field label="Country" value={po.country || "—"} />
              <Field label="ZIP" value={po.zip || "—"} />
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <div className="border-b border-gray-100 px-4 py-3">
              <h2 className="text-sm font-semibold text-gray-900">Line Items</h2>
            </div>
            {po.line_items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-gray-400">No line items.</p>
            ) : (
              <Table
                columns={lineItemColumns}
                rows={po.line_items}
                rowKey={(row) => row.po_line_item_id}
                dense
              />
            )}
            <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
              <span className="text-sm font-medium text-gray-600">Total Amount</span>
              <span className="text-base font-semibold text-gray-900">
                {formatCurrency(po.total_amount)}
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">History</h2>
            {historyQuery.isLoading ? (
              <p className="text-sm text-gray-400">Loading history…</p>
            ) : historyQuery.data && historyQuery.data.length > 0 ? (
              <ul className="space-y-3">
                {historyQuery.data.map((entry, index) => (
                  <li key={entry.id ?? `${entry.action}-${index}`} className="flex gap-3">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-400" />
                    <div>
                      <p className="text-sm font-medium text-gray-800">{titleCase(entry.action)}</p>
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

        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <VerificationPanel
              issues={po.verification?.issues ?? []}
              verification={po.verification}
              aiConfidence={po.ai_confidence}
            />
          </div>
          <ReviewDocumentPanel sourceFileUrl={po.source_file_url} />
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-medium text-gray-900">{value}</p>
    </div>
  );
}
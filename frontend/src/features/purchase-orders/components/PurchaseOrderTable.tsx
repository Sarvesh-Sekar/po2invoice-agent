import { useNavigate } from "react-router-dom";
import { Table, type Column } from "@/components/ui/Table";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/Button";
import { ROUTES } from "@/constants";
import { formatCurrency, formatDate, titleCase } from "@/lib/utils";
import type { PurchaseOrderListItem } from "@/types/api";

export interface PurchaseOrderTableProps {
  rows: PurchaseOrderListItem[];
  onRowClick?: (row: PurchaseOrderListItem) => void;
  onAction?: (row: PurchaseOrderListItem) => void;
}

function confidenceTone(confidence: number): string {
  if (confidence >= 0.9) return "text-green-700";
  if (confidence >= 0.75) return "text-amber-700";
  return "text-red-700";
}

export function PurchaseOrderTable({ rows, onRowClick, onAction }: PurchaseOrderTableProps) {
  const navigate = useNavigate();

  const columns: Array<Column<PurchaseOrderListItem>> = [
    {
      key: "po_number",
      header: "PO Number",
      cell: (row) => <span className="font-medium text-gray-900">{row.po_number}</span>,
    },
    {
      key: "customer",
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
      key: "ai_confidence",
      header: "AI Verification",
      cell: (row) =>
        typeof row.ai_confidence === "number" ? (
          <span className={`font-medium ${confidenceTone(row.ai_confidence)}`}>
            {Math.round(row.ai_confidence * 100)}%
          </span>
        ) : (
          <span className="text-gray-400">Pending</span>
        ),
    },
    {
      key: "created_at",
      header: "Created",
      cell: (row) => formatDate(row.created_at),
    },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (row) => (
        <Button
          variant="secondary"
          size="xs"
          onClick={(event) => {
            event.stopPropagation();
            if (onAction) onAction(row);
            else navigate(`${ROUTES.PURCHASE_ORDERS}/${row.po_id}`);
          }}
        >
          View
        </Button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      rows={rows}
      rowKey={(row) => row.po_id}
      onRowClick={onRowClick}
    />
  );
}
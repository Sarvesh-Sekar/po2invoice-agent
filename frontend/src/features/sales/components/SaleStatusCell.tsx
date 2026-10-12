import { useState, type ChangeEvent } from "react";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Select } from "@/components/ui/Select";
import { useUpdateSaleStatus } from "@/features/sales/hooks";
import { nextSaleStatus, titleCase } from "@/lib/utils";
import type { SaleListItem } from "@/types/api";
import type { SaleStatus } from "@/types/common";

export interface SaleStatusCellProps {
  sale: SaleListItem;
}

export function SaleStatusCell({ sale }: SaleStatusCellProps) {
  const updateStatus = useUpdateSaleStatus();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const next = nextSaleStatus(sale.status);

  if (!next) {
    return <StatusBadge status={sale.status} label={titleCase(sale.status)} />;
  }

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    event.stopPropagation();
    event.currentTarget.value = sale.status;
    const target = event.target.value as SaleStatus;
    if (!target || target === sale.status) return;
    if (target === "DELIVERED") {
      setConfirmOpen(true);
      return;
    }
    updateStatus.mutate({ id: sale.sale_id, payload: { status: target } });
  }

  function confirmDelivered() {
    setConfirmOpen(false);
    updateStatus.mutate({ id: sale.sale_id, payload: { status: "DELIVERED" } });
  }

  return (
    <>
      <Select
        aria-label={`Status for sale ${sale.sale_id}`}
        value={sale.status}
        disabled={updateStatus.isPending}
        onClick={(event) => event.stopPropagation()}
        onChange={handleChange}
        className="h-8 w-auto px-2 text-xs"
        options={[
          { value: sale.status, label: titleCase(sale.status) },
          { value: next, label: titleCase(next) },
        ]}
      />
      <ConfirmDialog
        open={confirmOpen}
        title="Mark as delivered?"
        description="This triggers the invoice workflow for this sale and cannot be undone."
        confirmLabel="Mark Delivered"
        loading={updateStatus.isPending}
        onConfirm={confirmDelivered}
        onCancel={() => setConfirmOpen(false)}
      />
    </>
  );
}

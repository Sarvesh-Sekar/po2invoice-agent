import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { EMPTY_PO_FILTERS } from "@/features/purchase-orders/types";
import type { PurchaseOrderFilterForm } from "@/features/purchase-orders/types";

export interface PurchaseOrderFiltersProps {
  value: PurchaseOrderFilterForm;
  onChange: (value: PurchaseOrderFilterForm) => void;
  onApply: () => void;
  onClear: () => void;
}

const STATUS_OPTIONS = [
  { value: "DRAFT", label: "Draft" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
];

const CONFIDENCE_OPTIONS = [
  { value: "0.9", label: "90% and above" },
  { value: "0.8", label: "80% and above" },
  { value: "0.7", label: "70% and above" },
  { value: "0.5", label: "50% and above" },
];

export function PurchaseOrderFilters({
  value,
  onChange,
  onApply,
  onClear,
}: PurchaseOrderFiltersProps) {
  function update<K extends keyof PurchaseOrderFilterForm>(
    key: K,
    next: PurchaseOrderFilterForm[K]
  ) {
    onChange({ ...value, [key]: next });
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onApply();
  }

  function handleClear() {
    onChange(EMPTY_PO_FILTERS);
    onClear();
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-3 rounded-lg border border-gray-200 bg-white p-4 lg:grid-cols-12"
    >
      <div className="lg:col-span-4">
        <Input
          label="Search"
          placeholder="PO number or customer"
          value={value.search}
          onChange={(event) => update("search", event.target.value)}
        />
      </div>
      <div className="lg:col-span-2">
        <Select
          label="Status"
          placeholder="All statuses"
          options={STATUS_OPTIONS}
          value={value.status}
          onChange={(event) => update("status", event.target.value)}
        />
      </div>
      <div className="lg:col-span-2">
        <Input
          label="From"
          type="date"
          value={value.date_from}
          onChange={(event) => update("date_from", event.target.value)}
        />
      </div>
      <div className="lg:col-span-2">
        <Input
          label="To"
          type="date"
          value={value.date_to}
          onChange={(event) => update("date_to", event.target.value)}
        />
      </div>
      <div className="lg:col-span-2">
        <Select
          label="AI Confidence"
          placeholder="Any confidence"
          options={CONFIDENCE_OPTIONS}
          value={value.min_confidence}
          onChange={(event) => update("min_confidence", event.target.value)}
        />
      </div>
      <div className="flex items-end gap-2 lg:col-span-12">
        <Button type="submit" size="sm">
          Apply filters
        </Button>
        <Button type="button" variant="secondary" size="sm" onClick={handleClear}>
          Clear filters
        </Button>
      </div>
    </form>
  );
}
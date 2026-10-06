import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { formatCurrency } from "@/lib/utils";
import { calculateTotal, lineItemTotal } from "@/features/purchase-orders/schemas";
import type { EditableLineItem, ReviewFormState } from "@/stores/reviewStore";

export interface ReviewEditorPanelProps {
  form: ReviewFormState;
  isEditMode: boolean;
  errors: Record<string, string>;
  onChange: (form: ReviewFormState) => void;
  readOnly?: boolean;
}

export function ReviewEditorPanel({
  form,
  isEditMode,
  errors,
  onChange,
  readOnly = false,
}: ReviewEditorPanelProps) {
  function update<K extends keyof ReviewFormState>(key: K, value: ReviewFormState[K]) {
    onChange({ ...form, [key]: value });
  }

  function updateLineItem(index: number, patch: Partial<EditableLineItem>) {
    const lineItems = form.line_items.map((item, i) => {
      if (i !== index) return item;
      const merged = { ...item, ...patch };
      return { ...merged, total_price: lineItemTotal(merged.quantity, merged.unit_price) };
    });
    onChange({ ...form, line_items: lineItems, total_amount: calculateTotal(lineItems) });
  }

  function addLineItem() {
    const lineItems = [
      ...form.line_items,
      { line_item_id: undefined, product_name: "", sku: "", quantity: 1, unit_price: 0, total_price: 0 },
    ];
    onChange({ ...form, line_items: lineItems });
  }

  function removeLineItem(index: number) {
    const lineItems = form.line_items.filter((_, i) => i !== index);
    onChange({ ...form, line_items: lineItems, total_amount: calculateTotal(lineItems) });
  }

  const disabled = !isEditMode || readOnly;

  return (
    <div className="flex h-full flex-col rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-900">Extracted Data</h3>
        {isEditMode && (
          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
            Editing
          </span>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            label="PO Number"
            value={form.po_number}
            disabled={disabled}
            error={errors.po_number}
            onChange={(event) => update("po_number", event.target.value)}
          />
          <Input
            label="Customer"
            value={form.customer}
            disabled={disabled}
            error={errors.customer}
            onChange={(event) => update("customer", event.target.value)}
          />
          <Input
            label="GST Number"
            value={form.gst_no}
            disabled={disabled}
            onChange={(event) => update("gst_no", event.target.value)}
          />
          <Input
            label="Ship To"
            value={form.ship_to}
            disabled={disabled}
            onChange={(event) => update("ship_to", event.target.value)}
          />
          <Input
            label="Address 1"
            value={form.address_1}
            disabled={disabled}
            onChange={(event) => update("address_1", event.target.value)}
          />
          <Input
            label="Address 2"
            value={form.address_2}
            disabled={disabled}
            onChange={(event) => update("address_2", event.target.value)}
          />
          <Input
            label="City"
            value={form.city}
            disabled={disabled}
            onChange={(event) => update("city", event.target.value)}
          />
          <Input
            label="State"
            value={form.state}
            disabled={disabled}
            onChange={(event) => update("state", event.target.value)}
          />
          <Input
            label="Country"
            value={form.country}
            disabled={disabled}
            onChange={(event) => update("country", event.target.value)}
          />
          <Input
            label="ZIP"
            value={form.zip}
            disabled={disabled}
            onChange={(event) => update("zip", event.target.value)}
          />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Line Items</p>
            {isEditMode && !readOnly && (
              <Button variant="ghost" size="xs" onClick={addLineItem}>
                Add item
              </Button>
            )}
          </div>
          {errors.line_items && <p className="mb-2 text-xs text-red-600">{errors.line_items}</p>}
          <div className="space-y-2">
            {form.line_items.length === 0 && (
              <p className="rounded-md border border-dashed border-gray-300 px-3 py-4 text-center text-xs text-gray-400">
                No line items available.
              </p>
            )}
            {form.line_items.map((item, index) => (
              <div
                key={item.line_item_id ?? `item-${index}`}
                className="rounded-md border border-gray-200 p-3"
              >
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input
                    label="Product"
                    value={item.product_name ?? ""}
                    disabled={disabled}
                    onChange={(event) => updateLineItem(index, { product_name: event.target.value })}
                  />
                  <Input
                    label="SKU"
                    value={item.sku ?? ""}
                    disabled={disabled}
                    onChange={(event) => updateLineItem(index, { sku: event.target.value })}
                  />
                  <Input
                    label="Quantity"
                    type="number"
                    min={1}
                    value={item.quantity}
                    disabled={disabled}
                    error={errors[`line_items.${index}.quantity`]}
                    onChange={(event) =>
                      updateLineItem(index, { quantity: Number(event.target.value) })
                    }
                  />
                  <Input
                    label="Unit Price"
                    type="number"
                    min={0}
                    step="0.01"
                    value={item.unit_price}
                    disabled={disabled}
                    error={errors[`line_items.${index}.unit_price`]}
                    onChange={(event) =>
                      updateLineItem(index, { unit_price: Number(event.target.value) })
                    }
                  />
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    Total: <span className="font-medium text-gray-800">{formatCurrency(lineItemTotal(item.quantity, item.unit_price))}</span>
                  </span>
                  {isEditMode && !readOnly && (
                    <button
                      type="button"
                      onClick={() => removeLineItem(index)}
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-gray-100 pt-3">
          <span className="text-sm font-medium text-gray-600">Total amount</span>
          <span className="text-base font-semibold text-gray-900">
            {formatCurrency(form.total_amount)}
          </span>
        </div>
      </div>
    </div>
  );
}
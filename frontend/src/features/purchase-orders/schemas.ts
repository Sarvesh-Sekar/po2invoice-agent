import { PO_ALLOWED_EXTENSIONS, PO_FILE_LIMIT_MB } from "@/constants";
import type { EditableLineItem } from "@/stores/reviewStore";

export interface ValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}

export function validateFile(file: File): ValidationResult {
  const errors: Record<string, string> = {};
  const maxBytes = PO_FILE_LIMIT_MB * 1024 * 1024;
  const name = file.name.toLowerCase();
  const allowed = PO_ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));

  if (!allowed) {
    errors.file = `Unsupported file type. Allowed: ${PO_ALLOWED_EXTENSIONS.join(", ")}`;
  }
  if (file.size > maxBytes) {
    errors.file = `File is larger than ${PO_FILE_LIMIT_MB} MB.`;
  }
  return { valid: Object.keys(errors).length === 0, errors };
}

export function isSupportedFile(file: File): boolean {
  return validateFile(file).valid;
}

export interface PurchaseOrderEditForm {
  po_number: string;
  customer: string;
  gst_no: string;
  ship_to: string;
  address_1: string;
  city: string;
  state: string;
  country: string;
  zip: string;
  line_items: EditableLineItem[];
}

export function validatePurchaseOrderEdit(form: PurchaseOrderEditForm): ValidationResult {
  const errors: Record<string, string> = {};

  if (!form.po_number.trim()) errors.po_number = "PO number is required.";
  if (!form.customer.trim()) errors.customer = "Customer is required.";
  if (form.line_items.length === 0) errors.line_items = "At least one line item is required.";

  form.line_items.forEach((item, index) => {
    if (!item.quantity || item.quantity < 1) {
      errors[`line_items.${index}.quantity`] = "Quantity must be at least 1.";
    }
    if (item.unit_price < 0) {
      errors[`line_items.${index}.unit_price`] = "Unit price cannot be negative.";
    }
  });

  return { valid: Object.keys(errors).length === 0, errors };
}

export function lineItemTotal(quantity: number, unitPrice: number): number {
  return Math.round(quantity * unitPrice * 100) / 100;
}

export function calculateTotal(lineItems: EditableLineItem[]): number {
  return Math.round(
    lineItems.reduce((sum, item) => sum + lineItemTotal(item.quantity, item.unit_price), 0) * 100
  ) / 100;
}

export function hasLineItemChanges(
  original: EditableLineItem[],
  current: EditableLineItem[]
): boolean {
  if (original.length !== current.length) return true;
  return current.some((item, index) => {
    const base = original[index];
    if (!base) return true;
    return (
      item.quantity !== base.quantity ||
      item.unit_price !== base.unit_price ||
      item.product_name !== base.product_name ||
      item.sku !== base.sku
    );
  });
}
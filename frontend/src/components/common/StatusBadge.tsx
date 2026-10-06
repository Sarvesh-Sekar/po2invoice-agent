import type { BadgeProps, BadgeTone } from "@/components/ui/Badge";
import { Badge } from "@/components/ui/Badge";

const STATUS_TONES: Record<string, BadgeTone> = {
  // Purchase orders
  APPROVED: "green",
  REJECTED: "red",
  DRAFT: "gray",

  // Sales
  CREATED: "gray",
  CONFIRMED: "blue",
  PROCESSING: "indigo",
  SHIPPED: "purple",
  DELIVERED: "green",

  // Invoices
  GENERATED: "blue",
  SENT: "green",

  // GST
  REGISTERED: "green",
  GST_PROCESSING: "indigo",

  // Delivery
  PENDING: "amber",
  RETRY_DELIVERY: "red",

  // Agent runs
  QUEUED: "gray",
  RUNNING: "indigo",
  WAITING_FOR_HUMAN: "amber",
  COMPLETED: "green",
  FAILED: "red",

  // Verification
  PASS: "green",
  FAIL: "red",
};

function toneFor(status: string): BadgeTone {
  return STATUS_TONES[status] ?? "gray";
}

export interface StatusBadgeProps {
  status: string;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <Badge tone={toneFor(status)} className={className}>
      {label ?? status}
    </Badge>
  );
}

export type { BadgeProps };
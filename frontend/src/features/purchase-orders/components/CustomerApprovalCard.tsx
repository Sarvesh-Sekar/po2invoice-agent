import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import type { CreateCustomerContext } from "@/types/api";

export interface CustomerApprovalCardProps {
  context: CreateCustomerContext;
  pending?: boolean;
  onDecision: (
    decision: "APPROVE" | "EDIT" | "REJECT",
    options?: { changes?: Record<string, unknown>; reason?: string }
  ) => void;
}

export function CustomerApprovalCard({
  context,
  pending = false,
  onDecision,
}: CustomerApprovalCardProps) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(context.customer_name ?? "");
  const [code, setCode] = useState(context.customer_code ?? "");
  const [note, setNote] = useState("");

  function handleEditSubmit() {
    if (!name.trim()) return;
    onDecision("EDIT", {
      changes: {
        customer_name: name.trim(),
        customer_code: code.trim() || undefined,
      },
      reason: note || undefined,
    });
  }

  return (
    <div className="mx-auto max-w-2xl rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-gray-900">New customer detected</h2>
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Awaiting approval
        </span>
      </div>

      <p className="text-sm text-gray-600">{context.message}</p>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-gray-500">Customer name</dt>
          <dd className="mt-0.5 text-sm font-semibold text-gray-900">{context.customer_name}</dd>
        </div>
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-gray-500">GST number (from PO)</dt>
          <dd className="mt-0.5 text-sm font-semibold text-gray-900">
            {context.customer_gst_no || "—"}
          </dd>
        </div>
      </dl>

      {editing && (
        <div className="mt-4 space-y-3 rounded-md border border-indigo-200 bg-indigo-50/50 p-4">
          <Input
            label="Customer name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <Input
            label="Customer code (optional)"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            hint="Leave blank to auto-generate one."
          />
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <Button loading={pending} onClick={() => onDecision("APPROVE")} disabled={editing}>
          Create & continue
        </Button>
        {!editing ? (
          <Button variant="outline" onClick={() => setEditing(true)} disabled={pending}>
            Edit details
          </Button>
        ) : (
          <Button
            variant="success"
            onClick={handleEditSubmit}
            loading={pending}
            disabled={!name.trim()}
          >
            Create with these details
          </Button>
        )}
        <Button variant="danger" onClick={() => onDecision("REJECT")} disabled={pending}>
          Reject
        </Button>
      </div>

      <Textarea
        className="mt-4"
        rows={2}
        placeholder="Optional note for this decision"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
    </div>
  );
}

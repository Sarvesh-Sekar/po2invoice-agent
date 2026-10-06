import { StatusBadge } from "@/components/common/StatusBadge";
import type { VerificationIssue, VerificationPayload } from "@/types/api";
import { titleCase } from "@/lib/utils";

export interface VerificationPanelProps {
  issues: VerificationIssue[];
  verification?: VerificationPayload;
  aiConfidence?: number;
}

function severityTone(severity: string): "red" | "amber" {
  return severity === "error" ? "red" : "amber";
}

interface ChecklistItem {
  label: string;
  passed: boolean;
  detail?: string;
}

function buildChecklist(verification: VerificationPayload): ChecklistItem[] {
  return [
    {
      label: "Customer matched",
      passed: verification.customer_verified,
      detail: verification.customer_id ?? undefined,
    },
    {
      label: "Products verified",
      passed:
        verification.products_total > 0 &&
        verification.products_verified === verification.products_total,
      detail: `${verification.products_verified}/${verification.products_total}`,
    },
    {
      label: "Pricing validated",
      passed: !verification.issues.some((issue) => issue.code === "PRICE_VALIDATION_FAILED"),
    },
    {
      label: "Stock available",
      passed: !verification.issues.some((issue) => issue.code === "QUANTITY_VALIDATION_FAILED"),
    },
    {
      label: "Policy compliant",
      passed: !verification.issues.some((issue) => issue.code === "POLICY_VIOLATION"),
    },
  ];
}

export function VerificationPanel({ issues, verification, aiConfidence }: VerificationPanelProps) {
  const blockingIssues = issues.filter((issue) => issue.severity === "error");
  const warnings = issues.filter((issue) => issue.severity === "warning");
  const passed = blockingIssues.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">AI Verification</h3>
        <StatusBadge status={passed ? "PASS" : "FAIL"} label={passed ? "Passed" : "Needs review"} />
      </div>

      {typeof aiConfidence === "number" && (
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-500">AI confidence</p>
          <p className="text-sm font-semibold text-gray-900">
            {Math.round(aiConfidence * 100)}%
          </p>
        </div>
      )}

      {verification && (
        <ul className="space-y-2">
          {buildChecklist(verification).map((item) => (
            <li key={item.label} className="flex items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <span
                  className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] text-white ${
                    item.passed ? "bg-green-500" : "bg-red-500"
                  }`}
                >
                  {item.passed ? "✓" : "!"}
                </span>
                <span className="text-gray-700">{item.label}</span>
              </span>
              {item.detail && <span className="text-xs text-gray-400">{item.detail}</span>}
            </li>
          ))}
        </ul>
      )}

      {blockingIssues.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-600">
            Blocking issues
          </p>
          <ul className="space-y-2">
            {blockingIssues.map((issue, index) => (
              <li
                key={`${issue.code}-${index}`}
                className="rounded-md border border-red-200 bg-red-50 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-red-800">
                    {titleCase(issue.code)}
                  </span>
                  <StatusBadge status={issue.severity.toUpperCase()} label={issue.severity} />
                </div>
                <p className="mt-1 text-xs text-red-700">{issue.message}</p>
                {typeof issue.details?.catalogue_price === "number" && (
                  <p className="mt-1 text-xs text-red-600">
                    Catalogue {String(issue.details.catalogue_price)} · PO{" "}
                    {String(issue.details.unit_price ?? "")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-600">
            Warnings
          </p>
          <ul className="space-y-2">
            {warnings.map((issue, index) => (
              <li
                key={`${issue.code}-warn-${index}`}
                className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-amber-800">{titleCase(issue.code)}</span>
                  <StatusBadge status={severityTone(issue.severity).toUpperCase()} label={issue.severity} />
                </div>
                <p className="mt-1 text-xs text-amber-700">{issue.message}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {verification && verification.policy_applied.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Applied policies
          </p>
          <div className="flex flex-wrap gap-1">
            {verification.policy_applied.map((policy) => (
              <span
                key={policy}
                className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
              >
                {titleCase(policy.replace(/_/g, " "))}
              </span>
            ))}
          </div>
        </div>
      )}

      {issues.length === 0 && !verification && (
        <p className="text-sm text-gray-500">No verification issues reported.</p>
      )}
    </div>
  );
}
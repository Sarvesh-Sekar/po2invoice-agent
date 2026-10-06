import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { StatusBadge } from "@/components/common/StatusBadge";
import { AGENT_RUN_STATUSES } from "@/constants";
import { useAgentRun } from "@/features/ai-processing/hooks";
import { titleCase } from "@/lib/utils";

export function AiProcessingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("runId") ?? "";

  const [runIdInput, setRunIdInput] = useState(runId);
  const query = useAgentRun(runId || undefined);

  function lookUp() {
    if (!runIdInput.trim()) return;
    const next = new URLSearchParams();
    next.set("runId", runIdInput.trim());
    setSearchParams(next);
  }

  return (
    <div className="space-y-5">
      <PageHeader title="AI Processing" description="Inspect the status of agent workflow runs." />

      <div className="grid gap-3 sm:grid-cols-12">
        <div className="sm:col-span-8">
          <Input
            placeholder="Enter a run ID to inspect its workflow status"
            value={runIdInput}
            onChange={(event) => setRunIdInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") lookUp();
            }}
          />
        </div>
        <div className="flex items-end gap-2 sm:col-span-4">
          <Button size="md" onClick={lookUp} className="w-full">
            Inspect Run
          </Button>
        </div>
      </div>

      {!runId ? (
        <EmptyState
          title="No run selected"
          description="Enter a run ID above to track an agent workflow through its lifecycle."
        />
      ) : query.isLoading ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
          Loading run {runId}…
        </div>
      ) : query.isError ? (
        <ErrorState message="Unable to load the agent run." onRetry={() => query.refetch()} />
      ) : !query.data ? (
        <EmptyState title="Run not found" description="The run could not be located." />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Run ID</dt>
              <dd className="mt-1 font-mono text-sm text-gray-900">{query.data.run_id}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Workflow
              </dt>
              <dd className="mt-1 text-sm text-gray-900">{titleCase(query.data.workflow)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</dt>
              <dd className="mt-1">
                <StatusBadge status={query.data.status} label={titleCase(query.data.status)} />
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Current Step
              </dt>
              <dd className="mt-1 text-sm text-gray-900">
                {query.data.current_step ? titleCase(query.data.current_step) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Purchase Order
              </dt>
              <dd className="mt-1 font-mono text-sm text-gray-900">
                {query.data.po_id ? query.data.po_id.slice(0, 8) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Sale</dt>
              <dd className="mt-1 font-mono text-sm text-gray-900">
                {query.data.sale_id ? query.data.sale_id.slice(0, 8) : "—"}
              </dd>
            </div>
          </dl>

          {query.data.hitl ? (
            <div className="mt-6 rounded-md border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-medium text-amber-800">Awaiting human review</p>
              <p className="mt-1 text-sm text-amber-700">{query.data.hitl.message}</p>
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-1.5">
            {AGENT_RUN_STATUSES.map((statusValue) => (
              <span
                key={statusValue}
                className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  statusValue === query.data.status
                    ? "bg-indigo-100 text-indigo-700 ring-1 ring-inset ring-indigo-300"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {titleCase(statusValue)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

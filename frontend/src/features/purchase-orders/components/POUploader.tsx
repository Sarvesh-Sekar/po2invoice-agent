import { useCallback, useRef, useState } from "react";
import type { DragEvent } from "react";
import { Button } from "@/components/ui/Button";
import { useUploadPurchaseOrder, useAgentRun } from "@/features/purchase-orders/hooks";
import { validateFile } from "@/features/purchase-orders/schemas";
import { PO_ALLOWED_EXTENSIONS, PO_FILE_LIMIT_MB, ROUTES } from "@/constants";
import { useUploadStore } from "@/stores/uploadStore";
import type { StepperStep } from "@/stores/uploadStore";
import { cn } from "@/lib/utils";
import { useNavigate } from "react-router-dom";

const STEPS: Array<{ key: StepperStep; label: string }> = [
  { key: "upload", label: "Upload" },
  { key: "extract", label: "Extract" },
  { key: "verify", label: "Verify" },
  { key: "sale", label: "Sale" },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function stepFromRun(status: string | undefined, currentStep: string | null | undefined): StepperStep {
  if (!status) return "upload";
  if (status === "COMPLETED") return "sale";
  switch (currentStep) {
    case "queued":
      return "upload";
    case "extraction":
      return "extract";
    case "verification":
    case "criteria_evaluation":
    case "hitl":
    case "apply_edits":
      return "verify";
    case "sales":
      return "sale";
    default:
      return status === "WAITING_FOR_HUMAN" ? "verify" : "extract";
  }
}

export function POUploader() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const phase = useUploadStore((state) => state.phase);
  const file = useUploadStore((state) => state.file);
  const runId = useUploadStore((state) => state.runId);
  const activeStep = useUploadStore((state) => state.activeStep);
  const setPhase = useUploadStore((state) => state.setPhase);
  const setFile = useUploadStore((state) => state.setFile);
  const setRunId = useUploadStore((state) => state.setRunId);
  const setActiveStep = useUploadStore((state) => state.setActiveStep);
  const reset = useUploadStore((state) => state.reset);

  const uploadMutation = useUploadPurchaseOrder();
  const runQuery = useAgentRun(runId ?? undefined, { poll: true });

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const selected = files?.[0];
      if (!selected) return;
      const result = validateFile(selected);
      if (!result.valid) {
        setLocalError(result.errors.file ?? "Invalid file.");
        return;
      }
      setLocalError(null);
      uploadMutation.reset();
      setFile(selected);
      setPhase("SELECTED");
      setActiveStep("upload");
    },
    [setFile, setPhase, setActiveStep, uploadMutation]
  );

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragActive(false);
    handleFiles(event.dataTransfer.files);
  }

  async function startProcessing() {
    if (!file) return;
    setPhase("UPLOADING");
    setActiveStep("upload");
    try {
      const run = await uploadMutation.mutateAsync(file);
      setRunId(run.run_id);
      setActiveStep(stepFromRun(run.status, run.current_step));
      if (run.status === "WAITING_FOR_HUMAN") {
        setActiveStep("verify");
        setPhase("PROCESSING");
      } else if (run.status === "COMPLETED") {
        setActiveStep("sale");
        setPhase("COMPLETED");
      } else {
        setPhase("PROCESSING");
        setActiveStep("extract");
      }
    } catch {
      setPhase("FAILED");
      setLocalError("Upload failed. Please try again.");
    }
  }

  const run = runQuery.data;
  const effectiveStatus = run?.status ?? uploadMutation.data?.status;
  const effectiveStep = stepFromRun(effectiveStatus, run?.current_step);

  if (run?.status === "COMPLETED" && run.po_id) {
    return (
      <div className="space-y-5">
        <Stepper activeStep="sale" />
        <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
          <h3 className="text-base font-semibold text-green-800">Purchase order processed</h3>
          <p className="mt-1 text-sm text-green-700">
            The purchase order passed verification and a sale was created.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button onClick={() => navigate(`${ROUTES.PURCHASE_ORDERS}/${run.po_id}`)}>
              View purchase order
            </Button>
            <Button variant="secondary" onClick={reset}>
              Upload another
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (run?.status === "WAITING_FOR_HUMAN") {
    return (
      <div className="space-y-5">
        <Stepper activeStep="verify" />
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
          <h3 className="text-base font-semibold text-amber-900">Human review required</h3>
          <p className="mt-1 text-sm text-amber-800">
            The AI agent could not fully verify this purchase order. A reviewer must inspect and decide.
          </p>
          <div className="mt-4">
            <Button
              onClick={() => navigate(`${ROUTES.PURCHASE_ORDERS}/${runId}/review`)}
            >
              Open Human Review
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (run?.status === "FAILED") {
    return (
      <div className="space-y-5">
        <Stepper activeStep={effectiveStep} />
        <div className="rounded-lg border border-red-200 bg-red-50 p-6">
          <h3 className="text-base font-semibold text-red-800">Processing failed</h3>
          <p className="mt-1 text-sm text-red-700">
            The workflow could not complete. Please retry with a valid document.
          </p>
          <div className="mt-4">
            <Button variant="secondary" onClick={reset}>
              Try again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Stepper activeStep={phase === "PROCESSING" ? effectiveStep : activeStep} />

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border-2 border-dashed bg-white px-6 py-12 text-center transition-colors",
          dragActive ? "border-indigo-500 bg-indigo-50" : "border-gray-300"
        )}
      >
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-600">
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 7.5 7.5 12m4.5-4.5V21" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-900">
          Drag and drop your purchase order here
        </p>
        <p className="mt-1 text-xs text-gray-500">
          PDF, PNG, JPG and Excel · up to {PO_FILE_LIMIT_MB} MB
        </p>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => inputRef.current?.click()}>
            Browse files
          </Button>
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept={PO_ALLOWED_EXTENSIONS.join(",")}
            onChange={(event) => handleFiles(event.target.files)}
          />
        </div>
      </div>

      {(localError || uploadMutation.isError) && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {localError ?? "Upload failed. Please try again."}
        </div>
      )}

      {file && phase !== "PROCESSING" && phase !== "UPLOADING" && (
        <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-gray-100 text-xs font-semibold uppercase text-gray-500">
              {file.name.split(".").pop()}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">{formatBytes(file.size)}</p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button variant="ghost" size="sm" onClick={reset}>
              Remove
            </Button>
            <Button size="sm" loading={uploadMutation.isPending} onClick={startProcessing}>
              Process
            </Button>
          </div>
        </div>
      )}

      {(phase === "UPLOADING" || phase === "PROCESSING") && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="text-sm text-blue-800">
            {phase === "UPLOADING" ? "Uploading document…" : "AI agent is processing your purchase order…"}
          </p>
        </div>
      )}

      {phase === "PROCESSING" && run && (
        <div className="text-right">
          <Button variant="secondary" size="sm" onClick={reset}>
            Cancel
          </Button>
          <span className="ml-2 text-xs text-gray-400">Run {run.run_id.slice(0, 8)}</span>
        </div>
      )}
    </div>
  );
}

function Stepper({ activeStep }: { activeStep: StepperStep }) {
  const activeIndex = STEPS.findIndex((step) => step.key === activeStep);

  return (
    <ol className="flex items-center">
      {STEPS.map((step, index) => {
        const isComplete = index < activeIndex;
        const isActive = index === activeIndex;
        return (
          <li key={step.key} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
                  isComplete && "bg-green-500 text-white",
                  isActive && "bg-indigo-600 text-white",
                  !isComplete && !isActive && "bg-gray-200 text-gray-500"
                )}
              >
                {isComplete ? "✓" : index + 1}
              </span>
              <span
                className={cn(
                  "text-sm font-medium",
                  isActive ? "text-indigo-700" : isComplete ? "text-green-700" : "text-gray-400"
                )}
              >
                {step.label}
              </span>
            </div>
            {index < STEPS.length - 1 && (
              <span
                className={cn(
                  "mx-3 h-0.5 flex-1",
                  index < activeIndex ? "bg-green-400" : "bg-gray-200"
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
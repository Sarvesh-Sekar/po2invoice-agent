import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PageHeader } from "@/components/common/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingState } from "@/components/common/LoadingState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { CustomerApprovalCard } from "@/features/purchase-orders/components/CustomerApprovalCard";
import { ReviewDocumentPanel } from "@/features/purchase-orders/components/ReviewDocumentPanel";
import { ReviewEditorPanel } from "@/features/purchase-orders/components/ReviewEditorPanel";
import { VerificationPanel } from "@/features/purchase-orders/components/VerificationPanel";
import { useAgentRun, usePurchaseOrder, useSubmitDecision } from "@/features/purchase-orders/hooks";
import { calculateTotal, validatePurchaseOrderEdit } from "@/features/purchase-orders/schemas";
import { useReviewStore } from "@/stores/reviewStore";
import type { ReviewFormState } from "@/stores/reviewStore";
import { useUploadStore } from "@/stores/uploadStore";
import { useUIStore } from "@/stores/uiStore";
import { ROUTES } from "@/constants";
import type { CreateCustomerContext, HitlReviewContext, VerificationIssue } from "@/types/api";

function contextIssues(context: Record<string, unknown> | undefined): VerificationIssue[] {
  if (!context) return [];
  const issues = context.issues;
  return Array.isArray(issues) ? (issues as VerificationIssue[]) : [];
}

function toForm(
  po: ReturnType<typeof usePurchaseOrder>["data"],
  context: HitlReviewContext | null
): ReviewFormState {
  if (po) {
    return {
      po_number: po.po_number ?? "",
      customer: po.customer?.name ?? "",
      gst_no: po.customer?.gst_no ?? "",
      ship_to: po.ship_to ?? "",
      address_1: po.address_1 ?? "",
      address_2: po.address_2 ?? "",
      city: po.city ?? "",
      state: po.state ?? "",
      country: po.country ?? "",
      zip: po.zip ?? "",
      line_items: (po.line_items ?? []).map((item) => ({
        line_item_id: item.po_line_item_id,
        product_name: "",
        sku: "",
        quantity: item.quantity,
        unit_price: item.unit_price,
        total_price: item.total_price,
      })),
      total_amount: po.total_amount ?? 0,
    };
  }
  return {
    po_number: String(context?.po_number ?? ""),
    customer: String(context?.customer ?? ""),
    gst_no: "",
    ship_to: "",
    address_1: "",
    address_2: "",
    city: "",
    state: "",
    country: "",
    zip: "",
    line_items: [],
    total_amount: Number(context?.total_amount ?? 0),
  };
}

export function HumanReviewPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const uploadFile = useUploadStore((state) => state.file);
  const pushToast = useUIStore((state) => state.pushToast);

  const runQuery = useAgentRun(runId, { poll: true });
  const run = runQuery.data;
  const poQuery = usePurchaseOrder(run?.po_id ?? undefined);

  const form = useReviewStore((state) => state.form);
  const isEditMode = useReviewStore((state) => state.isEditMode);
  const auditorNote = useReviewStore((state) => state.auditorNote);
  const confirmAction = useReviewStore((state) => state.confirmAction);
  const setForm = useReviewStore((state) => state.setForm);
  const setIsEditMode = useReviewStore((state) => state.setIsEditMode);
  const setAuditorNote = useReviewStore((state) => state.setAuditorNote);
  const setConfirmAction = useReviewStore((state) => state.setConfirmAction);
  const setRunId = useReviewStore((state) => state.setRunId);
  const reset = useReviewStore((state) => state.reset);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const initializedRun = useRef<string | null>(null);

  const submitDecision = useSubmitDecision();

  useEffect(() => {
    setRunId(runId ?? null);
    return () => {
      reset();
    };
  }, [runId, setRunId, reset]);

  useEffect(() => {
    if (!run || !runId) return;
    const context = (run.hitl?.context ?? null) as HitlReviewContext | null;
    const key = `${runId}:${run.status}:${run.po_id ?? ""}`;
    if (initializedRun.current === key) return;
    if (run.po_id && !poQuery.data) return;
    initializedRun.current = key;
    setForm(toForm(poQuery.data, context));
    setIsEditMode(false);
  }, [run, runId, poQuery.data, setForm, setIsEditMode]);

  if (runQuery.isLoading) {
    return <LoadingState title="Loading workflow" description="Fetching the review context." />;
  }

  if (runQuery.isError || !run) {
    return (
      <ErrorState
        message="Unable to load the review workflow."
        onRetry={() => runQuery.refetch()}
      />
    );
  }

  if (run.status === "COMPLETED") {
    return (
      <div className="mx-auto max-w-xl space-y-4 py-10 text-center">
        <h2 className="text-lg font-semibold text-gray-900">Workflow completed</h2>
        <p className="text-sm text-gray-500">
          This purchase order has already been processed. No further human decision is required.
        </p>
        <div className="flex justify-center gap-2">
          {run.po_id && (
            <Button onClick={() => navigate(`${ROUTES.PURCHASE_ORDERS}/${run.po_id}`)}>
              View purchase order
            </Button>
          )}
          <Button variant="secondary" onClick={() => navigate(ROUTES.PURCHASE_ORDERS)}>
            Back to list
          </Button>
        </div>
      </div>
    );
  }

  if (run.status === "RUNNING" || run.status === "QUEUED") {
    return (
      <LoadingState
        title="AI agent is processing"
        description="Extraction and verification are in progress. This page updates automatically."
      />
    );
  }

  if (run.hitl?.question === "create_customer") {
    const createContext = (run.hitl?.context ?? null) as unknown as CreateCustomerContext | null;

    async function handleCustomerDecision(
      decision: "APPROVE" | "EDIT" | "REJECT",
      options?: { changes?: Record<string, unknown>; reason?: string }
    ) {
      if (!runId) return;
      try {
        const result = await submitDecision.mutateAsync({
          runId,
          payload: {
            decision,
            changes: decision === "EDIT" ? options?.changes : undefined,
            reason: options?.reason || undefined,
          },
        });
        initializedRun.current = null;
        setForm(null);

        if (decision === "REJECT") {
          pushToast("info", "Customer creation rejected. The workflow has ended.");
          navigate(ROUTES.PURCHASE_ORDERS);
          return;
        }
        if (result.sale_id) {
          pushToast("success", "Approved. A sale has been created.");
          navigate(`${ROUTES.SALES}/${result.sale_id}`);
        } else if (result.po_id) {
          pushToast("success", "Customer created. Purchase order in progress.");
          navigate(`${ROUTES.PURCHASE_ORDERS}/${result.po_id}`);
        } else {
          await runQuery.refetch();
        }
      } catch {
        // mutation hook already surfaces the error toast
      }
    }

    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <PageHeader
            title="Customer not found"
            description="No matching customer was found for this purchase order during extraction."
          />
          <Link to={ROUTES.PURCHASE_ORDERS}>
            <Button variant="ghost" size="sm">
              Back
            </Button>
          </Link>
        </div>
        {createContext ? (
          <CustomerApprovalCard
            context={createContext}
            pending={submitDecision.isPending}
            onDecision={handleCustomerDecision}
          />
        ) : (
          <ErrorState message="The review context is missing." onRetry={() => runQuery.refetch()} />
        )}
      </div>
    );
  }

  const context = (run.hitl?.context ?? null) as HitlReviewContext | null;
  const issues = contextIssues(run.hitl?.context);
  const activeForm = form ?? toForm(poQuery.data, context);

  function buildChanges(current: ReviewFormState): Record<string, unknown> {
    return {
      po_number: current.po_number,
      customer: current.customer,
      gst_no: current.gst_no,
      ship_to: current.ship_to,
      address_1: current.address_1,
      address_2: current.address_2,
      city: current.city,
      state: current.state,
      country: current.country,
      zip: current.zip,
      line_items: current.line_items.map((item) => ({
        product_name: item.product_name,
        sku: item.sku,
        quantity: item.quantity,
        unit_price: item.unit_price,
        total_price: item.total_price,
      })),
    };
  }

  async function handleDecision(decision: "APPROVE" | "REJECT" | "EDIT") {
    if (!runId) return;
    try {
      const result = await submitDecision.mutateAsync({
        runId,
        payload: {
          decision,
          changes: decision === "EDIT" ? buildChanges(activeForm) : undefined,
          reason: auditorNote || undefined,
        },
      });

      if (decision === "REJECT") {
        pushToast("info", "Purchase order rejected. The workflow has ended.");
        navigate(ROUTES.PURCHASE_ORDERS);
        return;
      }

      if (decision === "EDIT") {
        pushToast("info", "Changes submitted. Re-verification is in progress.");
        initializedRun.current = null;
        setForm(null);
        await runQuery.refetch();
        if (result.po_id) await poQuery.refetch();
        return;
      }

      if (result.sale_id) {
        pushToast("success", "Approved. A sale has been created.");
        navigate(`${ROUTES.SALES}/${result.sale_id}`);
      } else if (result.po_id) {
        pushToast("success", "Approved. Purchase order processed.");
        navigate(`${ROUTES.PURCHASE_ORDERS}/${result.po_id}`);
      } else {
        initializedRun.current = null;
        await runQuery.refetch();
      }
    } catch {
      // mutation hook already surfaces the error toast
    }
  }

  function handleEditClick() {
    if (!isEditMode) {
      setIsEditMode(true);
      return;
    }
    const validation = validatePurchaseOrderEdit({
      po_number: activeForm.po_number,
      customer: activeForm.customer,
      gst_no: activeForm.gst_no,
      ship_to: activeForm.ship_to,
      address_1: activeForm.address_1,
      city: activeForm.city,
      state: activeForm.state,
      country: activeForm.country,
      zip: activeForm.zip,
      line_items: activeForm.line_items,
    });
    setErrors(validation.errors);
    if (!validation.valid) return;
    void handleDecision("EDIT");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title={`Human Review · ${context?.po_number ?? "Purchase Order"}`}
          description="Review the extracted data and AI verification, then approve, reject or edit."
        />
        <div className="flex items-center gap-2">
          <Link to={ROUTES.PURCHASE_ORDERS}>
            <Button variant="ghost" size="sm">
              Back
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={handleEditClick}
            loading={submitDecision.isPending && isEditMode}
          >
            {isEditMode ? "Edit & Re-verify" : "Edit"}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setConfirmAction("reject")}
            disabled={submitDecision.isPending}
          >
            Reject
          </Button>
          <Button
            size="sm"
            onClick={() => setConfirmAction("approve")}
            loading={submitDecision.isPending}
            disabled={isEditMode}
          >
            Approve
          </Button>
        </div>
      </div>

      {isEditMode && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          Changes trigger re-verification by the AI agent. The workflow will resume only after the
          verifier evaluates the updated data.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ReviewDocumentPanel file={uploadFile} sourceFileUrl={poQuery.data?.source_file_url} />
        </div>
        <div className="lg:col-span-1">
          <ReviewEditorPanel
            form={activeForm}
            isEditMode={isEditMode}
            errors={errors}
            onChange={setForm}
          />
        </div>
        <div className="lg:col-span-1">
          <div className="flex h-full flex-col rounded-lg border border-gray-200 bg-white">
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              <VerificationPanel
                issues={issues}
                verification={poQuery.data?.verification}
                aiConfidence={poQuery.data?.ai_confidence}
              />
              <div>
                <label
                  htmlFor="auditor-note"
                  className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Auditor Notes
                </label>
                <Textarea
                  id="auditor-note"
                  rows={3}
                  placeholder="Add a note for this decision (optional)"
                  value={auditorNote}
                  onChange={(event) => setAuditorNote(event.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmAction === "reject"}
        title="Reject purchase order?"
        description="Rejecting ends the workflow. This action cannot be undone."
        confirmLabel="Reject"
        tone="danger"
        loading={submitDecision.isPending}
        onConfirm={() => {
          setConfirmAction(null);
          void handleDecision("REJECT");
        }}
        onCancel={() => setConfirmAction(null)}
      />

      <ConfirmDialog
        open={confirmAction === "approve"}
        title="Approve purchase order?"
        description="Approving resumes the workflow and creates a sale if it passes verification."
        confirmLabel="Approve"
        loading={submitDecision.isPending}
        onConfirm={() => {
          setConfirmAction(null);
          void handleDecision("APPROVE");
        }}
        onCancel={() => setConfirmAction(null)}
      />

      <p className="text-xs text-gray-400">
        Total on record: {calculateTotal(activeForm.line_items).toFixed(2)}
      </p>
    </div>
  );
}

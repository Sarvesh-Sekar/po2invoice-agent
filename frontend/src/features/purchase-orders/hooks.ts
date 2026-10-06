import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { purchaseOrderApi } from "@/features/purchase-orders/api";
import { queryKeys } from "@/lib/queryKeys";
import { workflowRefetchInterval } from "@/app/query-client";
import { useUIStore } from "@/stores/uiStore";
import type {
  HITLDecisionRequest,
  POLineItemUpdate,
  PurchaseOrderFilters,
  PurchaseOrderUpdate,
} from "@/types/api";

export function usePurchaseOrders(filters: PurchaseOrderFilters) {
  return useQuery({
    queryKey: queryKeys.purchaseOrders.list(filters),
    queryFn: () => purchaseOrderApi.getPurchaseOrders(filters),
    placeholderData: (previous) => previous,
  });
}

export function usePurchaseOrder(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.purchaseOrders.detail(id ?? ""),
    queryFn: () => purchaseOrderApi.getPurchaseOrder(id as string),
    enabled: Boolean(id),
  });
}

export function usePOLineItems(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.purchaseOrders.lineItems(id ?? ""),
    queryFn: () => purchaseOrderApi.getLineItems(id as string),
    enabled: Boolean(id),
  });
}

export function usePurchaseOrderHistory(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.purchaseOrders.history(id ?? ""),
    queryFn: () => purchaseOrderApi.getHistory(id as string),
    enabled: Boolean(id),
  });
}

export function useAgentRun(runId: string | undefined, options?: { poll?: boolean }) {
  return useQuery({
    queryKey: queryKeys.agentRuns.detail(runId ?? ""),
    queryFn: () => purchaseOrderApi.getRun(runId as string),
    enabled: Boolean(runId),
    refetchInterval: options?.poll
      ? (query) => workflowRefetchInterval(query.state.data?.status)
      : false,
  });
}

export function useUpdatePurchaseOrder() {
  const queryClient = useQueryClient();
  const pushToast = useUIStore((state) => state.pushToast);

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: PurchaseOrderUpdate }) =>
      purchaseOrderApi.updatePurchaseOrder(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.purchaseOrders.all });
      pushToast("success", "Purchase order updated.");
    },
    onError: () => pushToast("error", "Unable to update purchase order."),
  });
}

export function useUpdateLineItem() {
  const queryClient = useQueryClient();
  const pushToast = useUIStore((state) => state.pushToast);

  return useMutation({
    mutationFn: ({
      poId,
      lineItemId,
      payload,
    }: {
      poId: string;
      lineItemId: string;
      payload: POLineItemUpdate;
    }) => purchaseOrderApi.updateLineItem(poId, lineItemId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.purchaseOrders.detail(variables.poId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.purchaseOrders.lineItems(variables.poId),
      });
    },
    onError: () => pushToast("error", "Unable to update line item."),
  });
}

export function useSubmitDecision() {
  const queryClient = useQueryClient();
  const pushToast = useUIStore((state) => state.pushToast);

  return useMutation({
    mutationFn: ({ runId, payload }: { runId: string; payload: HITLDecisionRequest }) =>
      purchaseOrderApi.submitDecision(runId, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.agentRuns.detail(data.run_id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.agentRuns.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.purchaseOrders.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.sales.all });
      pushToast("success", "Decision submitted.");
    },
    onError: () => pushToast("error", "Unable to submit decision."),
  });
}

export function useUploadPurchaseOrder() {
  const queryClient = useQueryClient();
  const pushToast = useUIStore((state) => state.pushToast);

  return useMutation({
    mutationFn: (file: File) => purchaseOrderApi.uploadAndProcess(file),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.agentRuns.detail(data.run_id), data);
      queryClient.invalidateQueries({ queryKey: queryKeys.purchaseOrders.all });
    },
    onError: () => {
      pushToast("error", "Upload failed. Please try again.");
    },
  });
}
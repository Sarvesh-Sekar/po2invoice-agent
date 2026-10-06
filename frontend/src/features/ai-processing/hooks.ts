import { useQuery } from "@tanstack/react-query";
import { agentRunApi } from "@/features/ai-processing/api";
import { queryKeys } from "@/lib/queryKeys";
import { workflowRefetchInterval } from "@/app/query-client";

export function useAgentRun(runId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.agentRuns.detail(runId ?? ""),
    queryFn: () => agentRunApi.getRun(runId as string),
    enabled: Boolean(runId),
    refetchInterval: (query) => workflowRefetchInterval(query.state.data?.status),
  });
}

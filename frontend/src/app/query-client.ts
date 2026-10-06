import { QueryClient } from "@tanstack/react-query";
import { isTerminalAgentStatus } from "@/lib/utils";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});

const POLL_INTERVAL_MS = 2_000;

export function workflowRefetchInterval(status: string | undefined): number | false {
  if (!status || isTerminalAgentStatus(status) || status === "WAITING_FOR_HUMAN") return false;
  return POLL_INTERVAL_MS;
}
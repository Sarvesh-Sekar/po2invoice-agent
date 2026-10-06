import { pythonHttpClient } from "@/lib/httpClient";
import type { AgentRun } from "@/types/api";

export const agentRunApi = {
  async getRun(runId: string): Promise<AgentRun> {
    return pythonHttpClient.get<AgentRun>(`/agents/runs/${runId}`);
  },
};

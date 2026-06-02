import type { AgentOutput, FunnelSummary, LLMAnalysisData, RecommendationsData } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  funnel: () => get<FunnelSummary>("/funnel"),
  recommendations: () => get<{ data: RecommendationsData } & AgentOutput<RecommendationsData>>("/recommendations"),
  llmAnalysis: () => get<{ data: LLMAnalysisData } & AgentOutput<LLMAnalysisData>>("/agents/llm_analysis"),
  agent: (name: string) => get<AgentOutput>(`/agents/${name}`),
  agents: () => get<{ agents: Record<string, { run: boolean; modified: number | null }> }>("/agents"),
  run: (demo = true) =>
    fetch(`${BASE}/run?demo=${demo}`, { method: "POST" }).then((r) => r.json()),
};

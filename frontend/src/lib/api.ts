import type { AgentOutput, BacktestData, FunnelSummary, LLMAnalysisData, RecommendationsData } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  funnel:        () => get<FunnelSummary>("/funnel"),
  recommendations: () => get<{ data: RecommendationsData } & AgentOutput<RecommendationsData>>("/recommendations"),
  llmAnalysis:   () => get<{ data: LLMAnalysisData } & AgentOutput<LLMAnalysisData>>("/agents/llm_analysis"),
  analyst:       () => get<AgentOutput>("/agents/analyst"),
  secFilings:    () => get<AgentOutput>("/agents/sec_filings"),
  backtest:      () => get<{ data: BacktestData } & AgentOutput<BacktestData>>("/agents/backtest"),
  agent:         (name: string) => get<AgentOutput>(`/agents/${name}`),
  agents:        () => get<{ agents: Record<string, { run: boolean; modified: number | null }> }>("/agents"),
  econConfig:    () => get<{ snapshot: Record<string, number | string | null>; regime_override: string | null }>("/config/economy"),
  setEconConfig: (payload: Record<string, number | string>) =>
    fetch(`${BASE}/config/economy`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(r => r.json()),
  run: (demo = true) =>
    fetch(`${BASE}/run?demo=${demo}`, { method: "POST" }).then((r) => r.json()),
  runStatus: () => get<{ running: boolean; started_at: string | null; finished_at: string | null; error: string | null }>("/run/status"),
  runBacktest: (demo = true) =>
    fetch(`${BASE}/run/backtest?demo=${demo}`, { method: "POST" }).then((r) => r.json()),
  backtestRunStatus: () => get<{ running: boolean; started_at: string | null; finished_at: string | null; error: string | null }>("/run/backtest/status"),
  liveMacro: () => get<{ values: Record<string, number>; source: Record<string, string>; has_fred_key: boolean; note?: string; error?: string }>("/live/macro"),
  assumptions: () => get<Record<string, unknown>>("/config/assumptions"),
  setAssumptions: (payload: Record<string, unknown>) =>
    fetch(`${BASE}/config/assumptions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }).then(r => r.json()),
};

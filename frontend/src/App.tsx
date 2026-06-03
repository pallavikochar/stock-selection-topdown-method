import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./lib/api";
import { TopDownFunnel } from "./components/TopDownFunnel";
import { InvestmentClock } from "./components/InvestmentClock";
import { HopeStrip } from "./components/HopeStrip";
import { SectorHeatmap } from "./components/SectorHeatmap";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { RecommendationsTable } from "./components/RecommendationsTable";
import { EconomyPanel } from "./components/EconomyPanel";
import { BacktestResults } from "./components/BacktestResults";
import { AssumptionsPanel } from "./components/AssumptionsPanel";
import type {
  AnalystConsensus, BacktestData, CycleData, EconomyData,
  LLMAnalysisData, SECFilingsData, SectorScore, Scenario, StockRecommendation,
} from "./lib/types";

type ActivePanel = "economy" | "cycle" | "scenarios" | "sector" | "style" | "screen" | "fundamental" | "recommendations" | null;

export default function App() {
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [runTriggered, setRunTriggered] = useState(false);
  const qc = useQueryClient();

  const { data: runStatus } = useQuery({
    queryKey: ["runStatus"],
    queryFn: api.runStatus,
    refetchInterval: runTriggered ? 2000 : false,
  });

  const isRunning = runStatus?.running ?? false;

  const [justFinished, setJustFinished] = useState(false);

  useEffect(() => {
    if (runTriggered && !isRunning && runStatus?.finished_at) {
      setRunTriggered(false);
      qc.invalidateQueries();
      setJustFinished(true);
      setTimeout(() => setJustFinished(false), 5000);
    }
  }, [isRunning, runTriggered, runStatus?.finished_at, qc]);

  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.funnel,
  });

  const hasData = !!funnel && Object.keys(funnel.funnel).length > 0;

  const { data: economyRaw } = useQuery({
    queryKey: ["agent", "economy"],
    queryFn: () => api.agent("economy"),
    enabled: hasData,
  });

  const { data: cycleRaw } = useQuery({
    queryKey: ["agent", "cycle"],
    queryFn: () => api.agent("cycle"),
    enabled: hasData,
  });

  const { data: sectorRaw } = useQuery({
    queryKey: ["agent", "sector"],
    queryFn: () => api.agent("sector"),
    enabled: hasData,
  });

  const { data: scenarioRaw } = useQuery({
    queryKey: ["agent", "scenario"],
    queryFn: () => api.agent("scenario"),
    enabled: hasData,
  });

  const { data: recsRaw } = useQuery({
    queryKey: ["recommendations"],
    queryFn: api.recommendations,
    enabled: hasData,
  });

  const { data: llmRaw } = useQuery({
    queryKey: ["llm_analysis"],
    queryFn: api.llmAnalysis,
    enabled: hasData,
  });

  const { data: analystRaw } = useQuery({
    queryKey: ["analyst"],
    queryFn: api.analyst,
    enabled: hasData,
  });

  const { data: secRaw } = useQuery({
    queryKey: ["sec_filings"],
    queryFn: api.secFilings,
    enabled: hasData,
  });

  const { data: backtestRaw } = useQuery({
    queryKey: ["backtest"],
    queryFn: api.backtest,
    enabled: hasData,
  });

  const handleRun = async () => {
    if (isRunning) return;
    setRunTriggered(true);
    await api.run(true);
  };

  const economy     = economyRaw?.data as EconomyData | undefined;
  const cycle       = cycleRaw?.data  as CycleData   | undefined;
  const sectorData  = sectorRaw?.data  as { ranked_sectors: SectorScore[]; favored: string[]; unfavored: string[] } | undefined;
  const scenarioData= scenarioRaw?.data as { scenarios: Scenario[] } | undefined;
  const recsData    = recsRaw?.data    as { ranked: StockRecommendation[] } | undefined;
  const llmData     = llmRaw?.data     as LLMAnalysisData | undefined;
  const analystData = analystRaw?.data as Record<string, AnalystConsensus> | undefined;
  const secData     = secRaw?.data     as Record<string, SECFilingsData>   | undefined;
  const backtestData= backtestRaw?.data as BacktestData | undefined;

  return (
    <div className="min-h-screen relative z-10">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-navy-800/60 bg-navy-950/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-cyan-accent animate-pulse" />
              <span className="font-display font-700 text-lg tracking-tight text-white">Project APM</span>
              <span className="text-navy-500 text-sm">·</span>
              <span className="text-navy-500 text-sm font-mono">Top-Down Process</span>
            </div>
            <p className="text-xs text-navy-500 mt-0.5 ml-5">
              From the economy down to the stock — macro explains ~70% of the move
              <span className="ml-3 text-navy-600">· Pallavi Kochar</span>
            </p>
          </div>
          <div className="flex items-center gap-4">
            {funnel?.as_of_date && (
              <span className="text-xs text-navy-500 font-mono">{funnel.as_of_date}</span>
            )}
            <button
              onClick={handleRun}
              disabled={isRunning}
              className={`px-4 py-2 text-sm font-600 rounded-lg border transition-colors flex items-center gap-2 ${
                isRunning
                  ? "border-amber-accent/30 bg-amber-accent/10 text-amber-accent cursor-not-allowed"
                  : "border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent hover:bg-cyan-accent/20"
              }`}
            >
              {isRunning ? (
                <>
                  <span className="w-3 h-3 border-2 border-amber-accent/40 border-t-amber-accent rounded-full animate-spin" />
                  Running Pipeline…
                </>
              ) : "▶ Run Analysis"}
            </button>
          </div>
        </div>
      </header>

      {/* Run status banners */}
      {isRunning && (
        <div className="sticky top-[65px] z-40 bg-amber-accent/10 border-b border-amber-accent/30 text-amber-accent text-xs font-600 text-center py-2 flex items-center justify-center gap-2">
          <span className="w-3 h-3 border-2 border-amber-accent/40 border-t-amber-accent rounded-full animate-spin" />
          Pipeline running — results will refresh automatically when complete
        </div>
      )}
      {justFinished && !isRunning && (
        <div className="sticky top-[65px] z-40 bg-green-signal/10 border-b border-green-signal/30 text-green-signal text-xs font-600 text-center py-2">
          ✓ Pipeline complete — all outputs refreshed
        </div>
      )}

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {funnelLoading && (
          <div className="flex items-center justify-center py-24 text-navy-500">
            <div className="text-center space-y-3">
              <div className="w-8 h-8 border-2 border-cyan-accent/30 border-t-cyan-accent rounded-full animate-spin mx-auto" />
              <p className="text-sm font-mono">Loading pipeline outputs…</p>
              <p className="text-xs">Run <code className="text-cyan-accent">python -m apm run --demo</code> first</p>
            </div>
          </div>
        )}

        {!funnelLoading && !hasData && (
          <div className="text-center py-24 space-y-4">
            <div className="text-5xl">⚡</div>
            <h2 className="text-xl font-600 text-white">No pipeline data found</h2>
            <p className="text-navy-500 text-sm">
              Run <code className="font-mono text-cyan-accent bg-navy-800 px-2 py-0.5 rounded">python -m apm run --demo</code> to generate demo outputs
            </p>
            <button
              onClick={handleRun}
              disabled={isRunning}
              className="mt-4 px-6 py-3 bg-cyan-accent text-navy-950 font-600 rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2 mx-auto"
            >
              {isRunning ? (
                <><span className="w-4 h-4 border-2 border-navy-950/30 border-t-navy-950 rounded-full animate-spin" />Running…</>
              ) : "Run Demo Pipeline"}
            </button>
          </div>
        )}

        {!funnelLoading && hasData && (
          <>
            {/* ① Final Recommendations — top of page */}
            {recsData && (
              <section className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">Final Recommendations</h3>
                  {recsData.ranked.length > 0 && (
                    <div className="flex gap-2 text-xs text-navy-500">
                      <span className="text-green-signal font-600">{recsData.ranked.filter(r => r.action === "Buy").length} Buy</span>
                      <span>·</span>
                      <span className="text-amber-accent font-600">{recsData.ranked.filter(r => r.action === "Hold").length} Hold</span>
                      <span>·</span>
                      <span className="text-red-signal font-600">{recsData.ranked.filter(r => r.action === "Sell").length} Sell</span>
                    </div>
                  )}
                </div>
                <RecommendationsTable
                  recommendations={recsData.ranked}
                  llmAnalysis={llmData}
                  analystData={analystData}
                  secFilings={secData}
                />
              </section>
            )}

            {/* ② Top-Down Funnel */}
            <section>
              <TopDownFunnel
                funnel={funnel.funnel}
                economy={economy}
                cycle={cycle}
                activePanel={activePanel}
                onSelectPanel={setActivePanel}
              />
            </section>

            {/* ③ Economy macro dashboard */}
            <section>
              <EconomyPanel />
            </section>

            {/* ④ Investment Clock + H.O.P.E. */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {cycle && (
                <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                  <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-4">Investment Clock</h3>
                  <InvestmentClock phase={cycle.clock_phase} />
                </div>
              )}
              {cycle && (
                <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                  <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-4">H.O.P.E. Transmission</h3>
                  <HopeStrip
                    currentStage={cycle.hope_stage}
                    nextStage={cycle.hope_next_stage}
                    inflecting={cycle.hope_inflecting_indicators}
                  />
                </div>
              )}
            </section>

            {/* ⑤ Scenarios + Sectors */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {scenarioData && (
                <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                  <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-4">Scenarios</h3>
                  <ScenarioPanel scenarios={scenarioData.scenarios} />
                </div>
              )}
              {sectorData && (
                <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                  <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-4">Sector Heatmap</h3>
                  <SectorHeatmap sectors={sectorData.ranked_sectors} />
                </div>
              )}
            </section>

            {/* ⑥ Model Assumptions */}
            <section>
              <AssumptionsPanel />
            </section>

            {/* ⑦ 10-Year Backtest */}
            {backtestData && (
              <section className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">10-Year Sector Rotation Backtest</h3>
                    <p className="text-xs text-navy-600 mt-0.5">{backtestData.strategy_name}</p>
                  </div>
                  <div className="flex gap-4 text-xs font-mono">
                    <span className="text-green-signal font-600">{backtestData.metrics.cagr_pct.toFixed(1)}% CAGR</span>
                    <span className="text-navy-500">/</span>
                    <span className="text-cyan-accent font-600">+{backtestData.metrics.alpha_pct.toFixed(1)}% α</span>
                  </div>
                </div>
                <BacktestResults data={backtestData} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

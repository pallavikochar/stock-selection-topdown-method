import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";
import { TopDownFunnel } from "./components/TopDownFunnel";
import { InvestmentClock } from "./components/InvestmentClock";
import { HopeStrip } from "./components/HopeStrip";
import { SectorHeatmap } from "./components/SectorHeatmap";
import { ScenarioPanel } from "./components/ScenarioPanel";
import { RecommendationsTable } from "./components/RecommendationsTable";
import type { CycleData, EconomyData, SectorScore, Scenario, StockRecommendation } from "./lib/types";

type ActivePanel = "economy" | "cycle" | "scenarios" | "sectors" | "styles" | "screen" | "stocks" | "recommendations" | null;

export default function App() {
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);

  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.funnel,
  });

  const { data: economyRaw } = useQuery({
    queryKey: ["agent", "economy"],
    queryFn: () => api.agent("economy"),
    enabled: !!funnel?.funnel.economy?.confidence,
  });

  const { data: cycleRaw } = useQuery({
    queryKey: ["agent", "cycle"],
    queryFn: () => api.agent("cycle"),
    enabled: !!funnel?.funnel.cycle?.confidence,
  });

  const { data: sectorRaw } = useQuery({
    queryKey: ["agent", "sector"],
    queryFn: () => api.agent("sector"),
    enabled: !!funnel?.funnel.sector?.confidence,
  });

  const { data: scenarioRaw } = useQuery({
    queryKey: ["agent", "scenario"],
    queryFn: () => api.agent("scenario"),
    enabled: !!funnel?.funnel.scenario?.confidence,
  });

  const { data: recsRaw } = useQuery({
    queryKey: ["recommendations"],
    queryFn: api.recommendations,
    enabled: !!funnel?.funnel.recommendations?.confidence,
  });

  const handleRun = async () => {
    await api.run(true);
    setTimeout(() => window.location.reload(), 3000);
  };

  const economy = economyRaw?.data as EconomyData | undefined;
  const cycle = cycleRaw?.data as CycleData | undefined;
  const sectorData = sectorRaw?.data as { ranked_sectors: SectorScore[]; favored: string[]; unfavored: string[] } | undefined;
  const scenarioData = scenarioRaw?.data as { scenarios: Scenario[] } | undefined;
  const recsData = recsRaw?.data as { ranked: StockRecommendation[] } | undefined;

  const hasData = !!funnel && Object.keys(funnel.funnel).length > 0;

  return (
    <div className="min-h-screen relative z-10">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-navy-800/60 bg-navy-950/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-cyan-accent animate-pulse" />
              <span className="font-display font-700 text-lg tracking-tight text-white">
                Project APM
              </span>
              <span className="text-navy-500 text-sm">·</span>
              <span className="text-navy-500 text-sm font-mono">Top-Down Process</span>
            </div>
            <p className="text-xs text-navy-500 mt-0.5 ml-5">
              From the economy down to the stock — macro explains ~70% of the move
            </p>
          </div>
          <div className="flex items-center gap-4">
            {funnel?.as_of_date && (
              <span className="text-xs text-navy-500 font-mono">
                {funnel.as_of_date}
              </span>
            )}
            <button
              onClick={handleRun}
              className="px-4 py-2 text-sm font-600 rounded-lg border border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent hover:bg-cyan-accent/20 transition-colors"
            >
              ▶ Run Analysis
            </button>
          </div>
        </div>
      </header>

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
            <button onClick={handleRun} className="mt-4 px-6 py-3 bg-cyan-accent text-navy-950 font-600 rounded-lg hover:opacity-90 transition-opacity">
              Run Demo Pipeline
            </button>
          </div>
        )}

        {!funnelLoading && hasData && (
          <>
            {/* Top-Down Funnel — hero */}
            <section>
              <TopDownFunnel
                funnel={funnel.funnel}
                economy={economy}
                cycle={cycle}
                activePanel={activePanel}
                onSelectPanel={setActivePanel}
              />
            </section>

            {/* Investment Clock + H.O.P.E. Strip */}
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

            {/* Scenarios + Sectors */}
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

            {/* Recommendations */}
            {recsData && (
              <section className="bg-navy-900 rounded-xl border border-navy-800 p-6">
                <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-4">Final Recommendations</h3>
                <RecommendationsTable recommendations={recsData.ranked} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

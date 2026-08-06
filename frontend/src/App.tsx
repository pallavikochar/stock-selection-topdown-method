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
import { Portfolio } from "./components/Portfolio";
import { TickerSearch } from "./components/TickerSearch";
import { ProfilePage } from "./components/ProfilePage";
import { RagPanel, RagIngestionBadge } from "./components/RagPanel";
import { StyleFactorPanel } from "./components/StyleFactorPanel";
import type {
  AgentOutput, AnalystConsensus, BacktestData, CycleData, EconomyData,
  FundamentalProfile, LLMAnalysisData, SECFilingsData, SectorScore, Scenario, StockRecommendation, StyleData,
} from "./lib/types";

type Tab = "analysis" | "portfolio" | "profile";
type ActivePanel = "economy" | "cycle" | "scenarios" | "sector" | "style" | "screen" | "fundamental" | "recommendations" | null;

const PROCESS_STEPS = [
  { num: "01", key: "economy",         label: "Economy",         anchor: "sec-economy"   },
  { num: "02", key: "cycle",           label: "Cycle",           anchor: "sec-cycle"     },
  { num: "03", key: "scenario",        label: "Scenarios",       anchor: "sec-scenarios" },
  { num: "04", key: "sector",          label: "Sectors",         anchor: "sec-sectors"   },
  { num: "05", key: "style",           label: "Style",           anchor: "sec-style"     },
  { num: "06", key: "screen",          label: "Pipeline",        anchor: "sec-pipeline"  },
  { num: "07", key: "recommendations", label: "Recs",            anchor: "sec-recs"      },
] as const;

function SectionHeader({
  num, title, subtitle, funnelLayer,
}: {
  num: string;
  title: string;
  subtitle: string;
  funnelLayer?: { confidence: number; confidence_label: string; warnings: string[] };
}) {
  const conf = funnelLayer?.confidence_label;
  const badge =
    conf === "High"   ? "text-green-signal  border-green-signal/30  bg-green-signal/8"   :
    conf === "Medium" ? "text-cyan-accent   border-cyan-accent/30   bg-cyan-accent/8"    :
    conf === "Low"    ? "text-red-signal    border-red-signal/30    bg-red-signal/8"     : "";

  return (
    <div className="relative mb-12 overflow-visible">
      {/* Giant watermark number */}
      <span
        className="absolute -top-10 -left-2 font-mono font-700 select-none pointer-events-none text-white/[0.025] leading-none"
        style={{ fontSize: "9rem" }}
      >
        {num}
      </span>

      <div className="relative z-10">
        <div className="flex items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-2.5 mb-3">
              <span className="text-[10px] font-mono text-cyan-accent tracking-[0.3em] uppercase">{num}</span>
              <div className="h-px w-12 bg-cyan-accent/40" />
            </div>
            <h2 className="text-3xl font-700 text-white tracking-tight leading-none">{title}</h2>
            <p className="text-sm text-navy-500 mt-2.5 leading-relaxed max-w-2xl">{subtitle}</p>
          </div>

          {funnelLayer && (
            <div className="shrink-0 flex flex-col items-end gap-1.5 pb-1">
              {funnelLayer.warnings.length > 0 && (
                <span className="text-amber-accent text-xs font-mono">⚠ {funnelLayer.warnings.length} flag{funnelLayer.warnings.length > 1 ? "s" : ""}</span>
              )}
              <span className={`text-xs font-mono px-3 py-1 rounded border font-600 tracking-wide ${badge}`}>
                {conf} · {funnelLayer.confidence.toFixed(0)}
              </span>
            </div>
          )}
        </div>

        {/* Gold gradient rule */}
        <div className="mt-5 section-rule" />
      </div>
    </div>
  );
}

const TABS: { id: Tab; label: string }[] = [
  { id: "analysis",  label: "Top-Down Analysis" },
  { id: "portfolio", label: "My Portfolio" },
  { id: "profile",   label: "Profile" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("analysis");
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [runTriggered, setRunTriggered] = useState(false);
  const [backtestTriggered, setBacktestTriggered] = useState(false);
  const qc = useQueryClient();

  const { data: runStatus } = useQuery({
    queryKey: ["runStatus"],
    queryFn: api.runStatus,
    refetchInterval: runTriggered ? 2000 : false,
  });

  const { data: backtestRunStatus } = useQuery({
    queryKey: ["backtestRunStatus"],
    queryFn: api.backtestRunStatus,
    refetchInterval: backtestTriggered ? 2000 : false,
  });

  const isRunning = runStatus?.running ?? false;
  const isBacktestRunning = backtestRunStatus?.running ?? false;

  const [justFinished, setJustFinished] = useState(false);
  const [backtestJustFinished, setBacktestJustFinished] = useState(false);

  const [prevRunFinishedAt, setPrevRunFinishedAt] = useState<string | null | undefined>(undefined);
  const [prevBacktestFinishedAt, setPrevBacktestFinishedAt] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    if (
      runTriggered &&
      !isRunning &&
      runStatus?.finished_at !== undefined &&
      runStatus?.finished_at !== prevRunFinishedAt
    ) {
      setRunTriggered(false);
      qc.invalidateQueries();
      setJustFinished(true);
      setTimeout(() => setJustFinished(false), 5000);
    }
  }, [isRunning, runTriggered, runStatus?.finished_at, prevRunFinishedAt, qc]);

  useEffect(() => {
    if (
      backtestTriggered &&
      !isBacktestRunning &&
      backtestRunStatus?.finished_at !== undefined &&
      backtestRunStatus?.finished_at !== prevBacktestFinishedAt
    ) {
      setBacktestTriggered(false);
      qc.invalidateQueries({ queryKey: ["backtest"] });
      setBacktestJustFinished(true);
      setTimeout(() => setBacktestJustFinished(false), 5000);
    }
  }, [isBacktestRunning, backtestTriggered, backtestRunStatus?.finished_at, prevBacktestFinishedAt, qc]);

  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.funnel,
  });

  const hasData = !!funnel && Object.keys(funnel.funnel).length > 0;

  const { data: economyRaw }  = useQuery({ queryKey: ["agent", "economy"],   queryFn: () => api.agent("economy"),   enabled: hasData });
  const { data: cycleRaw }    = useQuery({ queryKey: ["agent", "cycle"],     queryFn: () => api.agent("cycle"),     enabled: hasData });
  const { data: sectorRaw }   = useQuery({ queryKey: ["agent", "sector"],    queryFn: () => api.agent("sector"),    enabled: hasData });
  const { data: scenarioRaw } = useQuery({ queryKey: ["agent", "scenario"],  queryFn: () => api.agent("scenario"),  enabled: hasData });
  const { data: recsRaw }     = useQuery({ queryKey: ["recommendations"],    queryFn: api.recommendations,          enabled: hasData });
  const { data: llmRaw }      = useQuery({ queryKey: ["llm_analysis"],       queryFn: api.llmAnalysis,              enabled: hasData });
  const { data: analystRaw }  = useQuery({ queryKey: ["analyst"],            queryFn: api.analyst,                  enabled: hasData });
  const { data: secRaw }      = useQuery({ queryKey: ["sec_filings"],        queryFn: api.secFilings,               enabled: hasData });
  const { data: styleRaw }       = useQuery({ queryKey: ["agent", "style"],       queryFn: () => api.agent("style"),       enabled: hasData });
  const { data: fundamentalRaw } = useQuery({ queryKey: ["agent", "fundamental"], queryFn: () => api.agent("fundamental"), enabled: hasData });
  const { data: backtestRaw } = useQuery({ queryKey: ["backtest"],           queryFn: api.backtest,                 enabled: hasData });

  const handleRun = async () => {
    if (isRunning) return;
    setPrevRunFinishedAt(runStatus?.finished_at);
    setRunTriggered(true);
    await api.run(true);
  };

  const handleRerunBacktest = async () => {
    if (isBacktestRunning || isRunning) return;
    setPrevBacktestFinishedAt(backtestRunStatus?.finished_at);
    setBacktestTriggered(true);
    await api.runBacktest(false);
  };

  const economy      = economyRaw?.data  as EconomyData | undefined;
  const cycle        = cycleRaw?.data    as CycleData   | undefined;
  const sectorData   = sectorRaw?.data   as { ranked_sectors: SectorScore[]; favored: string[]; unfavored: string[] } | undefined;
  const scenarioData = scenarioRaw?.data as { scenarios: Scenario[] } | undefined;
  const recsData     = recsRaw?.data     as { ranked: StockRecommendation[] } | undefined;
  const llmData      = llmRaw?.data      as LLMAnalysisData | undefined;
  const analystData  = analystRaw?.data  as Record<string, AnalystConsensus> | undefined;
  const secData      = secRaw?.data      as Record<string, SECFilingsData>   | undefined;
  const styleOutput      = styleRaw       as AgentOutput<StyleData>                         | undefined;
  const fundamentalData  = fundamentalRaw?.data as Record<string, FundamentalProfile>       | undefined;
  const backtestData = backtestRaw?.data as BacktestData | undefined;

  return (
    <div className="min-h-screen relative z-10">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-navy-950/98 backdrop-blur-md border-b border-navy-700/40">
        {/* Brand row */}
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-5">
            {/* Logo mark */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-cyan-accent flex items-center justify-center shrink-0">
                <span
                  className="font-mono font-700 leading-none text-navy-950"
                  style={{ fontSize: "9px", letterSpacing: "0.05em" }}
                >
                  APM
                </span>
              </div>
              <div className="flex flex-col leading-tight">
                <span className="font-700 text-sm text-white tracking-tight">Project DOIT</span>
                <span className="text-[9px] text-navy-500 font-mono tracking-[0.2em] uppercase">Quantamental Engine</span>
              </div>
            </div>
            <div className="w-px h-6 bg-navy-700 hidden sm:block" />
            <span className="text-[11px] text-navy-500 font-mono hidden sm:block">Pallavi Kochar</span>
          </div>

          <div className="flex items-center gap-3">
            {funnel?.as_of_date && (
              <span className="text-[11px] text-navy-600 font-mono hidden md:block">{funnel.as_of_date}</span>
            )}
            <RagIngestionBadge />
            {activeTab === "analysis" && (
              <button
                onClick={handleRun}
                disabled={isRunning}
                className={`px-4 py-1.5 text-[11px] font-700 rounded border tracking-widest uppercase transition-all flex items-center gap-2 ${
                  isRunning
                    ? "border-amber-accent/30 bg-amber-accent/8 text-amber-accent cursor-not-allowed"
                    : "border-cyan-accent bg-cyan-accent text-navy-950 hover:opacity-90 disabled:opacity-40"
                }`}
              >
                {isRunning ? (
                  <>
                    <span className="w-2.5 h-2.5 border border-amber-accent/40 border-t-amber-accent rounded-full animate-spin" />
                    Running…
                  </>
                ) : "▶ Run"}
              </button>
            )}
          </div>
        </div>

        {/* Tab bar */}
        <div className="max-w-7xl mx-auto px-6 border-t border-navy-800/40">
          <div className="flex">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-2 text-[10px] font-700 tracking-[0.2em] uppercase border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-cyan-accent text-cyan-accent"
                    : "border-transparent text-navy-600 hover:text-navy-400"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── Status banners ────────────────────────────────────────────── */}
      {activeTab === "analysis" && isRunning && (
        <div className="sticky top-[89px] z-40 bg-amber-accent/8 border-b border-amber-accent/20 text-amber-accent text-[11px] font-600 tracking-wide text-center py-2 flex items-center justify-center gap-2">
          <span className="w-3 h-3 border-2 border-amber-accent/30 border-t-amber-accent rounded-full animate-spin" />
          Pipeline running — results will refresh automatically when complete
        </div>
      )}
      {activeTab === "analysis" && justFinished && !isRunning && (
        <div className="sticky top-[89px] z-40 bg-green-signal/8 border-b border-green-signal/20 text-green-signal text-[11px] font-600 tracking-wide text-center py-2">
          ✓ Pipeline complete — all outputs refreshed
        </div>
      )}

      {/* ── Portfolio tab ─────────────────────────────────────────────── */}
      {activeTab === "portfolio" && (
        <main className="max-w-7xl mx-auto px-6 py-10">
          <Portfolio />
        </main>
      )}

      {/* ── Profile tab ───────────────────────────────────────────────── */}
      {activeTab === "profile" && (
        <main className="max-w-7xl mx-auto px-6 py-10">
          <ProfilePage />
        </main>
      )}

      {/* ── Top-Down Analysis tab ─────────────────────────────────────── */}
      {activeTab === "analysis" && (
        <>
          {/* Process step bar */}
          {hasData && (
            <div className="sticky top-[89px] z-30 bg-navy-950/98 backdrop-blur-sm border-b border-navy-700/30">
              <div className="max-w-7xl mx-auto px-6 flex items-stretch overflow-x-auto">
                {PROCESS_STEPS.map((step, idx) => {
                  const layer = funnel?.funnel?.[step.key];
                  const conf = layer?.confidence_label;
                  const dotCls =
                    conf === "High"   ? "bg-green-signal"  :
                    conf === "Medium" ? "bg-cyan-accent"   :
                    conf === "Low"    ? "bg-red-signal"    : "bg-navy-700";
                  const textCls =
                    conf === "High"   ? "text-green-signal"  :
                    conf === "Medium" ? "text-cyan-accent"   :
                    conf === "Low"    ? "text-red-signal"    : "text-navy-600";
                  return (
                    <button
                      key={step.key}
                      onClick={() => document.getElementById(step.anchor)?.scrollIntoView({ behavior: "smooth", block: "start" })}
                      className={`group flex items-center gap-2 px-4 py-3 shrink-0 hover:bg-navy-900/50 transition-colors ${
                        idx < PROCESS_STEPS.length - 1 ? "border-r border-navy-800/60" : ""
                      } ${textCls}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotCls}`} />
                      <span className="text-[9px] font-mono text-navy-700 tabular-nums">{step.num}</span>
                      <span className="text-[11px] font-600 tracking-wide">{step.label}</span>
                      {layer && (
                        <span className="text-[9px] font-mono opacity-50 tabular-nums">{layer.confidence.toFixed(0)}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <main className="max-w-7xl mx-auto px-6 py-12">

            {/* Loading */}
            {funnelLoading && (
              <div className="flex items-center justify-center py-32 text-navy-500">
                <div className="text-center space-y-4">
                  <div className="w-8 h-8 border-2 border-cyan-accent/20 border-t-cyan-accent rounded-full animate-spin mx-auto" />
                  <p className="text-sm font-mono tracking-wide">Loading pipeline outputs…</p>
                  <p className="text-xs text-navy-600">Run <code className="text-cyan-accent">python -m apm run --demo</code> first</p>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!funnelLoading && !hasData && (
              <div className="text-center py-32 space-y-5">
                <div className="text-6xl text-navy-800 font-mono">⚡</div>
                <h2 className="text-2xl font-700 text-white tracking-tight">No pipeline data</h2>
                <p className="text-navy-500 text-sm max-w-sm mx-auto leading-relaxed">
                  Run <code className="font-mono text-cyan-accent bg-navy-800 px-1.5 py-0.5 rounded text-xs">python -m apm run --demo</code> to generate demo outputs, then click Run.
                </p>
                <button
                  onClick={handleRun}
                  disabled={isRunning}
                  className="mt-2 px-6 py-3 bg-cyan-accent text-navy-950 font-700 tracking-wide rounded text-sm hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2 mx-auto"
                >
                  {isRunning ? (
                    <><span className="w-4 h-4 border-2 border-navy-950/30 border-t-navy-950 rounded-full animate-spin" />Running…</>
                  ) : "▶ Run Demo Pipeline"}
                </button>
              </div>
            )}

            {/* ── Full analysis ────────────────────────────────────────── */}
            {!funnelLoading && hasData && (
              <div className="space-y-24">

                {/* ── 01 ECONOMY ───────────────────────────────────────── */}
                <section id="sec-economy" className="scroll-mt-28">
                  <SectionHeader
                    num="01"
                    title="Economy"
                    subtitle="Macro baseline — growth, inflation, and leading indicators position the Investment Clock"
                    funnelLayer={funnel?.funnel?.economy}
                  />
                  <div className="space-y-5">
                    <EconomyPanel />
                    {economy && (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-navy-900 rounded-md border border-navy-700 p-5 card-accent">
                          <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-2 font-mono">PMI / ISM New Orders</p>
                          <div className="flex items-baseline gap-2 mb-3">
                            <span className="text-3xl font-mono font-700 text-white tabular-nums">{economy.pmi_read.toFixed(1)}</span>
                            <span className={`text-xs font-700 uppercase tracking-wide ${economy.pmi_read >= 50 ? "text-green-signal" : "text-red-signal"}`}>
                              {economy.pmi_read >= 50 ? "Expansion" : "Contraction"}
                            </span>
                          </div>
                          <div className="relative h-1.5 rounded-full overflow-hidden bg-navy-800">
                            <div className="absolute inset-0 flex">
                              <div className="w-1/2 bg-red-signal/15" /><div className="w-1/2 bg-green-signal/15" />
                            </div>
                            <div
                              className={`absolute top-0 h-full w-1 rounded-full ${economy.pmi_read >= 50 ? "bg-green-signal" : "bg-red-signal"}`}
                              style={{ left: `${Math.max(2, Math.min(98, ((economy.pmi_read - 25) / 50) * 100))}%` }}
                            />
                          </div>
                          <div className="flex justify-between text-[9px] text-navy-700 mt-1.5 font-mono">
                            <span>25</span><span>50 threshold</span><span>75</span>
                          </div>
                          <p className="text-[10px] text-navy-600 mt-4 italic">ISM NO &gt; 50 = positive earnings revisions</p>
                        </div>
                        <div className="bg-navy-900 rounded-md border border-navy-700 p-5">
                          <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-1 font-mono">Cost of Money</p>
                          <p className="text-[9px] text-cyan-accent/60 font-mono mb-3 tracking-wide">~18 month lead on PMI direction</p>
                          <p className="text-sm text-white leading-relaxed">{economy.cost_of_money_read}</p>
                          <p className="text-[10px] text-navy-600 mt-4 italic">Fed funds · 10yr yield · yield curve</p>
                        </div>
                        <div className="bg-navy-900 rounded-md border border-navy-700 p-5">
                          <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-1 font-mono">Cost of Goods</p>
                          <p className="text-[9px] text-cyan-accent/60 font-mono mb-3 tracking-wide">~24 month lead on PMI direction</p>
                          <p className="text-sm text-white leading-relaxed">{economy.cost_of_goods_read}</p>
                          <p className="text-[10px] text-navy-600 mt-4 italic">WTI crude · ISM prices paid</p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* ── 02 CYCLE ─────────────────────────────────────────── */}
                <section id="sec-cycle" className="scroll-mt-28">
                  <SectionHeader
                    num="02"
                    title="Business Cycle"
                    subtitle="Investment Clock · H.O.P.E. rate-transmission chain — Housing → Orders → Profits → Employment"
                    funnelLayer={funnel?.funnel?.cycle}
                  />
                  {cycle && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                      <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                        <div className="flex items-center justify-between mb-5">
                          <h3 className="text-[10px] font-700 text-navy-500 uppercase tracking-widest font-mono">Investment Clock</h3>
                          <span className="text-[10px] font-mono px-2.5 py-1 rounded border border-navy-700 text-navy-400 tracking-wide">
                            {cycle.market_cycle_phase.replace("_", " ")}
                          </span>
                        </div>
                        <InvestmentClock phase={cycle.clock_phase} />
                      </div>
                      <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                        <div className="flex items-center justify-between mb-5">
                          <h3 className="text-[10px] font-700 text-navy-500 uppercase tracking-widest font-mono">H.O.P.E. Transmission</h3>
                          {cycle.rotation_direction && (
                            <span className="text-[10px] font-mono text-amber-accent tracking-wide">{cycle.rotation_direction}</span>
                          )}
                        </div>
                        <HopeStrip
                          currentStage={cycle.hope_stage}
                          nextStage={cycle.hope_next_stage}
                          inflecting={cycle.hope_inflecting_indicators}
                        />
                      </div>
                    </div>
                  )}
                </section>

                {/* ── 03 SCENARIOS ─────────────────────────────────────── */}
                <section id="sec-scenarios" className="scroll-mt-28">
                  <SectionHeader
                    num="03"
                    title="Macro Scenarios"
                    subtitle="Probability-weighted paths — each scenario feeds distinct valuation and sector assumptions"
                    funnelLayer={funnel?.funnel?.scenario}
                  />
                  {scenarioData && (
                    <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                      <ScenarioPanel scenarios={scenarioData.scenarios} />
                    </div>
                  )}
                </section>

                {/* ── 04 SECTORS ───────────────────────────────────────── */}
                <section id="sec-sectors" className="scroll-mt-28">
                  <SectionHeader
                    num="04"
                    title="Sector Rotation"
                    subtitle="Macro-variable correlations rank sectors — most cyclical (Energy) to most defensive (Staples / Utilities)"
                    funnelLayer={funnel?.funnel?.sector}
                  />
                  {sectorData && (
                    <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                      <SectorHeatmap sectors={sectorData.ranked_sectors} />
                    </div>
                  )}
                </section>

                {/* ── 05 STYLE & FACTOR ────────────────────────────────── */}
                <section id="sec-style" className="scroll-mt-28">
                  <SectionHeader
                    num="05"
                    title="Style & Factor Selection"
                    subtitle="Phase factor leaders · size/style cyclicality spectrum · value vs. growth read"
                    funnelLayer={funnel?.funnel?.style}
                  />
                  {styleOutput?.data && <StyleFactorPanel output={styleOutput} />}
                </section>

                {/* ── 06 PIPELINE SUMMARY ──────────────────────────────── */}
                <section id="sec-pipeline" className="scroll-mt-28">
                  <SectionHeader
                    num="06"
                    title="Pipeline Summary"
                    subtitle="Screen → Fundamental → Valuation → Risk — per-layer confidence scores and rationale"
                    funnelLayer={funnel?.funnel?.screen}
                  />
                  <TopDownFunnel
                    funnel={funnel.funnel}
                    economy={economy}
                    cycle={cycle}
                    activePanel={activePanel}
                    onSelectPanel={setActivePanel}
                  />
                </section>

                {/* ── 07 FINAL RECOMMENDATIONS ─────────────────────────── */}
                <section id="sec-recs" className="scroll-mt-28">
                  <SectionHeader
                    num="07"
                    title="Final Recommendations"
                    subtitle="Ranked by conviction score — output of the complete top-down process"
                    funnelLayer={funnel?.funnel?.recommendations}
                  />
                  {recsData && (
                    <div className="space-y-5">
                      <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                        <div className="flex gap-4 text-xs font-mono mb-5">
                          <span className="text-green-signal font-700">{recsData.ranked.filter(r => r.action === "Buy").length} BUY</span>
                          <span className="text-navy-700">·</span>
                          <span className="text-amber-accent font-700">{recsData.ranked.filter(r => r.action === "Hold").length} HOLD</span>
                          <span className="text-navy-700">·</span>
                          <span className="text-red-signal font-700">{recsData.ranked.filter(r => r.action === "Sell").length} SELL</span>
                        </div>
                        <RecommendationsTable
                          recommendations={recsData.ranked}
                          llmAnalysis={llmData}
                          analystData={analystData}
                          secFilings={secData}
                          fundamentalData={fundamentalData}
                        />
                      </div>
                      <TickerSearch />
                    </div>
                  )}
                </section>

                {/* ── 08 RESEARCH & APPENDIX ───────────────────────────── */}
                <section className="scroll-mt-28 space-y-5">
                  <SectionHeader
                    num="08"
                    title="Research & Appendix"
                    subtitle="Contextual research · model assumptions · 10-year sector rotation backtest"
                  />
                  <RagPanel />
                  <AssumptionsPanel />
                  {backtestData && (
                    <div className="bg-navy-900 rounded-md border border-navy-700 p-6">
                      <div className="flex items-center justify-between mb-5">
                        <div>
                          <h3 className="text-[10px] font-700 text-navy-500 uppercase tracking-widest font-mono">10-Year Sector Rotation Backtest</h3>
                          <p className="text-xs text-navy-600 mt-0.5">{backtestData.strategy_name}</p>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="flex gap-4 text-xs font-mono">
                            <span className="text-green-signal font-700">{backtestData.metrics.cagr_pct.toFixed(1)}% CAGR</span>
                            <span className="text-navy-600">/</span>
                            <span className="text-cyan-accent font-700">+{backtestData.metrics.alpha_pct.toFixed(1)}% α</span>
                          </div>
                          {backtestJustFinished && (
                            <span className="text-[10px] text-green-signal border border-green-signal/30 bg-green-signal/8 px-2 py-1 rounded font-mono">✓ Updated</span>
                          )}
                          <button
                            onClick={handleRerunBacktest}
                            disabled={isBacktestRunning || isRunning}
                            className={`text-[11px] px-3 py-1.5 rounded border font-700 tracking-wide transition-colors flex items-center gap-1.5 uppercase ${
                              isBacktestRunning
                                ? "border-amber-accent/30 bg-amber-accent/8 text-amber-accent cursor-not-allowed"
                                : "border-cyan-accent/30 text-cyan-accent hover:bg-cyan-accent/8"
                            }`}
                          >
                            {isBacktestRunning ? (
                              <><span className="w-2.5 h-2.5 border border-amber-accent/40 border-t-amber-accent rounded-full animate-spin" />Running…</>
                            ) : "↺ Rerun"}
                          </button>
                        </div>
                      </div>
                      <BacktestResults data={backtestData} />
                    </div>
                  )}
                </section>

              </div>
            )}
          </main>
        </>
      )}
    </div>
  );
}

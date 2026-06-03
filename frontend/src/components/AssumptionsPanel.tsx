import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { api } from "../lib/api";

type Section = "scenarios" | "valuation" | "weights" | "thresholds";

interface ScenMacro { gdp_growth_pct: number; revenue_growth_pct: number; cpi_pct: number; fed_funds_pct: number; ten_year_yield_pct: number; earnings_growth_pct: number }
interface ScenCase { name?: string; probability: number; macro: ScenMacro }

interface NumberFieldProps {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  unit?: string;
}

function NumberField({ label, hint, value, onChange, step = 0.1, min, max, unit }: NumberFieldProps) {
  return (
    <div className="bg-navy-800/50 rounded-lg px-3 py-2.5 border border-navy-700/40">
      <label className="block text-[10px] text-navy-500 uppercase tracking-wider mb-1">
        {label}
        {unit && <span className="ml-1 normal-case text-navy-600">({unit})</span>}
      </label>
      {hint && <p className="text-[10px] text-navy-600 mb-1.5 normal-case">{hint}</p>}
      <input
        type="number"
        step={step}
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="w-full bg-transparent font-mono text-sm text-white tabular-nums focus:outline-none focus:ring-1 focus:ring-cyan-accent/50 rounded px-1 py-0.5"
      />
    </div>
  );
}

const SECTION_META: Record<Section, { label: string; hint: string }> = {
  scenarios:  { label: "Scenario Probabilities", hint: "Macro scenarios driving DCF — must sum to 100%" },
  valuation:  { label: "DCF & Valuation",        hint: "Terminal growth, risk premium, DCF/multiples blend" },
  weights:    { label: "Confidence Weights",      hint: "100-point score breakdown across macro, sector, fundamentals, etc." },
  thresholds: { label: "Buy / Sell Thresholds",   hint: "Minimum confidence / return / R:R required to recommend Buy or hold" },
};

export function AssumptionsPanel() {
  const qc = useQueryClient();
  const [openSection, setOpenSection] = useState<Section | null>(null);
  const [dirty, setDirty] = useState<Record<string, unknown>>({});

  const { data: cfg, isLoading } = useQuery({
    queryKey: ["assumptions"],
    queryFn: api.assumptions,
  });

  const { data: liveMacro } = useQuery({
    queryKey: ["liveMacro"],
    queryFn: api.liveMacro,
    staleTime: 60_000,
  });

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.setAssumptions(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assumptions"] });
      setDirty({});
    },
  });

  if (isLoading || !cfg) {
    return (
      <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
        <div className="text-xs text-navy-500 animate-pulse">Loading assumptions…</div>
      </div>
    );
  }

  // ── typed accessors ──────────────────────────────────────────────────────

  const scenarios = (cfg.scenarios ?? {}) as Record<string, Record<string, unknown>>;
  const val = (cfg.valuation ?? {}) as Record<string, number>;
  const weightsConfig = (cfg.weights ?? {}) as Record<string, Record<string, Record<string, unknown>>>;
  const weightComponents = (weightsConfig.score_components ?? {}) as Record<string, { weight: number; description: string }>;

  // Merged draft + saved
  const d = { ...val, ...(dirty.valuation as Record<string, number> | undefined ?? {}) };

  const SCEN_DEFAULTS: ScenCase = { probability: 0, macro: { gdp_growth_pct: 0, revenue_growth_pct: 0, cpi_pct: 0, fed_funds_pct: 0, ten_year_yield_pct: 0, earnings_growth_pct: 0 } };
  const dirtyScen = (dirty.scenarios ?? {}) as Record<string, Partial<ScenCase>>;
  function mergeCase(key: string): ScenCase {
    const saved = (scenarios[key] ?? SCEN_DEFAULTS) as unknown as ScenCase;
    const patch = dirtyScen[key] ?? {};
    return { ...saved, ...patch, macro: { ...saved.macro, ...((patch.macro as Partial<ScenMacro>) ?? {}) } };
  }
  const scen = { base: mergeCase("base_case"), bull: mergeCase("bull_case"), bear: mergeCase("bear_case") };
  const wts: Record<string, number> = {};
  for (const [k, v] of Object.entries(weightComponents)) {
    wts[k] = ((dirty.weights as Record<string, number> | undefined)?.[k] ?? v.weight) as number;
  }
  const wtsSum = Object.values(wts).reduce((a, b) => a + b, 0);

  function patchVal(key: string, v: number) {
    setDirty(prev => ({ ...prev, valuation: { ...((prev.valuation as object) ?? {}), [key]: v } }));
  }
  function patchScen(caseKey: string, field: string, v: unknown) {
    setDirty(prev => ({
      ...prev,
      scenarios: {
        ...((prev.scenarios as object) ?? {}),
        [caseKey]: { ...((prev.scenarios as Record<string, object> | undefined)?.[caseKey] ?? {}), [field]: v },
      },
    }));
  }
  function patchWeight(key: string, v: number) {
    setDirty(prev => ({ ...prev, weights: { ...((prev.weights as object) ?? {}), [key]: v } }));
  }
  function hasChanges(s: Section) {
    if (s === "scenarios") return !!dirty.scenarios;
    if (s === "valuation" || s === "thresholds") return !!dirty.valuation;
    if (s === "weights") return !!dirty.weights;
    return false;
  }

  const saveSection = (s: Section) => {
    const payload: Record<string, unknown> = {};
    if ((s === "scenarios") && dirty.scenarios) payload.scenarios = dirty.scenarios;
    if ((s === "valuation" || s === "thresholds") && dirty.valuation) payload.valuation = dirty.valuation;
    if (s === "weights" && dirty.weights) payload.weights = dirty.weights;
    saveMutation.mutate(payload);
  };

  const scenProbs = [
    { key: "base_case", label: "Base", color: "text-amber-accent", caseData: scen.base, defaultProb: 0.55 },
    { key: "bull_case", label: "Bull", color: "text-green-signal",  caseData: scen.bull, defaultProb: 0.25 },
    { key: "bear_case", label: "Bear", color: "text-red-signal",    caseData: scen.bear, defaultProb: 0.20 },
  ].map(sp => ({ ...sp, val: (sp.caseData.probability ?? sp.defaultProb) * 100 }));
  const probSum = scenProbs.reduce((a, x) => a + x.val, 0);

  return (
    <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">Model Assumptions</h3>
          <p className="text-xs text-navy-600 mt-0.5">Tune defaults — values are used on next pipeline run</p>
        </div>
        {/* Live data fetch status */}
        <div className="flex items-center gap-3">
          {liveMacro?.has_fred_key ? (
            <span className="text-[10px] text-green-signal border border-green-signal/30 bg-green-signal/10 px-2 py-1 rounded">
              FRED connected
            </span>
          ) : (
            <span className="text-[10px] text-navy-500 border border-navy-700 bg-navy-800/40 px-2 py-1 rounded" title={liveMacro?.note ?? ""}>
              FRED key not set — macro is manual
            </span>
          )}
        </div>
      </div>

      {/* Live data source info */}
      {!liveMacro?.has_fred_key && (
        <div className="mb-5 p-3 rounded-lg bg-navy-800/40 border border-navy-700/40 text-xs text-navy-500 space-y-1">
          <p className="font-600 text-navy-400">Free live data sources available:</p>
          <ul className="space-y-0.5 ml-2">
            <li><span className="text-cyan-accent">yfinance</span> — stock prices, SEC financials, analyst consensus <span className="text-green-signal">✓ active (no key needed)</span></li>
            <li><span className="text-cyan-accent">FRED</span> — Fed Funds, 10yr yield, yield curve, BAA spread, VIX, CPI, WTI, DXY, initial claims, NAHB <span className="text-amber-accent">add FRED_API_KEY env var (free at fred.stlouisfed.org)</span></li>
            <li><span className="text-navy-500">ISM PMI / New Orders</span> — proprietary; enter manually in the Macro Dashboard above</li>
          </ul>
          <p className="text-navy-600 mt-1">Once FRED_API_KEY is set, the Macro Dashboard "Pull Live Data" button will auto-populate all FRED fields.</p>
        </div>
      )}

      {/* Sections */}
      <div className="space-y-3">
        {(["scenarios", "valuation", "thresholds", "weights"] as Section[]).map(s => {
          const isOpen = openSection === s;
          const changed = hasChanges(s);
          return (
            <div key={s} className="border border-navy-700/50 rounded-lg overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-4 py-3 bg-navy-800/30 hover:bg-navy-800/50 transition-colors text-left"
                onClick={() => setOpenSection(isOpen ? null : s)}
              >
                <div>
                  <span className="text-sm font-600 text-white">{SECTION_META[s].label}</span>
                  <span className="ml-2 text-xs text-navy-500">{SECTION_META[s].hint}</span>
                </div>
                <div className="flex items-center gap-2">
                  {changed && <span className="text-[10px] text-cyan-accent border border-cyan-accent/30 bg-cyan-accent/10 px-1.5 py-0.5 rounded">unsaved</span>}
                  <span className="text-navy-500 text-xs">{isOpen ? "▲" : "▼"}</span>
                </div>
              </button>

              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="p-4 space-y-4">

                      {/* ── Scenarios ── */}
                      {s === "scenarios" && (
                        <>
                          <div className={`text-xs font-600 ${Math.abs(probSum - 100) > 0.5 ? "text-red-signal" : "text-green-signal"}`}>
                            Probability sum: {probSum.toFixed(0)}% {Math.abs(probSum - 100) > 0.5 ? "⚠ must equal 100%" : "✓"}
                          </div>
                          {scenProbs.map(sp => {
                            const m = sp.caseData.macro;
                            const patchMacro = (field: string, v: number) =>
                              patchScen(sp.key, "macro", { ...((scenarios[sp.key] as unknown as ScenCase | undefined)?.macro ?? {}), [field]: v });
                            return (
                              <div key={sp.key}>
                                <div className="flex items-center gap-3 mb-3">
                                  <div className={`text-xs font-700 px-2 py-0.5 rounded ${sp.color}`}>{sp.label}</div>
                                  <span className="text-xs text-navy-400">{sp.caseData.name ?? ""}</span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                  <NumberField label="Probability" unit="%" value={sp.val} step={1} min={0} max={100}
                                    onChange={v => patchScen(sp.key, "probability", v / 100)} />
                                  <NumberField label="GDP Growth" unit="%" step={0.1} value={m.gdp_growth_pct}
                                    onChange={v => patchMacro("gdp_growth_pct", v)} />
                                  <NumberField label="Revenue Growth" unit="%" step={0.5} value={m.revenue_growth_pct}
                                    onChange={v => patchMacro("revenue_growth_pct", v)} />
                                  <NumberField label="CPI" unit="%" step={0.1} value={m.cpi_pct}
                                    onChange={v => patchMacro("cpi_pct", v)} />
                                  <NumberField label="Fed Funds" unit="%" step={0.25} value={m.fed_funds_pct}
                                    onChange={v => patchMacro("fed_funds_pct", v)} />
                                  <NumberField label="10yr Yield" unit="%" step={0.05} value={m.ten_year_yield_pct}
                                    onChange={v => patchMacro("ten_year_yield_pct", v)} />
                                  <NumberField label="Earnings Growth" unit="%" step={1} value={m.earnings_growth_pct}
                                    onChange={v => patchMacro("earnings_growth_pct", v)} />
                                </div>
                              </div>
                            );
                          })}
                        </>
                      )}

                      {/* ── DCF / Valuation ── */}
                      {s === "valuation" && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                          <NumberField label="Terminal g — Startup" unit="%" hint="Perpetuity growth, early-stage"
                            value={d.terminal_g_startup ?? 3.0} step={0.1} min={0} max={5}
                            onChange={v => patchVal("terminal_g_startup", v)} />
                          <NumberField label="Terminal g — Growth" unit="%" hint="Perpetuity growth, growth stage"
                            value={d.terminal_g_growth ?? 2.5} step={0.1} min={0} max={5}
                            onChange={v => patchVal("terminal_g_growth", v)} />
                          <NumberField label="Terminal g — Mature" unit="%" hint="Perpetuity growth, mature stage"
                            value={d.terminal_g_mature ?? 2.0} step={0.1} min={0} max={5}
                            onChange={v => patchVal("terminal_g_mature", v)} />
                          <NumberField label="Terminal g — Decline" unit="%" hint="Perpetuity growth, declining stage"
                            value={d.terminal_g_decline ?? 1.0} step={0.1} min={0} max={4}
                            onChange={v => patchVal("terminal_g_decline", v)} />
                          <NumberField label="Equity Risk Premium" unit="%" hint="ERP added to risk-free rate"
                            value={d.equity_risk_premium ?? 5.5} step={0.1} min={2} max={10}
                            onChange={v => patchVal("equity_risk_premium", v)} />
                          <NumberField label="Corporate Tax Rate" unit="%" hint="Applied to NOPAT in DCF"
                            value={d.tax_rate_pct ?? 21.0} step={0.5} min={10} max={40}
                            onChange={v => patchVal("tax_rate_pct", v)} />
                          <NumberField label="DCF Weight" unit="0–1" hint="Share of blended value from DCF"
                            value={d.dcf_weight ?? 0.6} step={0.05} min={0} max={1}
                            onChange={v => patchVal("dcf_weight", v)} />
                          <NumberField label="Multiples Weight" unit="0–1" hint="Share from peer multiples (auto = 1 − DCF weight)"
                            value={d.multiples_weight ?? 0.4} step={0.05} min={0} max={1}
                            onChange={v => patchVal("multiples_weight", v)} />
                          <NumberField label="Bear Multiple Adj" unit="×" hint="Multiple compression in bear scenario"
                            value={d.bear_multiple_adj ?? 0.80} step={0.01} min={0.4} max={1}
                            onChange={v => patchVal("bear_multiple_adj", v)} />
                          <NumberField label="Bull Multiple Adj" unit="×" hint="Multiple expansion in bull scenario"
                            value={d.bull_multiple_adj ?? 1.15} step={0.01} min={1} max={1.5}
                            onChange={v => patchVal("bull_multiple_adj", v)} />
                        </div>
                      )}

                      {/* ── Action thresholds ── */}
                      {s === "thresholds" && (
                        <div className="space-y-4">
                          <div>
                            <div className="text-xs font-600 text-green-signal mb-2">BUY signal — all three must be met</div>
                            <div className="grid grid-cols-3 gap-3">
                              <NumberField label="Min Confidence" unit="pts (0–100)" hint="Score ≥ this to recommend Buy"
                                value={d.buy_confidence_min ?? 63} step={1} min={40} max={90}
                                onChange={v => patchVal("buy_confidence_min", v)} />
                              <NumberField label="Min Expected Return" unit="%" hint="Prob-weighted return > this"
                                value={d.buy_return_min_pct ?? 8.0} step={0.5} min={3} max={25}
                                onChange={v => patchVal("buy_return_min_pct", v)} />
                              <NumberField label="Min Reward:Risk" unit="×" hint="R:R ratio ≥ this"
                                value={d.buy_rr_min ?? 1.5} step={0.1} min={1} max={4}
                                onChange={v => patchVal("buy_rr_min", v)} />
                            </div>
                          </div>
                          <div>
                            <div className="text-xs font-600 text-red-signal mb-2">SELL / hold review — existing positions</div>
                            <div className="grid grid-cols-3 gap-3">
                              <NumberField label="Sell if Confidence ≤" unit="pts" hint="Sell existing if score drops below"
                                value={d.sell_confidence_max ?? 48} step={1} min={20} max={65}
                                onChange={v => patchVal("sell_confidence_max", v)} />
                              <NumberField label="Sell if Return ≤" unit="%" hint="Sell existing if expected return below"
                                value={d.sell_return_max_pct ?? 3.0} step={0.5} min={-10} max={10}
                                onChange={v => patchVal("sell_return_max_pct", v)} />
                              <NumberField label="Hold min R:R" unit="×" hint="Sell existing if R:R drops below"
                                value={d.hold_rr_min ?? 1.0} step={0.1} min={0.5} max={2}
                                onChange={v => patchVal("hold_rr_min", v)} />
                            </div>
                          </div>
                        </div>
                      )}

                      {/* ── Confidence weights ── */}
                      {s === "weights" && (
                        <>
                          <div className={`text-xs font-600 ${Math.abs(wtsSum - 100) > 0.5 ? "text-red-signal" : "text-green-signal"}`}>
                            Weight sum: {wtsSum} pts {Math.abs(wtsSum - 100) > 0.5 ? "⚠ must equal 100" : "✓"}
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                            {Object.entries(weightComponents).map(([key, meta]) => (
                              <NumberField
                                key={key}
                                label={key.replace(/_/g, " ")}
                                hint={(meta as { description: string }).description?.slice(0, 60)}
                                unit="pts"
                                value={wts[key] ?? 0}
                                step={1}
                                min={0}
                                max={50}
                                onChange={v => patchWeight(key, v)}
                              />
                            ))}
                          </div>
                        </>
                      )}

                      {/* Save button */}
                      {changed && (
                        <div className="flex gap-3 pt-2 border-t border-navy-700/40">
                          <button
                            onClick={() => saveSection(s)}
                            disabled={saveMutation.isPending}
                            className="px-4 py-2 text-sm font-600 rounded-lg bg-cyan-accent text-navy-950 hover:opacity-90 disabled:opacity-50 transition"
                          >
                            {saveMutation.isPending ? "Saving…" : "Save Assumptions"}
                          </button>
                          <button
                            onClick={() => setDirty(prev => {
                              const next = { ...prev };
                              if (s === "scenarios") delete next.scenarios;
                              if (s === "valuation" || s === "thresholds") delete next.valuation;
                              if (s === "weights") delete next.weights;
                              return next;
                            })}
                            className="px-4 py-2 text-sm text-navy-400 hover:text-white transition"
                          >
                            Reset
                          </button>
                          <p className="text-[10px] text-navy-600 self-center">Changes take effect on next pipeline run</p>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}

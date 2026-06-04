import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ConfidenceBar } from "./ConfidenceBar";
import { LLMAnalysis } from "./LLMAnalysis";
import { AnalystPanel } from "./AnalystPanel";
import { FinancialsPanel } from "./FinancialsPanel";
import type {
  StockRecommendation, ConfidenceLabel, Action,
  LLMAnalysisData, AnalystConsensus, SECFilingsData,
} from "../lib/types";

interface Props {
  recommendations: StockRecommendation[];
  llmAnalysis?: LLMAnalysisData;
  analystData?: Record<string, AnalystConsensus>;
  secFilings?: Record<string, SECFilingsData>;
}

const ACTION_STYLE: Record<Action, string> = {
  Buy:  "text-green-signal border-green-signal/40 bg-green-signal/10",
  Hold: "text-amber-accent border-amber-accent/40 bg-amber-accent/10",
  Sell: "text-red-signal   border-red-signal/40   bg-red-signal/10",
};

const CONF_STYLE: Record<ConfidenceLabel, string> = {
  High:   "confidence-high",
  Medium: "confidence-medium",
  Low:    "confidence-low",
};

type DrawerTab = "thesis" | "scenarios" | "analyst" | "financials" | "ai";

function fmt(n: number, decimals = 0) {
  return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function RecommendationsTable({ recommendations, llmAnalysis, analystData, secFilings }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Record<string, DrawerTab>>({});

  function getTab(ticker: string): DrawerTab {
    return activeTab[ticker] ?? "thesis";
  }

  function setTab(ticker: string, tab: DrawerTab) {
    setActiveTab(prev => ({ ...prev, [ticker]: tab }));
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="grid grid-cols-7 gap-2 px-3 py-2 text-xs text-navy-500 font-mono uppercase tracking-widest border-b border-navy-800">
        <span>Ticker</span>
        <span>Action</span>
        <span className="text-right">Current</span>
        <span className="text-right">Target</span>
        <span className="text-right">Return</span>
        <span className="text-right">R:R</span>
        <span className="text-right">Confidence</span>
      </div>

      {recommendations.map((rec, i) => {
        const isOpen = expanded === rec.ticker;
        const tab = getTab(rec.ticker);
        const hasAnalyst = !!analystData?.[rec.ticker];
        const hasFilings = !!secFilings?.[rec.ticker];
        const hasLLM = !!llmAnalysis?.analyses[rec.ticker];

        return (
          <div key={rec.ticker}>
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`grid grid-cols-7 gap-2 px-3 py-3 rounded-lg cursor-pointer border transition-colors ${
                isOpen ? "border-navy-700 bg-navy-800/70" : "border-transparent bg-navy-900/30 hover:bg-navy-900/60"
              }`}
              onClick={() => setExpanded(isOpen ? null : rec.ticker)}
              role="row"
              aria-expanded={isOpen}
            >
              <span className="font-display font-700 text-white text-sm">{rec.ticker}</span>

              <span className={`text-xs font-600 px-2 py-0.5 rounded border w-fit self-center ${ACTION_STYLE[rec.action]}`}>
                {rec.action}
              </span>

              <span className="text-right font-mono tabular-nums text-navy-400 text-sm self-center">
                ${fmt(rec.current_price)}
              </span>

              <span className="text-right font-mono tabular-nums text-white text-sm self-center">
                ${fmt(rec.prob_weighted_target)}
              </span>

              <span
                className={`text-right font-mono tabular-nums text-sm self-center ${
                  rec.action === "Sell"
                    ? rec.expected_return_pct < 0 ? "text-green-signal" : "text-red-signal"
                    : rec.expected_return_pct > 0 ? "text-green-signal" : "text-red-signal"
                }`}
                title={rec.action === "Sell" ? "Short return (profit from price decline)" : "Expected return (long)"}
              >
                {rec.action === "Sell"
                  ? (rec.expected_return_pct < 0 ? "+" : "") + fmt(-rec.expected_return_pct, 1) + "% short"
                  : (rec.expected_return_pct > 0 ? "+" : "") + fmt(rec.expected_return_pct, 1) + "%"
                }
              </span>

              <span className="text-right font-mono tabular-nums text-navy-400 text-sm self-center">
                {fmt(rec.reward_to_risk, 1)}×
              </span>

              <div className="self-center flex justify-end">
                <span className={`text-xs font-mono px-2 py-0.5 rounded border tabular-nums ${CONF_STYLE[rec.confidence_label]}`}>
                  {rec.confidence_label} {rec.confidence_numeric.toFixed(0)}
                </span>
              </div>
            </motion.div>

            {/* Expanded drawer */}
            <AnimatePresence>
              {isOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="mx-2 mb-2 bg-navy-800/50 rounded-xl border border-navy-700/50 overflow-hidden">
                    {/* Tab bar */}
                    <div className="flex border-b border-navy-700/50 bg-navy-900/30">
                      {(["thesis", "scenarios", "analyst", "financials", "ai"] as DrawerTab[]).map(t => {
                        if (t === "analyst" && !hasAnalyst) return null;
                        if (t === "financials" && !hasFilings) return null;
                        if (t === "ai" && !hasLLM) return null;
                        const labels: Record<DrawerTab, string> = {
                          thesis: "Thesis",
                          scenarios: "Scenarios",
                          analyst: "Analyst",
                          financials: "Financials",
                          ai: "AI Analysis",
                        };
                        return (
                          <button
                            key={t}
                            onClick={e => { e.stopPropagation(); setTab(rec.ticker, t); }}
                            className={`px-4 py-2.5 text-xs font-600 transition-colors border-b-2 ${
                              tab === t
                                ? "text-cyan-accent border-cyan-accent bg-cyan-accent/5"
                                : "text-navy-500 border-transparent hover:text-navy-300"
                            }`}
                          >
                            {labels[t]}
                          </button>
                        );
                      })}
                    </div>

                    <div className="p-5">
                      {/* Thesis tab */}
                      {tab === "thesis" && (
                        <div className="space-y-5">
                          <div>
                            <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Investment Thesis</h4>
                            <p className="text-sm text-navy-300 leading-relaxed">{rec.thesis}</p>
                          </div>
                          {rec.warnings.length > 0 && (
                            <div className="space-y-1">
                              {rec.warnings.map((w, wi) => (
                                <div key={wi} className="flex items-start gap-2 text-xs text-amber-accent">
                                  <span className="mt-px">⚠</span><span>{w}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          <div>
                            <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-3">Confidence Breakdown</h4>
                            <ConfidenceBar breakdown={rec.confidence_breakdown} total={rec.confidence_numeric} />
                          </div>
                        </div>
                      )}

                      {/* Scenarios tab */}
                      {tab === "scenarios" && (
                        <div>
                          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-3">Scenario Analysis</h4>
                          <div className="space-y-2">
                            {rec.scenario_table.map((sv) => (
                              <div key={sv.scenario_name} className="flex items-center justify-between text-xs bg-navy-900/50 rounded-lg px-3 py-2.5 border border-navy-800/50">
                                <span className="text-navy-400 w-28">{sv.scenario_name}</span>
                                <span className="text-navy-500 font-mono">{(sv.probability * 100).toFixed(0)}% prob</span>
                                <div className="text-right">
                                  <div className="font-mono tabular-nums text-white">${sv.blended_value.toFixed(0)} blended</div>
                                  <div className="text-[10px] text-navy-500">DCF ${sv.dcf_value.toFixed(0)} · Mult ${sv.multiples_value.toFixed(0)}</div>
                                </div>
                                <span className={`font-mono tabular-nums font-600 ${sv.upside_pct > 0 ? "text-green-signal" : "text-red-signal"}`}>
                                  {sv.upside_pct > 0 ? "+" : ""}{sv.upside_pct.toFixed(1)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Analyst tab */}
                      {tab === "analyst" && hasAnalyst && (
                        <div>
                          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-4">Analyst Consensus</h4>
                          <AnalystPanel data={analystData![rec.ticker]} />
                        </div>
                      )}

                      {/* Financials tab */}
                      {tab === "financials" && hasFilings && (
                        <div>
                          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-4">SEC Filings — Annual Financials</h4>
                          <FinancialsPanel data={secFilings![rec.ticker]} />
                        </div>
                      )}

                      {/* AI tab */}
                      {tab === "ai" && hasLLM && (
                        <div>
                          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-4">AI Analysis — Tailwinds & Headwinds</h4>
                          <LLMAnalysis
                            analysis={llmAnalysis!.analyses[rec.ticker]}
                            modelUsed={llmAnalysis!.model_used}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

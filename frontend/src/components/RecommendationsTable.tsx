import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ConfidenceBar } from "./ConfidenceBar";
import type { StockRecommendation, ConfidenceLabel, Action } from "../lib/types";

interface Props {
  recommendations: StockRecommendation[];
}

const ACTION_STYLE: Record<Action, string> = {
  Buy:     "text-green-signal  border-green-signal/40  bg-green-signal/10",
  Hold:    "text-amber-accent  border-amber-accent/40  bg-amber-accent/10",
  Replace: "text-red-signal    border-red-signal/40    bg-red-signal/10",
  Avoid:   "text-navy-500      border-navy-600/40      bg-navy-800/30",
};

const CONF_STYLE: Record<ConfidenceLabel, string> = {
  High:   "confidence-high",
  Medium: "confidence-medium",
  Low:    "confidence-low",
};

function fmt(n: number, decimals = 0) {
  return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function RecommendationsTable({ recommendations }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="grid grid-cols-8 gap-2 px-3 py-2 text-xs text-navy-500 font-mono uppercase tracking-widest border-b border-navy-800">
        <span>Ticker</span>
        <span>Action</span>
        <span className="text-right">Current</span>
        <span className="text-right">Target</span>
        <span className="text-right">Return</span>
        <span className="text-right">R:R</span>
        <span className="text-right">Confidence</span>
        <span>Replaces</span>
      </div>

      {recommendations.map((rec, i) => {
        const isOpen = expanded === rec.ticker;

        return (
          <div key={rec.ticker}>
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`grid grid-cols-8 gap-2 px-3 py-3 rounded-lg cursor-pointer border transition-colors ${
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

              <span className={`text-right font-mono tabular-nums text-sm self-center ${
                rec.expected_return_pct > 0 ? "text-green-signal" : "text-red-signal"
              }`}>
                {rec.expected_return_pct > 0 ? "+" : ""}{fmt(rec.expected_return_pct, 1)}%
              </span>

              <span className="text-right font-mono tabular-nums text-navy-400 text-sm self-center">
                {fmt(rec.reward_to_risk, 1)}×
              </span>

              <div className="self-center flex justify-end">
                <span className={`text-xs font-mono px-2 py-0.5 rounded border tabular-nums ${CONF_STYLE[rec.confidence_label]}`}>
                  {rec.confidence_label} {rec.confidence_numeric.toFixed(0)}
                </span>
              </div>

              <span className="text-xs text-navy-500 font-mono self-center">
                {rec.replaces_ticker ?? "—"}
              </span>
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
                  <div className="mx-2 mb-2 bg-navy-800/50 rounded-xl border border-navy-700/50 p-5 space-y-5">
                    {/* Thesis */}
                    <div>
                      <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">
                        Investment Thesis
                      </h4>
                      <p className="text-sm text-navy-300 leading-relaxed">{rec.thesis}</p>
                    </div>

                    {/* Warnings */}
                    {rec.warnings.length > 0 && (
                      <div className="space-y-1">
                        {rec.warnings.map((w, wi) => (
                          <div key={wi} className="flex items-start gap-2 text-xs text-amber-accent">
                            <span className="mt-px">⚠</span>
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Scenario table */}
                      <div>
                        <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-3">
                          Scenario Analysis
                        </h4>
                        <div className="space-y-2">
                          {rec.scenario_table.map((sv) => (
                            <div key={sv.scenario_name} className="flex items-center justify-between text-xs bg-navy-900/50 rounded-lg px-3 py-2 border border-navy-800/50">
                              <span className="text-navy-400">{sv.scenario_name}</span>
                              <span className="text-navy-500 font-mono">{(sv.probability * 100).toFixed(0)}%</span>
                              <span className="font-mono tabular-nums text-white">${sv.blended_value.toFixed(0)}</span>
                              <span className={`font-mono tabular-nums ${sv.upside_pct > 0 ? "text-green-signal" : "text-red-signal"}`}>
                                {sv.upside_pct > 0 ? "+" : ""}{sv.upside_pct.toFixed(1)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Confidence breakdown */}
                      <div>
                        <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-3">
                          Confidence Breakdown
                        </h4>
                        <ConfidenceBar
                          breakdown={rec.confidence_breakdown}
                          total={rec.confidence_numeric}
                        />
                      </div>
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

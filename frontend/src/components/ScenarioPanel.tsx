import { motion } from "motion/react";
import type { Scenario } from "../lib/types";

interface Props {
  scenarios: Scenario[];
}

const SCENARIO_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  base_case: { color: "text-amber-accent",  bg: "bg-amber-accent/10",  border: "border-amber-accent/30" },
  bull_case: { color: "text-green-signal",  bg: "bg-green-signal/10",  border: "border-green-signal/30" },
  bear_case: { color: "text-red-signal",    bg: "bg-red-signal/10",    border: "border-red-signal/30"   },
};

export function ScenarioPanel({ scenarios }: Props) {
  const totalProb = scenarios.reduce((s, x) => s + x.probability, 0);
  const probOk = Math.abs(totalProb - 1.0) < 0.005;

  return (
    <div className="space-y-3">
      {/* Probability sum indicator */}
      <div className={`flex items-center gap-2 text-xs font-mono px-2 py-1 rounded border w-fit ${
        probOk
          ? "text-green-signal border-green-signal/30 bg-green-signal/10"
          : "text-red-signal border-red-signal/30 bg-red-signal/10"
      }`}>
        <span>∑ = {(totalProb * 100).toFixed(0)}%</span>
        <span>{probOk ? "✓" : "⚠ must sum to 100%"}</span>
      </div>

      {scenarios.map((s, i) => {
        const style = SCENARIO_STYLES[s.name] ?? SCENARIO_STYLES.base_case;
        const widthPct = s.probability * 100;

        return (
          <motion.div
            key={s.name}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`rounded-lg border p-4 ${style.border} ${style.bg}`}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className={`text-sm font-700 ${style.color}`}>{s.label}</div>
                <div className={`text-xs font-mono tabular-nums mt-0.5 ${style.color}`}>
                  {s.probability.toFixed(0) === "0" ? (s.probability * 100).toFixed(0) : Math.round(s.probability * 100)}%
                </div>
              </div>
              <div className="text-right text-xs text-navy-500 font-mono">
                <div>GDP {s.macro.gdp_growth_pct > 0 ? "+" : ""}{s.macro.gdp_growth_pct}%</div>
                <div>EPS {s.macro.earnings_growth_pct > 0 ? "+" : ""}{s.macro.earnings_growth_pct}%</div>
              </div>
            </div>

            {/* Probability bar */}
            <div className="h-1 bg-navy-800 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${widthPct}%` }}
                transition={{ delay: i * 0.1 + 0.2, duration: 0.5 }}
                className={`h-full rounded-full ${
                  s.name === "base_case" ? "bg-amber-accent" :
                  s.name === "bull_case" ? "bg-green-signal" : "bg-red-signal"
                }`}
              />
            </div>

            {/* Key macro assumptions */}
            <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-navy-500 font-mono">
              <span>CPI {s.macro.cpi_pct}%</span>
              <span>10yr {s.macro.ten_year_yield_pct}%</span>
              <span className="capitalize">{s.macro.margin_trajectory}</span>
              <span className="capitalize">{s.macro.market_multiple_path} PE</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

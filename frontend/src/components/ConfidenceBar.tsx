import { motion } from "motion/react";
import type { ConfidenceBreakdown } from "../lib/types";

interface Props {
  breakdown: ConfidenceBreakdown;
  total: number;
}

const COMPONENTS = [
  { key: "macro_cycle_conviction",      label: "Macro/Cycle",   color: "bg-cyan-accent",        max: 30 },
  { key: "sector_fit",                  label: "Sector Fit",    color: "bg-amber-accent",        max: 20 },
  { key: "style_factor_fit",            label: "Style/Factor",  color: "bg-purple-signal",       max: 15 },
  { key: "reward_to_risk",              label: "Reward:Risk",   color: "bg-green-signal",        max: 15 },
  { key: "fundamental_quality",         label: "Fundamental",   color: "bg-cyan-accent/70",      max: 8  },
  { key: "cross_sectional_valuation",   label: "Valuation",     color: "bg-amber-accent/70",     max: 5  },
  { key: "technical_catalyst",          label: "Technical",     color: "bg-navy-500",            max: 4  },
  { key: "stock_picking_regime",        label: "Regime",        color: "bg-navy-600",            max: 3  },
] as const;

const PENALTIES = [
  { key: "no_downside_scenario_penalty", label: "No downside",  color: "bg-red-signal" },
  { key: "crowding_penalty",             label: "Crowding",     color: "bg-red-signal/70" },
  { key: "terminal_g_warning_penalty",   label: "Terminal g",   color: "bg-red-signal/50" },
  { key: "theme_not_universal_penalty",  label: "Non-universal",color: "bg-red-signal/40" },
] as const;

export function ConfidenceBar({ breakdown, total }: Props) {
  return (
    <div className="space-y-1.5" role="meter" aria-valuenow={total} aria-valuemin={0} aria-valuemax={100}>
      {COMPONENTS.map((comp) => {
        const value = breakdown[comp.key];
        const pct = (value / comp.max) * 100;
        return (
          <div key={comp.key} className="flex items-center gap-2 text-xs">
            <span className="text-navy-500 w-20 text-right">{comp.label}</span>
            <div className="flex-1 h-1.5 bg-navy-800 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.max(0, pct)}%` }}
                transition={{ duration: 0.4 }}
                className={`h-full rounded-full ${comp.color}`}
              />
            </div>
            <span className="font-mono tabular-nums text-navy-500 w-8">{value.toFixed(1)}</span>
          </div>
        );
      })}

      {/* Penalties */}
      {PENALTIES.map((pen) => {
        const value = breakdown[pen.key];
        if (value === 0) return null;
        return (
          <div key={pen.key} className="flex items-center gap-2 text-xs">
            <span className="text-red-signal/70 w-20 text-right">{pen.label}</span>
            <div className="flex-1 h-1.5 bg-navy-800 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.abs(value)}%` }}
                transition={{ duration: 0.4 }}
                className={`h-full rounded-full ${pen.color} ml-auto`}
              />
            </div>
            <span className="font-mono tabular-nums text-red-signal w-8">{value.toFixed(1)}</span>
          </div>
        );
      })}

      {/* Total */}
      <div className="pt-1 border-t border-navy-800/50 flex items-center justify-between text-xs">
        <span className="text-navy-500">Total Score</span>
        <span className="font-mono font-700 tabular-nums text-white">{total.toFixed(1)} / 100</span>
      </div>
    </div>
  );
}

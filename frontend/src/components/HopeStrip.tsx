import { motion } from "motion/react";
import type { HopeStage } from "../lib/types";

const STAGES: Array<{ key: HopeStage; label: string; full: string; lag: string }> = [
  { key: "Housing",    label: "H",          full: "Housing",    lag: "1–6m"   },
  { key: "Orders",     label: "O",          full: "New Orders", lag: "4–10m"  },
  { key: "Profits",    label: "P",          full: "Profits",    lag: "7–15m"  },
  { key: "Employment", label: "E",          full: "Employment", lag: "12–24m" },
];

interface Props {
  currentStage: HopeStage;
  nextStage: HopeStage;
  inflecting: string[];
}

export function HopeStrip({ currentStage, nextStage, inflecting }: Props) {
  const currentIdx = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="space-y-4">
      <div className="flex items-stretch gap-0">
        {STAGES.map((stage, i) => {
          const isPast    = i < currentIdx;
          const isCurrent = stage.key === currentStage;
          const isNext    = stage.key === nextStage;

          return (
            <div key={stage.key} className="flex items-stretch flex-1">
              {/* Stage block */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.1 }}
                className={`flex-1 rounded-lg p-3 text-center relative border transition-colors ${
                  isCurrent
                    ? "border-cyan-accent/60 bg-cyan-accent/10"
                    : isPast
                    ? "border-navy-700/40 bg-navy-800/30"
                    : "border-navy-800/30 bg-navy-900/20"
                }`}
                aria-current={isCurrent ? "step" : undefined}
              >
                {/* Active glow */}
                {isCurrent && (
                  <div className="absolute -top-px left-1/2 -translate-x-1/2 w-8 h-0.5 bg-cyan-accent rounded-full" />
                )}

                <div className={`text-2xl font-display font-700 mb-1 ${
                  isCurrent ? "text-cyan-accent" : isPast ? "text-navy-500" : "text-navy-600"
                }`}>
                  {stage.label}
                </div>
                <div className={`text-xs font-600 ${isCurrent ? "text-white" : "text-navy-500"}`}>
                  {stage.full}
                </div>
                <div className="text-xs text-navy-600 font-mono mt-0.5">{stage.lag}</div>

                {isCurrent && (
                  <div className="mt-2">
                    <span className="text-xs bg-cyan-accent/20 text-cyan-accent px-1.5 py-0.5 rounded font-mono">
                      current
                    </span>
                  </div>
                )}
                {isNext && !isCurrent && (
                  <div className="mt-2">
                    <span className="text-xs bg-amber-accent/15 text-amber-accent px-1.5 py-0.5 rounded font-mono">
                      next →
                    </span>
                  </div>
                )}
              </motion.div>

              {/* Connector arrow */}
              {i < STAGES.length - 1 && (
                <div className="flex items-center px-1 text-navy-700">→</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Inflecting indicators */}
      {inflecting.length > 0 && (
        <div className="pt-3 border-t border-navy-800/50">
          <p className="text-xs text-navy-500 mb-1.5">Inflecting now:</p>
          <div className="flex flex-wrap gap-1.5">
            {inflecting.map((ind, i) => (
              <span key={i} className="text-xs font-mono px-2 py-0.5 rounded bg-navy-800 text-navy-400 border border-navy-700/50">
                {ind}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-navy-600 italic">
        Rate-change transmission takes up to ~24 months to reach Employment. Employment is the last to turn.
      </p>
    </div>
  );
}

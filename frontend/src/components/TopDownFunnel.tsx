import { motion } from "motion/react";
import type { CycleData, EconomyData, FunnelSummary } from "../lib/types";

const LAYERS = [
  { key: "economy",        label: "ECONOMY",          num: "①" },
  { key: "cycle",          label: "CYCLE / CLOCK",    num: "②" },
  { key: "scenarios",      label: "SCENARIOS",        num: "③" },
  { key: "sector",         label: "SECTOR",           num: "④" },
  { key: "style",          label: "STYLE / FACTOR",   num: "⑤" },
  { key: "screen",         label: "SCREEN",           num: "⑥" },
  { key: "fundamental",    label: "STOCK ANALYSIS",   num: "⑦–⑨" },
  { key: "recommendations",label: "RECOMMENDATIONS",  num: "⑩" },
] as const;

type LayerKey = typeof LAYERS[number]["key"];

interface Props {
  funnel: FunnelSummary["funnel"];
  economy?: EconomyData;
  cycle?: CycleData;
  activePanel: LayerKey | null;
  onSelectPanel: (key: LayerKey | null) => void;
}

function confidenceColor(label: string) {
  if (label === "High")   return "text-green-signal border-green-signal/40 bg-green-signal/10";
  if (label === "Medium") return "text-amber-accent border-amber-accent/40 bg-amber-accent/10";
  return "text-red-signal border-red-signal/40 bg-red-signal/10";
}

function dirArrow(dir: string) {
  return dir === "rising" ? "↑" : dir === "falling" ? "↓" : "→";
}

export function TopDownFunnel({ funnel, economy, cycle, activePanel, onSelectPanel }: Props) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-0.5 h-6 bg-cyan-accent" />
        <h2 className="text-xs font-600 text-navy-500 uppercase tracking-widest">Top-Down Process</h2>
        <span className="text-navy-600 text-xs ml-2">Economy → Cycle → Sector → Style → Stock</span>
      </div>

      {LAYERS.map((layer, i) => {
        const data = funnel[layer.key];
        const isActive = activePanel === layer.key;
        const widthPct = 100 - i * 4;

        return (
          <motion.div
            key={layer.key}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08, duration: 0.4, ease: "easeOut" }}
            style={{ width: `${widthPct}%` }}
            className={`funnel-band relative rounded-lg border px-5 py-3 ${
              isActive
                ? "border-cyan-accent/50 bg-navy-800"
                : "border-navy-800/60 bg-navy-900/50"
            }`}
            onClick={() => onSelectPanel(isActive ? null : layer.key as LayerKey)}
            role="button"
            aria-expanded={isActive}
            aria-label={`${layer.label} panel`}
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onSelectPanel(isActive ? null : layer.key as LayerKey)}
          >
            {/* Left accent bar */}
            {isActive && (
              <motion.div
                layoutId="funnel-accent"
                className="absolute left-0 top-0 bottom-0 w-0.5 bg-cyan-accent rounded-l-lg"
              />
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-navy-600 font-mono text-xs w-8">{layer.num}</span>
                <span className={`text-xs font-700 tracking-widest ${isActive ? "text-cyan-accent" : "text-navy-400"}`}>
                  {layer.label}
                </span>
              </div>

              {/* Inline summary */}
              <div className="flex items-center gap-4">
                {/* Economy-specific pills */}
                {layer.key === "economy" && economy && (
                  <span className="text-xs font-mono text-white">
                    Growth {dirArrow(economy.growth_direction)} · Inflation {dirArrow(economy.inflation_direction)} · CMI {economy.cmi_score}
                  </span>
                )}
                {layer.key === "cycle" && cycle && (
                  <span className="text-xs font-mono text-amber-accent">{cycle.clock_phase}</span>
                )}
                {layer.key === "cycle" && cycle && (
                  <span className="text-xs text-navy-500 font-mono">H.O.P.E.: {cycle.hope_stage}</span>
                )}

                {/* Confidence pill */}
                {data && (
                  <span className={`text-xs font-mono px-2 py-0.5 rounded border tabular-nums ${confidenceColor(data.confidence_label)}`}>
                    {data.confidence_label} {data.confidence?.toFixed(0)}
                  </span>
                )}
                {!data && (
                  <span className="text-xs text-navy-600 font-mono">not run</span>
                )}

                <span className="text-navy-600 text-xs ml-1">{isActive ? "▾" : "▸"}</span>
              </div>
            </div>

            {/* Expanded rationale */}
            {isActive && data && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="mt-3 pt-3 border-t border-navy-700/50"
              >
                <p className="text-xs text-navy-400 leading-relaxed">{data.rationale}</p>
                {data.warnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {data.warnings.map((w, wi) => (
                      <p key={wi} className="text-xs text-amber-accent/80">⚠ {w}</p>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

import { motion } from "motion/react";
import type { SectorScore, Favorability } from "../lib/types";

interface Props {
  sectors: SectorScore[];
}

const FAV_STYLE: Record<Favorability, { bg: string; border: string; text: string; bar: string }> = {
  strongly_favored:   { bg: "bg-green-signal/20",  border: "border-green-signal/50",  text: "text-green-signal",  bar: "bg-green-signal" },
  favored:            { bg: "bg-green-signal/10",  border: "border-green-signal/30",  text: "text-green-signal",  bar: "bg-green-signal/70" },
  neutral:            { bg: "bg-navy-800/50",       border: "border-navy-700/40",      text: "text-navy-400",       bar: "bg-navy-600" },
  unfavored:          { bg: "bg-red-signal/10",     border: "border-red-signal/30",    text: "text-red-signal",    bar: "bg-red-signal/70" },
  strongly_unfavored: { bg: "bg-red-signal/20",     border: "border-red-signal/50",    text: "text-red-signal",    bar: "bg-red-signal" },
};

const FAV_LABELS: Record<Favorability, string> = {
  strongly_favored: "★★", favored: "★", neutral: "—",
  unfavored: "▼", strongly_unfavored: "▼▼",
};

export function SectorHeatmap({ sectors }: Props) {
  const sorted = [...sectors].sort((a, b) => b.score - a.score);

  return (
    <div className="space-y-1.5">
      {sorted.map((s, i) => {
        const style = FAV_STYLE[s.favorability];
        return (
          <motion.div
            key={s.sector}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${style.bg} ${style.border} group relative`}
            title={`Primary driver: ${s.primary_macro_driver}\n${s.supporting_drivers.join(", ")}`}
          >
            {/* Score bar */}
            <div className="w-24 h-1.5 bg-navy-800 rounded-full overflow-hidden flex-shrink-0">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${s.score}%` }}
                transition={{ delay: i * 0.04 + 0.15, duration: 0.4 }}
                className={`h-full rounded-full ${style.bar}`}
              />
            </div>

            <span className="text-xs font-600 text-white flex-1 truncate">{s.sector}</span>

            <span className={`text-xs font-mono w-6 text-center ${style.text}`}>
              {FAV_LABELS[s.favorability]}
            </span>

            <span className="text-xs font-mono tabular-nums text-navy-500 w-8 text-right">
              {s.score.toFixed(0)}
            </span>

            {/* Hover tooltip */}
            <div className="absolute left-full ml-2 top-0 z-20 hidden group-hover:block w-48 bg-navy-900 border border-navy-700 rounded-lg p-3 text-xs shadow-xl">
              <div className={`font-700 mb-1 ${style.text}`}>{s.sector}</div>
              <div className="text-navy-400 mb-1">Driver: {s.primary_macro_driver}</div>
              {s.supporting_drivers.slice(0, 2).map((d, di) => (
                <div key={di} className="text-navy-500">{d}</div>
              ))}
            </div>
          </motion.div>
        );
      })}

      <p className="text-xs text-navy-600 pt-2 italic">
        Correlations: Piper Sandler Field Guide. Hover for macro driver detail.
      </p>
    </div>
  );
}

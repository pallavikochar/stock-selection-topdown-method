import type { AgentOutput, StyleData } from "../lib/types";

// Field guide: SCV = most cyclical (left), LCG = most defensive (right)
const SIZE_STYLE_BOXES = [
  "Small Cap Value",
  "Small Cap Blend",
  "Small Cap Growth",
  "Mid Cap Value",
  "Mid Cap Blend",
  "Mid Cap Growth",
  "Large Cap Value",
  "Large Cap Blend",
  "Large Cap Growth",
] as const;

type SizeStyleBox = (typeof SIZE_STYLE_BOXES)[number];

const BOX_IDX: Record<SizeStyleBox, number> = {
  "Small Cap Value": 0,
  "Small Cap Blend": 1,
  "Small Cap Growth": 2,
  "Mid Cap Value": 3,
  "Mid Cap Blend": 4,
  "Mid Cap Growth": 5,
  "Large Cap Value": 6,
  "Large Cap Blend": 7,
  "Large Cap Growth": 8,
};

const SHORT: Record<SizeStyleBox, string> = {
  "Small Cap Value": "SV",
  "Small Cap Blend": "SB",
  "Small Cap Growth": "SG",
  "Mid Cap Value": "MV",
  "Mid Cap Blend": "MB",
  "Mid Cap Growth": "MG",
  "Large Cap Value": "LV",
  "Large Cap Blend": "LB",
  "Large Cap Growth": "LG",
};

export function StyleFactorPanel({ output }: { output: AgentOutput<StyleData> }) {
  const style = output.data;
  const activeIdx = BOX_IDX[style.favored_size_style_box as SizeStyleBox] ?? -1;

  return (
    <div className="bg-navy-900 rounded-xl border border-navy-800 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">
            Style & Factor Selection
          </h3>
          <p className="text-xs text-navy-600 mt-0.5">
            Piper Sandler field guide — phase: {style.phase}
          </p>
        </div>
        <span className="text-xs px-2 py-1 rounded border border-cyan-accent/30 text-cyan-accent font-mono">
          {style.favored_size_style_box}
        </span>
      </div>

      {/* Size/Style spectrum — field guide p.9: LCG most defensive, SCV most cyclical */}
      <div>
        <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-2">
          Size/Style Spectrum
        </p>
        <div className="flex gap-0.5">
          {SIZE_STYLE_BOXES.map((box, i) => (
            <div
              key={box}
              title={box}
              className={`flex-1 py-1.5 text-[9px] text-center rounded transition-colors ${
                i === activeIdx
                  ? "bg-cyan-accent text-navy-950 font-700"
                  : "bg-navy-800/50 text-navy-600 hover:text-navy-400"
              }`}
            >
              {SHORT[box]}
            </div>
          ))}
        </div>
        <div className="flex justify-between text-[9px] text-navy-600 mt-1">
          <span>← Most Cyclical</span>
          <span>Most Defensive →</span>
        </div>
      </div>

      {/* Favored factors */}
      <div>
        <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-2">
          Favored Factors
        </p>
        <div className="space-y-2">
          {style.favored_factors.map((f) => (
            <div
              key={f.factor_name}
              className="flex items-start gap-3 p-2.5 rounded-lg bg-navy-800/40 border border-navy-700/30"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-600 text-white">{f.factor_name}</span>
                  {f.cross_universe_holds ? (
                    <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-green-signal/10 text-green-signal border border-green-signal/20">
                      universal ✓
                    </span>
                  ) : (
                    <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-amber-accent/10 text-amber-accent border border-amber-accent/20">
                      partial ⚠
                    </span>
                  )}
                </div>
                <p className="text-xs text-navy-500 mt-0.5 leading-relaxed">{f.rationale}</p>
              </div>
              <div className="text-xs font-mono text-navy-400 tabular-nums shrink-0">
                {(f.weight * 100).toFixed(0)}wt
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Avoid factors */}
      {style.avoid_factors.length > 0 && (
        <div>
          <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-2">Avoid</p>
          <div className="flex flex-wrap gap-1.5">
            {style.avoid_factors.map((f) => (
              <span
                key={f}
                className="text-xs font-mono px-2 py-0.5 rounded bg-red-signal/10 text-red-signal border border-red-signal/20"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Value vs Growth */}
      <div className="p-3 rounded-lg bg-navy-800/30 border border-navy-700/20">
        <p className="text-[10px] text-navy-500 uppercase tracking-widest mb-1.5">
          Value vs. Growth
        </p>
        <p className="text-xs text-navy-300 leading-relaxed">{style.value_vs_growth_read}</p>
      </div>

      {/* Dividend yield warning — field guide: high div yield is CYCLICAL, not defensive */}
      <div className="flex gap-2 p-2.5 rounded-lg bg-amber-accent/5 border border-amber-accent/20">
        <span className="text-amber-accent text-xs mt-0.5 shrink-0">⚠</span>
        <p className="text-xs text-amber-accent/80 leading-relaxed">
          {style.dividend_yield_warning}
        </p>
      </div>

      {/* Field guide footnote */}
      <p className="text-[10px] text-navy-600 italic">
        "If a theme isn't working everywhere it isn't actually working." — Piper Sandler field guide.
        Factors marked <span className="text-green-signal">universal ✓</span> hold across cap sizes and sectors.
      </p>
    </div>
  );
}

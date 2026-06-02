import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { LLMStockAnalysis, VerifiedClaim, Grounding, Sentiment } from "../lib/types";

interface Props {
  analysis: LLMStockAnalysis;
  modelUsed: string;
}

const GROUNDING_STYLE: Record<Grounding, string> = {
  GROUNDED:   "text-green-signal  border-green-signal/40  bg-green-signal/10",
  INFERRED:   "text-amber-accent  border-amber-accent/40  bg-amber-accent/10",
  SPECULATIVE:"text-red-signal    border-red-signal/40    bg-red-signal/10",
};

const SENTIMENT_STYLE: Record<Sentiment, string> = {
  BULLISH: "text-green-signal  border-green-signal/40  bg-green-signal/10",
  NEUTRAL: "text-amber-accent  border-amber-accent/40  bg-amber-accent/10",
  BEARISH: "text-red-signal    border-red-signal/40    bg-red-signal/10",
};

const GROUNDING_LABEL: Record<Grounding, string> = {
  GROUNDED:    "Grounded",
  INFERRED:    "Inferred",
  SPECULATIVE: "Speculative",
};

function ClaimCard({ claim, index, side }: { claim: VerifiedClaim; index: number; side: "tail" | "head" }) {
  const [open, setOpen] = useState(false);
  const borderColor = side === "tail" ? "border-green-signal/20" : "border-red-signal/20";
  const dotColor   = side === "tail" ? "bg-green-signal" : "bg-red-signal";

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={`rounded-lg border ${borderColor} bg-navy-900/50 p-3 space-y-2`}
    >
      <div className="flex items-start gap-2">
        <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
        <p className="text-xs text-navy-200 leading-relaxed flex-1">{claim.claim}</p>
      </div>

      <div className="flex items-center justify-between ml-3.5">
        <span className={`text-[10px] font-600 font-mono px-1.5 py-0.5 rounded border ${GROUNDING_STYLE[claim.grounding]}`}>
          {GROUNDING_LABEL[claim.grounding]}
        </span>
        <button
          onClick={() => setOpen(!open)}
          className="text-[10px] text-navy-500 hover:text-navy-300 font-mono transition-colors"
          aria-label="Toggle evidence"
        >
          {open ? "hide evidence ↑" : "evidence ↓"}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden ml-3.5"
          >
            <p className="text-[10px] text-navy-400 leading-relaxed italic border-l border-navy-700 pl-2 mt-1">
              {claim.evidence}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function LLMAnalysis({ analysis, modelUsed }: Props) {
  const groundingPct = Math.round(analysis.grounding_score * 100);
  const groundingColor =
    groundingPct >= 85 ? "text-green-signal" :
    groundingPct >= 70 ? "text-amber-accent" :
    "text-red-signal";

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-navy-500 font-mono">
          {modelUsed === "demo-preseeded" ? "Demo analysis" : modelUsed}
        </span>
        <span className="text-navy-700">·</span>
        <span className={`text-xs font-mono font-600 ${groundingColor}`}>
          {groundingPct}% grounded
        </span>
        <span className="text-navy-700">·</span>
        <span className={`text-xs font-600 px-2 py-0.5 rounded border ${SENTIMENT_STYLE[analysis.net_sentiment]}`}>
          {analysis.net_sentiment}
        </span>
        <span className="text-navy-700">·</span>
        <span className="text-[10px] text-navy-500 font-mono">
          two-pass verified
        </span>
      </div>

      {/* Sentiment rationale */}
      <p className="text-xs text-navy-400 leading-relaxed italic border-l-2 border-cyan-accent/30 pl-3">
        {analysis.sentiment_rationale}
      </p>

      {/* Tailwinds / Headwinds two-column grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-2">
          <h5 className="text-[10px] font-600 text-green-signal uppercase tracking-widest mb-2">
            Tailwinds ({analysis.tailwinds.length})
          </h5>
          {analysis.tailwinds.map((c, i) => (
            <ClaimCard key={i} claim={c} index={i} side="tail" />
          ))}
        </div>
        <div className="space-y-2">
          <h5 className="text-[10px] font-600 text-red-signal uppercase tracking-widest mb-2">
            Headwinds ({analysis.headwinds.length})
          </h5>
          {analysis.headwinds.map((c, i) => (
            <ClaimCard key={i} claim={c} index={i} side="head" />
          ))}
        </div>
      </div>

      {/* Grounding legend */}
      <div className="flex gap-4 pt-1 border-t border-navy-800/50">
        {(["GROUNDED", "INFERRED", "SPECULATIVE"] as Grounding[]).map((g) => (
          <div key={g} className="flex items-center gap-1.5">
            <span className={`text-[9px] font-600 font-mono px-1 py-0.5 rounded border ${GROUNDING_STYLE[g]}`}>
              {GROUNDING_LABEL[g]}
            </span>
            <span className="text-[9px] text-navy-600">
              {g === "GROUNDED" ? "in source data" : g === "INFERRED" ? "logical inference" : "not in data"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

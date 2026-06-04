import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { ConfidenceBar } from "./ConfidenceBar";
import type { TickerAnalysis } from "../lib/types";

const ACTION_STYLE: Record<string, string> = {
  Buy:  "text-green-signal border-green-signal/40 bg-green-signal/10",
  Hold: "text-amber-accent border-amber-accent/40 bg-amber-accent/10",
  Sell: "text-red-signal   border-red-signal/40   bg-red-signal/10",
};

function fmt(n: number, d = 0) {
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function TickerSearch() {
  const [input, setInput] = useState("");
  const [searchTicker, setSearchTicker] = useState<string | null>(null);
  const [triggered, setTriggered] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const { data: statusData } = useQuery({
    queryKey: ["tickerRunStatus"],
    queryFn: api.tickerRunStatus,
    refetchInterval: triggered ? 1500 : false,
  });

  const isRunning = statusData?.running ?? false;

  useEffect(() => {
    if (triggered && !isRunning && statusData?.finished_at) {
      setTriggered(false);
      if (statusData.ticker) {
        setSearchTicker(statusData.ticker);
        qc.invalidateQueries({ queryKey: ["tickerAnalysis", statusData.ticker] });
      }
    }
  }, [isRunning, triggered, statusData, qc]);

  const { data: analysis, isFetching } = useQuery<TickerAnalysis>({
    queryKey: ["tickerAnalysis", searchTicker],
    queryFn: () => api.getTicker(searchTicker!),
    enabled: !!searchTicker && !isRunning,
    retry: false,
  });

  async function handleSearch() {
    const t = input.trim().toUpperCase();
    if (!t || isRunning) return;
    setSearchTicker(null);
    setTriggered(true);
    await api.runTicker(t);
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSearch();
  }

  const rec = analysis?.recommendation;
  const val = analysis?.valuation;
  const fund = analysis?.fundamental;

  return (
    <section className="bg-navy-900 rounded-xl border border-navy-800 p-6">
      <div className="mb-5">
        <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest mb-1">Single-Stock Analysis</h3>
        <p className="text-xs text-navy-600">
          Enter any ticker to run the full top-down pipeline — uses cached macro context, fetches live fundamentals.
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2 mb-6">
        <div className="relative flex-1 max-w-xs">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            onKeyDown={handleKey}
            placeholder="AAPL, NVDA, TSLA…"
            className="w-full bg-navy-800 border border-navy-700 rounded-lg px-4 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-cyan-accent/60 placeholder:text-navy-600 tracking-widest"
            disabled={isRunning}
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={isRunning || !input.trim()}
          className={`px-5 py-2.5 text-sm font-600 rounded-lg border transition-colors flex items-center gap-2 ${
            isRunning
              ? "border-amber-accent/30 bg-amber-accent/10 text-amber-accent cursor-not-allowed"
              : "border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent hover:bg-cyan-accent/20 disabled:opacity-40 disabled:cursor-not-allowed"
          }`}
        >
          {isRunning ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-amber-accent/40 border-t-amber-accent rounded-full animate-spin" />
              Analyzing {statusData?.ticker}…
            </>
          ) : "Analyze →"}
        </button>
      </div>

      {/* Error */}
      {statusData?.error && !isRunning && (
        <div className="text-xs text-red-signal bg-red-signal/10 border border-red-signal/30 rounded-lg px-4 py-2 mb-4">
          Analysis failed: {statusData.error}
        </div>
      )}

      {/* Loading */}
      {(isFetching || (isRunning)) && !rec && (
        <div className="flex items-center gap-3 py-8 justify-center text-navy-500 text-sm">
          <span className="w-4 h-4 border-2 border-navy-600 border-t-cyan-accent rounded-full animate-spin" />
          Running full analysis pipeline for {isRunning ? statusData?.ticker : searchTicker}…
        </div>
      )}

      {/* Results */}
      {rec && analysis && (
        <div className="space-y-5">
          {/* Header card */}
          <div className="flex items-start justify-between p-4 bg-navy-800/50 rounded-xl border border-navy-700/50">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <span className="font-display font-700 text-2xl text-white tracking-tight">{rec.ticker}</span>
                <span className={`text-xs font-600 px-2.5 py-1 rounded border ${ACTION_STYLE[rec.action] ?? ""}`}>
                  {rec.action}
                </span>
                <span className="text-[10px] font-mono text-navy-600">{analysis.as_of_date}</span>
              </div>
              {fund && (
                <p className="text-xs text-navy-400 leading-relaxed max-w-lg">{fund.narrative_quality}</p>
              )}
            </div>
            <div className="text-right space-y-1 shrink-0 ml-4">
              <div className="text-2xl font-mono font-700 text-white tabular-nums">
                ${fmt(rec.current_price, 2)}
              </div>
              <div className="text-xs text-navy-500">current price</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Valuation */}
            {val && (
              <div className="space-y-3">
                <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest">Valuation</h4>
                <div className="grid grid-cols-2 gap-2">
                  <Stat label="Target Price" value={`$${fmt(val.prob_weighted_target, 0)}`} />
                  <Stat
                    label="Expected Return"
                    value={
                      rec.action === "Sell"
                        ? `+${fmt(-val.expected_return_pct, 1)}% short`
                        : `${val.expected_return_pct > 0 ? "+" : ""}${fmt(val.expected_return_pct, 1)}%`
                    }
                    positive={rec.action === "Sell" ? val.expected_return_pct < 0 : val.expected_return_pct > 0}
                  />
                  <Stat label="Reward : Risk" value={`${fmt(val.reward_to_risk, 1)}×`} />
                  <Stat label="Confidence" value={`${rec.confidence_label} ${rec.confidence_numeric.toFixed(0)}`} />
                </div>

                <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest pt-1">Scenarios</h4>
                <div className="space-y-1.5">
                  {val.scenario_valuations.map(sv => (
                    <div key={sv.scenario_name} className="flex items-center justify-between text-xs bg-navy-900/60 rounded-lg px-3 py-2 border border-navy-800/60">
                      <span className="text-navy-400 w-24">{sv.scenario_name}</span>
                      <span className="text-navy-600 font-mono">{(sv.probability * 100).toFixed(0)}%</span>
                      <span className="font-mono text-white">${sv.blended_value.toFixed(0)}</span>
                      <span className={`font-mono font-600 ${sv.upside_pct > 0 ? "text-green-signal" : "text-red-signal"}`}>
                        {sv.upside_pct > 0 ? "+" : ""}{sv.upside_pct.toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Fundamentals */}
            {fund && (
              <div className="space-y-3">
                <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest">Fundamentals</h4>
                <div className="grid grid-cols-2 gap-2">
                  <Stat label="Life Cycle" value={fund.industry_life_cycle} />
                  <Stat label="Business Model" value={fund.business_model_type} />
                  <Stat label="Porter Score" value={`${fund.porter.overall_score}/10`} />
                  <Stat label="Quality Score" value={`${fund.qualitative_score.toFixed(0)}/100`} />
                </div>

                {(rec.warnings.length > 0 || fund.key_risks.length > 0) && (
                  <>
                    <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest pt-1">Key Risks</h4>
                    <div className="space-y-1">
                      {rec.warnings.map((w, i) => (
                        <div key={i} className="flex gap-2 text-xs text-amber-accent">
                          <span>⚠</span><span>{w}</span>
                        </div>
                      ))}
                      {fund.key_risks.map((r, i) => (
                        <div key={i} className="flex gap-2 text-xs text-navy-400">
                          <span className="text-navy-600">·</span><span>{r}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Thesis */}
          {rec.thesis && (
            <div>
              <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Investment Thesis</h4>
              <p className="text-sm text-navy-300 leading-relaxed">{rec.thesis}</p>
            </div>
          )}

          {/* Confidence breakdown */}
          <div>
            <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Confidence Breakdown</h4>
            <ConfidenceBar breakdown={rec.confidence_breakdown} total={rec.confidence_numeric} />
          </div>
        </div>
      )}

      {/* Empty state */}
      {!rec && !isRunning && !isFetching && (
        <div className="text-center py-10 space-y-2">
          <div className="text-3xl text-navy-700">⌕</div>
          <p className="text-sm text-navy-600">Search any S&amp;P 500 ticker to run a live top-down analysis.</p>
          <p className="text-xs text-navy-700">Takes ~20–40s for live data fetch and full pipeline.</p>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const color = positive === undefined
    ? "text-white"
    : positive ? "text-green-signal" : "text-red-signal";
  return (
    <div className="bg-navy-800/40 rounded-lg px-3 py-2 border border-navy-700/30">
      <div className="text-[10px] text-navy-600 uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`text-sm font-mono font-600 ${color}`}>{value}</div>
    </div>
  );
}

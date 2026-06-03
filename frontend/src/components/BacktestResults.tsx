import type { BacktestData } from "../lib/types";

interface Props {
  data: BacktestData;
}

function MetricCard({ label, value, sub, positive }: { label: string; value: string; sub?: string; positive?: boolean }) {
  const color = positive === undefined ? "text-white" : positive ? "text-green-signal" : "text-red-signal";
  return (
    <div className="bg-navy-800/50 rounded-lg px-4 py-3 border border-navy-700/40">
      <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-mono font-700 text-lg tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-navy-600 mt-0.5">{sub}</div>}
    </div>
  );
}

const REGIME_COLOR: Record<string, string> = {
  REFLATION:   "bg-cyan-accent/20 text-cyan-accent",
  INFLATION:   "bg-amber-accent/20 text-amber-accent",
  STAGFLATION: "bg-red-signal/20 text-red-signal",
  DEFLATION:   "bg-navy-700/40 text-navy-400",
};

export function BacktestResults({ data }: Props) {
  const { metrics, annual_returns, top_contributors, worst_contributors, methodology } = data;

  return (
    <div className="space-y-6">
      {/* Metrics grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <MetricCard label="Strategy CAGR" value={`${metrics.cagr_pct.toFixed(1)}%`} positive={metrics.cagr_pct > 0} />
        <MetricCard label="Benchmark CAGR" value={`${metrics.benchmark_cagr_pct.toFixed(1)}%`} />
        <MetricCard label="Alpha" value={`${metrics.alpha_pct > 0 ? "+" : ""}${metrics.alpha_pct.toFixed(1)}%`} positive={metrics.alpha_pct > 0} />
        <MetricCard label="Beta" value={metrics.beta.toFixed(2)} />
        <MetricCard label="Sharpe Ratio" value={metrics.sharpe_ratio.toFixed(2)} positive={metrics.sharpe_ratio > 1} />
        <MetricCard label="Sortino Ratio" value={metrics.sortino_ratio.toFixed(2)} positive={metrics.sortino_ratio > 1} />
        <MetricCard label="Max Drawdown" value={`${metrics.max_drawdown_pct.toFixed(1)}%`} positive={false} />
        <MetricCard label="Calmar Ratio" value={metrics.calmar_ratio.toFixed(2)} positive={metrics.calmar_ratio > 0.5} />
        <MetricCard label="Win Rate" value={`${metrics.win_rate_pct.toFixed(1)}%`} positive={metrics.win_rate_pct > 50} />
        <MetricCard
          label="Outperformance"
          value={`${metrics.outperformance_months}/${metrics.total_months} mo`}
          sub={`${((metrics.outperformance_months / metrics.total_months) * 100).toFixed(0)}% of months`}
        />
        <MetricCard label="Period" value={metrics.backtest_start} sub={`→ ${metrics.backtest_end}`} />
        <MetricCard label="Duration" value={`${metrics.total_months} mo`} sub="~10 years" />
      </div>

      {/* Annual returns */}
      <div>
        <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-3">Annual Returns vs Benchmark</h4>
        <div className="space-y-2">
          {annual_returns.map(row => {
            return (
              <div key={row.year} className="grid grid-cols-[48px_1fr_60px_60px_60px_80px] gap-3 items-center text-xs">
                <span className="font-mono text-navy-400">{row.year}</span>
                <div className="relative h-5 bg-navy-800/50 rounded overflow-hidden">
                  {/* benchmark bar */}
                  <div
                    className="absolute top-0 h-full bg-navy-600/40 rounded"
                    style={{ width: `${Math.min(Math.abs(row.benchmark_pct) * 1.5, 100)}%`, left: "0" }}
                  />
                  {/* strategy bar */}
                  <div
                    className={`absolute top-0 h-full rounded ${row.strategy_pct >= 0 ? "bg-cyan-accent/50" : "bg-red-signal/50"}`}
                    style={{ width: `${Math.min(Math.abs(row.strategy_pct) * 1.5, 100)}%`, left: "0" }}
                  />
                </div>
                <span className={`font-mono tabular-nums text-right ${row.strategy_pct >= 0 ? "text-green-signal" : "text-red-signal"}`}>
                  {row.strategy_pct > 0 ? "+" : ""}{row.strategy_pct.toFixed(1)}%
                </span>
                <span className="font-mono tabular-nums text-right text-navy-400">
                  {row.benchmark_pct > 0 ? "+" : ""}{row.benchmark_pct.toFixed(1)}%
                </span>
                <span className={`font-mono tabular-nums text-right ${row.excess_pct >= 0 ? "text-cyan-accent" : "text-amber-accent"}`}>
                  {row.excess_pct > 0 ? "+" : ""}{row.excess_pct.toFixed(1)}%
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded text-center ${REGIME_COLOR[row.regime] ?? "bg-navy-700/30 text-navy-400"}`}>
                  {row.regime}
                </span>
              </div>
            );
          })}
        </div>
        <div className="grid grid-cols-[48px_1fr_60px_60px_60px_80px] gap-3 mt-1 text-[10px] text-navy-600">
          <span />
          <span />
          <span className="text-right">Strategy</span>
          <span className="text-right">SPY</span>
          <span className="text-right">Alpha</span>
          <span className="text-center">Regime</span>
        </div>
      </div>

      {/* Contributors */}
      <div className="grid grid-cols-2 gap-6">
        <div>
          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Top Contributors</h4>
          <div className="space-y-1">
            {top_contributors.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-green-signal">▲</span>
                <span className="text-navy-300">{t}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Worst Contributors</h4>
          <div className="space-y-1">
            {worst_contributors.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-red-signal">▼</span>
                <span className="text-navy-300">{t}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Methodology */}
      <div className="border-t border-navy-700/40 pt-4">
        <h4 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-2">Methodology</h4>
        <p className="text-xs text-navy-500 leading-relaxed">{methodology}</p>
      </div>
    </div>
  );
}

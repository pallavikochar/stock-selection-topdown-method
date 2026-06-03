import type { SECFilingsData } from "../lib/types";

interface Props {
  data: SECFilingsData;
}

function fmtM(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  if (abs >= 1000) return `$${(v / 1000).toFixed(1)}B`;
  return `$${v.toFixed(0)}M`;
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${v.toFixed(1)}%`;
}

function KpiCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const color = positive === undefined ? "text-white" : positive ? "text-green-signal" : "text-red-signal";
  return (
    <div className="bg-navy-900/50 rounded-lg px-3 py-2.5 border border-navy-800/50">
      <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-mono text-sm font-600 ${color}`}>{value}</div>
    </div>
  );
}

export function FinancialsPanel({ data }: Props) {
  const sorted = [...data.annual].sort((a, b) => b.year - a.year);
  const maxRev = Math.max(...sorted.map(r => r.revenue ?? 0), 1);

  return (
    <div className="space-y-5">
      {/* Key metrics row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Rev CAGR 3yr" value={fmtPct(data.revenue_cagr_3yr_pct)} positive={(data.revenue_cagr_3yr_pct ?? 0) > 0} />
        <KpiCard label="FCF Yield" value={fmtPct(data.fcf_yield_pct)} positive={(data.fcf_yield_pct ?? 0) > 0} />
        <KpiCard label="Debt/Equity" value={data.debt_to_equity !== null ? data.debt_to_equity.toFixed(2) + "×" : "—"} positive={(data.debt_to_equity ?? 99) < 2} />
        <KpiCard label="Current Ratio" value={data.current_ratio !== null ? data.current_ratio.toFixed(2) + "×" : "—"} positive={(data.current_ratio ?? 0) > 1} />
        <KpiCard label="ROE" value={fmtPct(data.return_on_equity_pct)} positive={(data.return_on_equity_pct ?? 0) > 10} />
      </div>

      {/* Annual table */}
      <div>
        <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-2">Annual Financials</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-navy-800/60 text-navy-500">
                <th className="text-left pb-2 font-400">Year</th>
                <th className="text-right pb-2 font-400">Revenue</th>
                <th className="text-right pb-2 font-400 hidden sm:table-cell">Gross M%</th>
                <th className="text-right pb-2 font-400">Op Income</th>
                <th className="text-right pb-2 font-400 hidden sm:table-cell">Op M%</th>
                <th className="text-right pb-2 font-400">Net Income</th>
                <th className="text-right pb-2 font-400">FCF</th>
                <th className="text-right pb-2 font-400 hidden md:table-cell">EPS</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(row => (
                <tr key={row.year} className="border-b border-navy-800/30 hover:bg-navy-800/20 transition-colors">
                  <td className="py-2 font-mono text-navy-400">{row.year}</td>
                  <td className="py-2 font-mono text-right text-white">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1.5 rounded-full bg-cyan-accent/30" style={{ width: `${(row.revenue ?? 0) / maxRev * 48}px` }} />
                      {fmtM(row.revenue)}
                    </div>
                  </td>
                  <td className="py-2 font-mono text-right text-navy-300 hidden sm:table-cell">{fmtPct(row.gross_margin)}</td>
                  <td className={`py-2 font-mono text-right ${(row.operating_income ?? 0) >= 0 ? "text-white" : "text-red-signal"}`}>
                    {fmtM(row.operating_income)}
                  </td>
                  <td className="py-2 font-mono text-right text-navy-300 hidden sm:table-cell">{fmtPct(row.operating_margin)}</td>
                  <td className={`py-2 font-mono text-right ${(row.net_income ?? 0) >= 0 ? "text-white" : "text-red-signal"}`}>
                    {fmtM(row.net_income)}
                  </td>
                  <td className={`py-2 font-mono text-right ${(row.free_cash_flow ?? 0) >= 0 ? "text-cyan-accent" : "text-amber-accent"}`}>
                    {fmtM(row.free_cash_flow)}
                  </td>
                  <td className="py-2 font-mono text-right text-navy-300 hidden md:table-cell">
                    {row.eps_basic !== null ? `$${row.eps_basic.toFixed(2)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(data.latest_10k_period || data.latest_10q_period) && (
          <div className="flex gap-4 mt-2 text-[10px] text-navy-600">
            {data.latest_10k_period && <span>Latest 10-K: {data.latest_10k_period}</span>}
            {data.latest_10q_period && <span>Latest 10-Q: {data.latest_10q_period}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

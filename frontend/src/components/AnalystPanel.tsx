import type { AnalystConsensus } from "../lib/types";

interface Props {
  data: AnalystConsensus;
}

const CONSENSUS_STYLE: Record<string, string> = {
  "Strong Buy":  "text-green-signal border-green-signal/40 bg-green-signal/10",
  "Buy":         "text-cyan-accent  border-cyan-accent/40  bg-cyan-accent/10",
  "Hold":        "text-amber-accent border-amber-accent/40 bg-amber-accent/10",
  "Underperform":"text-red-signal   border-red-signal/40   bg-red-signal/10",
  "Sell":        "text-red-signal   border-red-signal/40   bg-red-signal/10",
};

function fmt(n: number | null, decimals = 0, prefix = "") {
  if (n === null || n === undefined) return "—";
  return prefix + n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function AnalystPanel({ data }: Props) {
  const total = data.buy_count + data.hold_count + data.sell_count;
  const buyPct  = total > 0 ? (data.buy_count  / total) * 100 : 0;
  const holdPct = total > 0 ? (data.hold_count / total) * 100 : 0;
  const sellPct = total > 0 ? (data.sell_count / total) * 100 : 0;

  const consensusKey = data.consensus
    .split(" ")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
  const badgeStyle = CONSENSUS_STYLE[consensusKey] ?? "text-navy-400 border-navy-600 bg-navy-800/40";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-600 px-2 py-1 rounded border ${badgeStyle}`}>
          {data.consensus} · {data.num_analysts} analysts
        </span>
        {data.upside_to_mean_pct !== null && (
          <span className={`text-sm font-mono font-600 ${data.upside_to_mean_pct > 0 ? "text-green-signal" : "text-red-signal"}`}>
            {data.upside_to_mean_pct > 0 ? "+" : ""}{fmt(data.upside_to_mean_pct, 1)}% to mean target
          </span>
        )}
      </div>

      {/* Price targets */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-navy-900/50 rounded-lg px-3 py-2.5 border border-navy-800/50 text-center">
          <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">Low Target</div>
          <div className="font-mono text-sm text-navy-300">{fmt(data.low_target, 0, "$")}</div>
        </div>
        <div className="bg-navy-900/50 rounded-lg px-3 py-2.5 border border-cyan-accent/20 text-center">
          <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">Mean Target</div>
          <div className="font-mono text-sm text-white font-600">{fmt(data.mean_target, 0, "$")}</div>
        </div>
        <div className="bg-navy-900/50 rounded-lg px-3 py-2.5 border border-navy-800/50 text-center">
          <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">High Target</div>
          <div className="font-mono text-sm text-navy-300">{fmt(data.high_target, 0, "$")}</div>
        </div>
      </div>

      {/* Buy/Hold/Sell bar */}
      {total > 0 && (
        <div>
          <div className="flex rounded-full overflow-hidden h-2 mb-2">
            {buyPct  > 0 && <div className="bg-green-signal transition-all" style={{ width: `${buyPct}%` }} />}
            {holdPct > 0 && <div className="bg-amber-accent transition-all" style={{ width: `${holdPct}%` }} />}
            {sellPct > 0 && <div className="bg-red-signal  transition-all" style={{ width: `${sellPct}%` }} />}
          </div>
          <div className="flex gap-4 text-[10px] text-navy-500">
            <span><span className="text-green-signal font-600">Buy {data.buy_count}</span> ({buyPct.toFixed(0)}%)</span>
            <span><span className="text-amber-accent font-600">Hold {data.hold_count}</span> ({holdPct.toFixed(0)}%)</span>
            <span><span className="text-red-signal font-600">Sell {data.sell_count}</span> ({sellPct.toFixed(0)}%)</span>
          </div>
        </div>
      )}
    </div>
  );
}

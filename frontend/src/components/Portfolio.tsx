import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

interface Position {
  id: string;
  ticker: string;
  shares: number;
  purchase_price: number;
  purchase_date: string;
}

function fmt(n: number, d = 0) {
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

const STORAGE_KEY = "apm_portfolio_v1";

function loadPositions(): Position[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

export function Portfolio() {
  const [positions, setPositions] = useState<Position[]>(loadPositions);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ticker: "", shares: "", purchase_price: "", purchase_date: "" });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
  }, [positions]);

  const tickers = [...new Set(positions.map(p => p.ticker))];

  const { data: pricesData, isLoading } = useQuery({
    queryKey: ["portfolio_prices", tickers.join(",")],
    queryFn: () => api.portfolioPrices(tickers),
    enabled: tickers.length > 0,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const prices = pricesData?.prices ?? {};

  function addPosition() {
    const t = form.ticker.trim().toUpperCase();
    if (!t || !form.shares || !form.purchase_price) return;
    setPositions(prev => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random()}`,
        ticker: t,
        shares: parseFloat(form.shares),
        purchase_price: parseFloat(form.purchase_price),
        purchase_date: form.purchase_date || new Date().toISOString().slice(0, 10),
      },
    ]);
    setForm({ ticker: "", shares: "", purchase_price: "", purchase_date: "" });
    setShowForm(false);
  }

  function removePosition(id: string) {
    setPositions(prev => prev.filter(p => p.id !== id));
  }

  const positionsWithPnl = positions.map(p => {
    const currentPrice = prices[p.ticker]?.current_price ?? 0;
    const cost = p.shares * p.purchase_price;
    const value = currentPrice > 0 ? p.shares * currentPrice : 0;
    const pnl = value - cost;
    const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0;
    return { ...p, currentPrice, cost, value, pnl, pnlPct };
  });

  const totalCost = positionsWithPnl.reduce((s, p) => s + p.cost, 0);
  const totalValue = positionsWithPnl.reduce((s, p) => s + p.value, 0);
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const pricesReady = !isLoading && tickers.length > 0;

  return (
    <section className="bg-navy-900 rounded-xl border border-navy-800 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">My Portfolio</h3>
          <p className="text-xs text-navy-600 mt-0.5">Track positions and monitor P&amp;L with live prices</p>
        </div>
        <button
          onClick={() => setShowForm(s => !s)}
          className="text-xs px-3 py-1.5 rounded border font-600 border-cyan-accent/30 text-cyan-accent hover:bg-cyan-accent/10 transition-colors"
        >
          + Add Position
        </button>
      </div>

      {/* Add position form */}
      {showForm && (
        <div className="mb-6 p-4 bg-navy-800/50 rounded-lg border border-navy-700/50">
          <h4 className="text-xs font-600 text-navy-400 uppercase tracking-widest mb-3">New Position</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { key: "ticker",         label: "Ticker",         placeholder: "AAPL",       type: "text" },
              { key: "shares",         label: "Shares",         placeholder: "100",        type: "number" },
              { key: "purchase_price", label: "Purchase Price", placeholder: "150.00",     type: "number" },
              { key: "purchase_date",  label: "Purchase Date",  placeholder: "",           type: "date" },
            ].map(({ key, label, placeholder, type }) => (
              <div key={key}>
                <label className="text-[10px] text-navy-500 uppercase tracking-wider block mb-1">{label}</label>
                <input
                  type={type}
                  placeholder={placeholder}
                  value={form[key as keyof typeof form]}
                  onChange={e => {
                    const val = key === "ticker" ? e.target.value.toUpperCase() : e.target.value;
                    setForm(f => ({ ...f, [key]: val }));
                  }}
                  className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1.5 text-sm text-white font-mono focus:outline-none focus:border-cyan-accent/60 placeholder:text-navy-700"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={addPosition}
              className="text-xs px-4 py-1.5 bg-cyan-accent text-navy-950 font-600 rounded hover:opacity-90 transition-opacity"
            >
              Add
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="text-xs px-4 py-1.5 text-navy-500 hover:text-navy-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {positions.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <div className="text-3xl text-navy-700">◫</div>
          <p className="text-sm text-navy-600">No positions yet.</p>
          <p className="text-xs text-navy-700">Click &quot;+ Add Position&quot; to track your first holding.</p>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <SummaryCard label="Total Invested"  value={`$${fmt(totalCost)}`} />
            <SummaryCard label="Current Value"   value={pricesReady ? `$${fmt(totalValue)}` : "…"} />
            <SummaryCard
              label="Total P&L"
              value={pricesReady ? `${totalPnl >= 0 ? "+" : "-"}$${fmt(Math.abs(totalPnl))}` : "…"}
              positive={pricesReady ? totalPnl >= 0 : undefined}
            />
            <SummaryCard
              label="Total Return"
              value={pricesReady ? `${totalPnlPct >= 0 ? "+" : ""}${fmt(totalPnlPct, 1)}%` : "…"}
              positive={pricesReady ? totalPnlPct >= 0 : undefined}
            />
          </div>

          {/* Positions table */}
          <div className="space-y-1">
            {/* Header */}
            <div className="grid gap-2 px-3 py-2 text-[10px] text-navy-600 uppercase tracking-widest border-b border-navy-800"
              style={{ gridTemplateColumns: "72px 100px 70px 80px 80px 90px 100px 32px" }}>
              <span>Ticker</span>
              <span>Bought</span>
              <span className="text-right">Shares</span>
              <span className="text-right">Buy $</span>
              <span className="text-right">Now $</span>
              <span className="text-right">Value</span>
              <span className="text-right">P&amp;L</span>
              <span />
            </div>

            {positionsWithPnl.map(p => (
              <div
                key={p.id}
                className="grid gap-2 px-3 py-2.5 rounded-lg bg-navy-800/30 border border-transparent hover:border-navy-700/50 items-center text-sm"
                style={{ gridTemplateColumns: "72px 100px 70px 80px 80px 90px 100px 32px" }}
              >
                <span className="font-display font-700 text-white text-sm">{p.ticker}</span>
                <span className="font-mono text-navy-500 text-xs">{p.purchase_date}</span>
                <span className="text-right font-mono tabular-nums text-navy-400 text-xs">{fmt(p.shares, p.shares % 1 === 0 ? 0 : 2)}</span>
                <span className="text-right font-mono tabular-nums text-navy-400 text-xs">${fmt(p.purchase_price, 2)}</span>
                <span className="text-right font-mono tabular-nums text-white text-xs">
                  {isLoading ? "…" : p.currentPrice ? `$${fmt(p.currentPrice, 2)}` : "N/A"}
                </span>
                <span className="text-right font-mono tabular-nums text-white text-xs">
                  {pricesReady && p.value ? `$${fmt(p.value, 0)}` : "…"}
                </span>
                <div className="text-right">
                  <div className={`font-mono tabular-nums font-600 text-xs ${p.pnl >= 0 ? "text-green-signal" : "text-red-signal"}`}>
                    {pricesReady && p.currentPrice
                      ? `${p.pnlPct >= 0 ? "+" : ""}${fmt(p.pnlPct, 1)}%`
                      : "…"}
                  </div>
                  <div className={`font-mono tabular-nums text-[10px] mt-0.5 ${p.pnl >= 0 ? "text-green-signal/60" : "text-red-signal/60"}`}>
                    {pricesReady && p.currentPrice
                      ? `${p.pnl >= 0 ? "+" : "-"}$${fmt(Math.abs(p.pnl), 0)}`
                      : ""}
                  </div>
                </div>
                <button
                  onClick={() => removePosition(p.id)}
                  className="text-navy-700 hover:text-red-signal transition-colors text-xs text-right"
                  title="Remove position"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          {tickers.length > 0 && (
            <p className="text-[10px] text-navy-700 mt-3 text-right">
              Prices refresh every 60s · Stored in browser localStorage
            </p>
          )}
        </>
      )}
    </section>
  );
}

function SummaryCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  const color = positive === undefined
    ? "text-white"
    : positive ? "text-green-signal" : "text-red-signal";
  return (
    <div className="bg-navy-800/50 rounded-lg px-4 py-3 border border-navy-700/40">
      <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`font-mono font-700 text-lg tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

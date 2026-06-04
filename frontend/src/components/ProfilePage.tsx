export function ProfilePage() {
  return (
    <div className="max-w-2xl mx-auto py-12 space-y-8">
      {/* Identity card */}
      <div className="bg-navy-900 rounded-xl border border-navy-800 p-8">
        <div className="flex items-start gap-6">
          <div className="w-16 h-16 rounded-full bg-cyan-accent/10 border-2 border-cyan-accent/30 flex items-center justify-center text-2xl font-display font-700 text-cyan-accent shrink-0">
            PK
          </div>
          <div>
            <h1 className="text-2xl font-display font-700 text-white tracking-tight mb-1">Pallavi Kochar</h1>
            <p className="text-sm text-cyan-accent font-600 mb-3">FIN 419 / FIN 589 · Active Portfolio Management</p>
            <p className="text-xs text-navy-500 font-mono">University of Illinois Urbana-Champaign</p>
            <p className="text-xs text-navy-600 font-mono mt-0.5">pallavi5kochar@gmail.com</p>
          </div>
        </div>
      </div>

      {/* About this project */}
      <div className="bg-navy-900 rounded-xl border border-navy-800 p-6 space-y-4">
        <h2 className="text-xs font-600 text-navy-500 uppercase tracking-widest">About Project DOIT</h2>
        <p className="text-sm text-navy-300 leading-relaxed">
          A multi-agent quantamental investment engine implementing the top-down portfolio management
          process. The system chains 15 specialized agents — from macro regime detection to single-stock
          valuation — replicating the institutional research workflow used by buy-side analysts.
        </p>
        <p className="text-sm text-navy-400 leading-relaxed">
          Built for the APM course at UIUC as a full-stack demonstration of quantamental investing:
          macro explains ~70% of a stock's move, so the process starts at the economy and works down
          to individual security selection.
        </p>
      </div>

      {/* Methodology */}
      <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
        <h2 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-4">Methodology Stack</h2>
        <div className="space-y-2">
          {[
            { step: "01", label: "Economy Agent",          desc: "CMI score · yield curve · PMI · credit spreads · H.O.P.E." },
            { step: "02", label: "Cycle Agent",             desc: "Merrill Lynch Investment Clock · REFLATION / INFLATION / STAGFLATION / DEFLATION" },
            { step: "03", label: "Scenario Agent",          desc: "Bull / Base / Bear macro assumptions with probabilities" },
            { step: "04", label: "Sector Agent",            desc: "11 GICS sectors scored on macro tailwinds / headwinds" },
            { step: "05", label: "Style Agent",             desc: "Factor tilts — value vs. growth, duration sensitivity" },
            { step: "06", label: "Screen Agent",            desc: "Magic Formula + Greenblatt EBIT/EV ranking across universe" },
            { step: "07", label: "Fundamental Agent",       desc: "Porter's Five Forces · life cycle · qualitative quality score" },
            { step: "08", label: "Valuation Agent",         desc: "6-step DCF + multiples + sector-specific leg (Gordon P/B, DDM, EV/EBITDA)" },
            { step: "09", label: "Risk Agent",              desc: "Correlation regime · drawdown analysis · position sizing" },
            { step: "10", label: "Recommendation Agent",    desc: "Buy / Hold / Sell with probability-weighted targets and R:R" },
            { step: "15", label: "Backtest Agent",          desc: "10-year sector rotation vs SPY · CAGR · Alpha · Sharpe · Sortino" },
          ].map(({ step, label, desc }) => (
            <div key={step} className="flex gap-4 items-start py-2 border-b border-navy-800/50 last:border-0">
              <span className="text-[10px] font-mono text-navy-700 w-5 shrink-0 pt-0.5">{step}</span>
              <div>
                <span className="text-xs font-600 text-navy-300">{label}</span>
                <span className="text-xs text-navy-600 ml-2">— {desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stack */}
      <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
        <h2 className="text-xs font-600 text-navy-500 uppercase tracking-widest mb-4">Tech Stack</h2>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Backend",   value: "Python 3.12 · FastAPI · Pydantic v2" },
            { label: "Frontend",  value: "React 19 · TypeScript · Tailwind v4" },
            { label: "Data",      value: "yfinance · FRED API · SEC EDGAR" },
            { label: "AI Layer",  value: "Claude (Anthropic) · LLM analysis agent" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-navy-800/40 rounded-lg px-4 py-3 border border-navy-700/30">
              <div className="text-[10px] text-navy-600 uppercase tracking-wider mb-1">{label}</div>
              <div className="text-xs text-navy-300 font-mono">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

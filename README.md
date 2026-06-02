# Project APM — Multi-Agent Top-Down Quantamental Engine

> *"From the economy down to the stock — macro explains ~70% of a stock's move."*
> — Piper Sandler Field Guide to Macro & Markets / FIN 419/589 Applied Portfolio Management, UIUC

---

## What This Is

Project APM is a Python multi-agent system that runs an explicitly **top-down** investment process:

```
Economy → Cycle/H.O.P.E. → Scenarios → Sector → Style/Factor → Screen → Fundamental → Valuation → Risk → Recommendation → Report
```

Each layer is a separate **agent** that does one job, writes a structured JSON output, and hands off to the next. A React frontend renders the entire funnel visually, making the top-down direction unmistakable.

---

## Quick Start

### Prerequisites
- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ with [`pnpm`](https://pnpm.io/)

### 1. Install Python dependencies
```bash
uv sync
```

### 2. Run the demo pipeline (no API keys needed)
```bash
python -m apm run --demo
```
This runs all 11 agents on cached data and writes outputs to `output/agents/*.json`.

### 3. Start the API
```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Start the frontend
```bash
cd frontend
pnpm install
pnpm dev
```
Open http://localhost:5173 — the Top-Down Funnel renders immediately on demo data.

### CLI options
```bash
python -m apm run --demo                    # full demo run
python -m apm run --demo --report           # + write output/report.md
python -m apm run --demo --agent economy    # run only EconomyAgent
python -m apm run --demo --from sector      # resume from SectorAgent
python -m apm run --log-level DEBUG         # verbose per-agent logging
```

### Live mode (with API keys)
```bash
export FRED_API_KEY=your_fred_key
python -m apm run                           # live FRED + yfinance data
```

---

## Methodology: Top-Down Process

### Governing philosophy
- **Macro dominates.** Piper Sandler: ~70% of a stock's movement is explained by macro (market/sector/industry). Brinson et al.: >90% of long-term return variance comes from asset allocation. The macro/cycle/sector/style layers carry the heaviest weight in the confidence score.
- **"Trends → business cycle → sector → factor as a screen."** The economic view decides *where to look*; it does NOT forecast individual stock prices.
- **"The qualitative analysis informs the quantitative analysis, not the other way around."**
- **Scenario analysis is mandatory, not sensitivity analysis.** ≥3 scenarios per stock; every stock must have a realistic downside.
- **Markets move WITH leading indicators** (LEIs). Forecast where LEIs are headed, not where they are.
- **Valuation is a condition, not a catalyst.** Use multiples cross-sectionally vs. current peers; never as a time-series timing signal.

---

## Agent Reference

| # | Agent | Job | Key output |
|---|-------|-----|-----------|
| 1 | `EconomyAgent` | Growth + inflation read; CMI; LEI forecast | `EconomyData` |
| 2 | `CycleAgent` | Investment Clock phase; H.O.P.E. stage | `CycleData` |
| 3 | `ScenarioAgent` | Scenario set (must sum to 1.0) | `ScenariosData` |
| 4 | `SectorAgent` | Sector ranking by macro-variable correlations | `SectorData` |
| 5 | `StyleAgent` | Factor/style selection for the phase | `StyleData` |
| 6 | `ScreenAgent` | Magic Formula ranking + sector/style filter | `ScreenData` |
| 7 | `FundamentalAgent` | Porter's Five Forces + narrative + value drivers | `FundamentalData` |
| 8 | `ValuationAgent` | DCF + multiples per scenario; R:R | `ValuationData` |
| 9 | `RiskCorrelationAgent` | Correlation regime; stock-picking reward | `RiskData` |
| 10 | `RecommendationAgent` | Confidence score; ranked recommendations | `RecommendationsData` |
| 11 | `ReportAgent` | Markdown report | `output/report.md` |

---

## Tunable Assumptions (All Config-Driven)

> Update these in `config/` without touching any Python code.
> All assumptions and their rationale are documented here so the context survives across sessions.

### `config/scenarios.yaml` — Scenario Probabilities

**Current settings:** Base 55% / Bull 25% / Bear 20%

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `base_case.probability` | 0.55 | Stagflation / soft-landing base in current cycle |
| `bull_case.probability` | 0.25 | Re-acceleration if Fed cuts early or oil falls |
| `bear_case.probability` | 0.20 | Recession if credit cracks or HOPE transmits faster |
| **Sum** | **1.00** | **Validated at runtime — will error if wrong** |

**TUNABLE:** Change these to reflect your current view. The base case must remain identical across all stocks. Alternative scenarios (bull/bear) can vary per company but the base cannot (per RCMP methodology).

**Key per-scenario macro inputs:**
- `gdp_growth_pct` — Real GDP YoY; drives revenue growth proxy
- `margin_trajectory` — `"compressed"`, `"stable"`, `"recovering"`, `"expanding"`, `"collapsing"`
- `market_multiple_path` — `"flat"`, `"expanding"`, `"compressing"` — in bear cases the sector multiple itself compresses (not just earnings)
- `earnings_growth_pct` — Used in multiples valuation

### `config/economic_view.yaml` — Current Macro View

**TUNABLE:** Update monthly with new FRED data releases.

| Variable | Current | What it drives |
|----------|---------|---------------|
| `growth.level` | `above_trend` | Investment Clock quadrant |
| `growth.direction` | `falling` | Clockwise rotation signal |
| `inflation.direction` | `rising` | Clock phase (Inflation vs. Stagflation) |
| `leading_indicators.ism_new_orders` | 48.1 | PMI proxy; primary LEI; earnings proxy |
| `leading_indicators.nahb_index` | 43 | H.O.P.E. Housing stage |
| `market.ten_year_yield_pct` | 4.65 | Rates → P/E regime; sector rotations |
| `market.baa_credit_spread_pct` | 1.72 | Risk regime; Financials/Staples/HC correlations |
| `overrides.force_clock_phase` | `null` | Set to e.g. `"STAGFLATION"` to override the agent's computed phase |

### `config/weights.yaml` — Confidence Score Weights

**TUNABLE:** Weights reflect the ~70% macro / Brinson 90% doctrine. Adjust if your process differs.

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Macro/cycle conviction | 30 | Heaviest — clock phase fit + CMI clarity |
| Sector fit | 20 | Asset allocation dominates long-run returns |
| Style/factor fit | 15 | Factor exposure for the phase |
| Reward-to-risk | 15 | Scenario-weighted upside/downside |
| Fundamental quality | 8 | Porter + narrative + ROIC |
| Cross-sectional valuation | 5 | Cheap vs. current peers only |
| Technical catalyst | 4 | 20/200-day MA + intermarket |
| Stock-picking regime | 3 | Low correlation = higher conviction |

**Penalties (reduce score after base):**
- No downside scenario: −15 (model integrity failure)
- Crowding: −10 (consensus Buy = crowded trade)
- Terminal growth rate too high: −8
- Factor thesis doesn't hold cross-universe: −5

**Confidence thresholds:** Low < 50 ≤ Medium < 75 ≤ High

### `config/sector_macro_corr.yaml` — Sector × Macro Correlations

Source: Piper Sandler Field Guide. **Do not change without fresh empirical data.**

Key values to know:
- **Staples**: PMI −0.74, Copper −0.83, BAA +0.75 — the most defensive sector
- **Energy**: 10yr +0.77, Oil +0.57 — rates AND oil rising = doubly favored
- **Tech**: 10yr −0.56 — most rate-sensitive large-cap sector
- **Financials**: BAA −0.66 — hardest hit when credit spreads blow out
- **Health Care**: Oil −0.73 — unique: outperforms most when oil *falls*

### `config/sector_cyclicality.yaml` — Cyclicality Spectrum

Piper Sandler order (most → least cyclical):
**Energy → Real Estate → Materials → Financials → Comm Services → Discretionary → Industrials → Tech → Health Care → Utilities → Staples**

TUNABLE: Ordering is empirical from the Field Guide. Do not change without strong justification.

### `config/phase_factor_leaders.yaml` — Factor Leadership by Phase

**Recovery** (growth just turned up): High Beta, Low P/E NTM, Small Cap Value  
**Expansion** (strong, broadening): High Book Yield, Low P/E NTM, High Cash Flow Yield  
**Quality** (late cycle, peak): High FCF Yield, High Div Yield, Low EPS Variance  
**Growth_Slowdown** (decelerating): High EPS Growth, Low Sales Variance, High ROIC  
**Trough** (downturn): Low Beta, Low D/E, High Interest Coverage  

**TUNABLE:** Weights within each phase reflect Field Guide rankings. Adjust if your phase call differs from what the agent computes.

### `config/factor_macro_corr.yaml` — Factor Cyclicality

Key non-obvious fact:
> **High Dividend Yield is a CYCLICAL factor** (positive correlation with beta/leverage). Dividend ETFs carry huge sector biases (Energy, Financials, Utilities). Do **not** assume dividend yield = defensive.

**Countercyclical factors** (outperform when growth slows): ROE, EPS Growth, FCF Yield, Low Volatility, Low Beta, ROIC, Low D/E

### `config/hope_sequence.yaml` — H.O.P.E. Transmission Lags

Rate change → **Housing** (1–6m) → **Orders** (4–10m) → **Profits** (7–15m) → **Employment** (12–24m) → Inflation rolls over at the end.

**Current phase: Orders** — NAHB < 50 (Housing confirmed), ISM New Orders < 50 (Orders turning).

TUNABLE: Typical lags are empirical estimates; vary with size of the rate move. The agent uses the indicator readings to classify stage, not calendar time.

### `config/universe.yaml` — Ticker Universe

127 tickers across all 11 GICS sectors. **Demo mode** uses 8 deep-dive tickers: XOM, CVX, FCX, JPM, ABBV, MPC, MSFT, KO.

TUNABLE: Add/remove tickers freely. The `demo_deep_dive_tickers` list controls which tickers get full fundamental + DCF treatment in demo mode.

### `config/holdings.yaml` — Current Portfolio

**Placeholder positions:** MSFT (growth), KO (defensive). Replace with real positions before a live run.

Replacement rules:
- New Buy replaces the weakest holding in the same group (growth or defensive)
- Only replace if new idea's confidence exceeds holding's by ≥10 points
- Never replace more than one holding per run without override

### DCF Model Assumptions (in `a08_valuation.py`)

**TUNABLE:** These are coded defaults, not config-driven. Change in the agent file if needed.

| Assumption | Default | Rationale |
|------------|---------|-----------|
| Terminal growth by life cycle | Startup 3%, Growth 2.5%, Mature 2%, Decline 1% | Per course: vary g by life-cycle stage, not flat for all companies |
| Terminal g warning bound | min(nominal GDP growth, 10yr yield) | If g exceeds this, warning fires and −8 pts penalty applied |
| DCF/multiples blend | 60% DCF / 40% multiples | Gives more weight to DCF; adjust if fundamentals are uncertain |
| Tax rate | 21% | US statutory; change for non-US companies |
| Equity risk premium | 5.5% | Damodaran long-run estimate; TUNABLE |
| WACC: sector premium over risk-free | Energy 3.5%, Materials 4.0%, Tech 3.0%, Utilities 2.0%, etc. | Rough defaults; replace with computed WACC for live runs |
| Bear case multiple compression | 0.80× | Sector P/E compresses 20% in bear scenario (per course requirement) |
| Bull case multiple expansion | 1.15× | 15% expansion in reflation/bull |
| Forecast horizon | 5 years (simplified) | Full course: 5–10 years across a full cycle |
| Sales-to-capital ratio | revenue / (market_cap + debt - cash) | Proxy; replace with balance-sheet data in live mode |

### Composite Macro Indicator (CMI) — `a01_economy.py`

**TUNABLE:** Group weights are coded in the agent, not config-driven.

| Group | Weight | Key inputs |
|-------|--------|-----------|
| Growth | 30% | PMI/ISM New Orders, CB LEI YoY |
| Liquidity | 25% | BAA spread, 10yr yield |
| Inflation | 25% | ISM Prices Paid (inverted) |
| Sentiment | 20% | Michigan Sentiment, VIX (inverted) |

CMI > 50 = expansionary; CMI < 50 = contractionary. Direction (rising/falling) matters more than level.

### Intermarket / Rates ↔ P/E Regime Dependency

The ValuationAgent pulls the regime from EconomyAgent to set multiple assumptions:
- **High-rate regime** (10yr > 4%): P/E falls when rates rise → bear case multiple compression is larger
- **Low-rate regime** (10yr < 2.5%): P/E can fall when rates fall (growth scare) → different direction

This is seeded in `config/economic_view.yaml` (`market.ten_year_yield_pct`) and used automatically.

---

## Architecture Notes

- **Shared Context**: A Pydantic v2 `Context` dataclass passes down the chain. Each agent reads upstream outputs from `context.economy`, `context.cycle`, etc.
- **AgentOutput**: Every agent writes a typed `AgentOutput` with `confidence`, `rationale`, `provenance`, and structured `data`. All outputs persist to `output/agents/<name>.json`.
- **Demo mode**: All agents have a `_run_demo()` path that uses `apm/data/demo_cache/*.json` — no API keys needed.
- **Single-agent runs**: `python -m apm run --demo --agent sector` runs only SectorAgent against cached upstream outputs.
- **Orchestrator**: `--from <name>` resumes the pipeline from any agent; it pre-loads cached outputs for all agents before the start point.

---

## Frontend Notes

- **Stack**: React 19, Vite 6, Tailwind CSS v4 (CSS-first config — no `tailwind.config.js`), Motion v12, Recharts 2, D3 v7, TanStack Query v5, Zustand v5, pnpm
- **Tailwind v4**: Theme is defined in `src/styles.css` using `@theme {}` block. Custom colors: `navy-*`, `cyan-accent`, `amber-accent`, `green-signal`, `red-signal`
- **Fonts**: Space Grotesk (headers) + JetBrains Mono (data numerals) — loaded from Google Fonts
- **Investment Clock**: Pure SVG + D3 arcs + Motion-animated needle overlay
- **API proxy**: Vite dev server proxies `/api/*` to FastAPI at `:8000`

---

## Running Tests

```bash
uv run pytest tests/ -v
```

Tests cover: scenario probability sum, base-case validation, no-downside warning, terminal-g warning, sector ranking respects cyclicality, high-correlation regime guidance, full pipeline on demo data, API smoke tests.

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FRED_API_KEY` | No (demo mode works without it) | FRED macro data; get free at fred.stlouisfed.org |

---

## File Tree

```
Project APM/
├── apm/                         # Python package
│   ├── core/
│   │   ├── agent.py             # Agent ABC, AgentOutput, Context (Pydantic v2)
│   │   ├── orchestrator.py      # Pipeline runner
│   │   └── types.py             # Enums: ClockPhase, HopeStage, Action, etc.
│   ├── agents/
│   │   ├── a01_economy.py … a11_report.py
│   ├── data/
│   │   ├── fetchers.py          # yfinance + FRED + demo cache
│   │   └── demo_cache/          # macro.json, prices.json, fundamentals.json
│   └── utils/
│       ├── config.py            # YAML loader (cached)
│       └── logging.py           # Structured logging
├── api/
│   └── main.py                  # FastAPI: /api/agents, /api/recommendations, /api/funnel
├── config/                      # All editable config (12 YAML files)
├── frontend/                    # React + Vite + Tailwind v4
│   └── src/
│       ├── components/          # TopDownFunnel, InvestmentClock, HopeStrip, SectorHeatmap, ...
│       ├── lib/api.ts + types.ts
│       └── App.tsx
├── output/
│   └── agents/                  # Agent output artifacts (*.json)
├── tests/                       # pytest suite
└── pyproject.toml               # uv-managed dependencies
```

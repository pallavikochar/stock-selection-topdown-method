# Backtest Methodology

## Why the universe changed (Pass 5)

The original backtest held 2 single-stock names per sector (e.g., XOM + CVX for Energy). Those results reflected both the regime signal *and* the idiosyncratic risk of holding concentrated positions. The 2022 standout year (+59.9% strategy vs −18.2% SPY) was driven partly by MPC's 55% return — a single-stock winner, not sector ETF breadth.

The revised backtest replaces those stocks with 11 SPDR Sector Select ETFs. This isolates the quality of the top-down cycle-to-sector signal from single-stock selection noise.

---

## Universe

| Component | Detail |
|---|---|
| Benchmark | SPY (S&P 500 Total Return, `auto_adjust=True`) |
| Sector ETFs | XLE, XLB, XLI, XLF, XLY, XLP, XLV, XLK, XLC, XLU, XLRE |
| Backfill | IYR substituted for XLRE from 2014-01 to 2015-09 (XLRE inception 2015-10-07) |
| XLC handling | Communication Services (XLC, inception 2018-06-18) excluded pre-June 2018; remaining 3 favored ETFs reweighted pro-rata |
| Data source | yfinance `auto_adjust=True`, monthly frequency |
| Fixture | `apm/data/demo_cache/backtest_prices_etf.csv` (152 rows, 13 columns) |

Legacy single-stock fixture (`backtest_prices.csv`) retained for A/B comparison.

---

## Regime-to-ETF mapping

Defined in `apm/core/phase_sector_map.py` — **single source of truth** shared with SectorAgent (a04).

| Regime | Favored ETFs | Investment Clock rationale |
|---|---|---|
| REFLATION | XLF, XLY, XLK, XLI | Growth recovering, inflation low → early cyclicals |
| INFLATION | XLE, XLB, XLI, XLF | Growth strong, inflation rising → late cyclicals + real assets |
| STAGFLATION | XLE, XLP, XLV, XLU | Growth slowing, inflation high → defensives + energy |
| DEFLATION | XLP, XLV, XLU, XLK | Growth falling, inflation low → pure defensives + quality growth |

Equal-weight across the 4 favored ETFs. Monthly rebalance.

---

## Transaction costs

- Round-trip cost: **10 bps** per rebalance (liquid sector ETFs, tight bid-ask)
- Turnover per month: Σ|w\_new\_i − w\_old\_i| / 2 (one-way)
- Cost charged: turnover × 10 / 10,000 deducted from that month's return
- Both gross and net metrics reported side-by-side

---

## Risk-free rate

Piecewise historical approximation (avoids applying current rates to the full period):
- **2014–2021**: ~1.5% annualized (ZIRP era)
- **2022–2024**: ~4.5% annualized (rate-hike cycle)

---

## Results comparison

| Metric | Old stocks (gross) | ETF gross | ETF net (10 bps) |
|---|---|---|---|
| CAGR | 16.8% | 17.2% | 17.1% |
| Alpha vs SPY | +3.2% | +3.3% | +3.2% |
| Beta | 1.13 | 0.95 | — |
| Sharpe | 0.70 | 0.96 | 0.96 |
| Sortino | 1.10 | 1.64 | — |
| Max Drawdown | −48.5% | −24.0% | — |
| Win Rate | 49.6% | 49.7% | — |
| Months | 125 | 151 | — |
| Avg Turnover | 3.4%/mo | 4.0%/mo | — |

---

## Per-regime attribution (ETF universe)

| Regime | Months | Strategy CAGR | Benchmark CAGR | Excess |
|---|---|---|---|---|
| REFLATION | 82 | 27.6% | 25.6% | +2.0% |
| INFLATION | 30 | 5.6% | 9.4% | −3.8% |
| STAGFLATION | 27 | 3.0% | −6.2% | +9.2% |
| DEFLATION | 12 | 13.4% | 4.0% | +9.5% |

Alpha is concentrated in STAGFLATION (+9.2% excess) and DEFLATION (+9.5%) periods. INFLATION underperforms (−3.8%) because Tech outperformed Energy/Materials during 2017–2018 despite rising rates — a regime misclassification risk acknowledged as a limitation.

---

## Key improvements vs. single-stock universe

1. **Sharpe**: 0.70 → 0.96 — diversification removes single-stock vol without sacrificing return
2. **Max Drawdown**: −48.5% → −24.0% — no single stock can blow up the portfolio
3. **Beta**: 1.13 → 0.95 — closer to market-neutral sector tilt
4. **Months covered**: 125 → 151 — full 2014–2026 history now included

---

## Limitations (unchanged from prior passes)

- Regime classification uses **hindsight labels** — real-time regime detection lags 1–3 months
- Fixed universe — no entry/exit of ETFs, no sector reclassifications modeled
- INFLATION regime misfire (2017–2018): sector map correctly weights Energy/Materials, but macro regime label may be imprecise for that period
- Future periods (2026–2029) use placeholder REFLATION labels pending updated cycle output from a02

---

## Files changed

| File | Change |
|---|---|
| `apm/core/phase_sector_map.py` | New — shared phase→ETF map |
| `apm/agents/a15_backtest.py` | Rewritten — ETF universe, costs, gross+net, regime attribution |
| `apm/core/agent.py` | Added `RegimeAttribution`, `net_*` fields, `universe` field to `BacktestData` |
| `apm/data/demo_cache/backtest_prices_etf.csv` | New fixture — 152 months, 13 tickers |
| `tests/test_pipeline.py` | 3 new tests including `test_backtest_etf_universe_matches_sector_agent_map` |

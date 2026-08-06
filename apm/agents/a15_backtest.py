"""
Agent 15 — BacktestAgent
10-year sector-rotation backtest implementing the Investment Clock methodology.

Strategy: At each monthly rebalance, rotate into stocks from the regime-favored
sectors within the demo universe. Tracks returns vs SPY benchmark.

Demo mode: loads a pre-committed CSV fixture (apm/data/demo_cache/backtest_prices.csv)
of monthly adjusted-close prices and computes all metrics at runtime — numbers
are real, deterministic, and offline-capable.

Live mode: downloads fresh monthly prices via yfinance and recomputes.

Metrics: CAGR, Alpha (Jensen's vs SPY), Beta, Sharpe, Sortino, Max Drawdown,
Calmar, Win Rate (months outperforming SPY), annual return table.

Risk-free rate: piecewise historical approximation (~1.5% ann. 2014-2021,
~4.5% ann. 2022-2024); avoids the bias of applying current rates to the
full historical period.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from apm.core.agent import Agent, AgentOutput, AnnualReturn, BacktestData, BacktestMetrics, Context

log = logging.getLogger(__name__)

# ── Regime classification ─────────────────────────────────────────────────────

_REGIME_PERIODS: list[tuple[str, str, str]] = [
    ("201401", "201506", "REFLATION"),    # post-GFC recovery, low inflation
    ("201507", "201606", "DEFLATION"),    # China slowdown, commodities crash
    ("201607", "201812", "INFLATION"),    # Trump expansion, rising rates
    ("201901", "201912", "STAGFLATION"),  # trade war, PMI contracting
    ("202001", "202003", "STAGFLATION"),  # COVID demand shock
    ("202004", "202112", "REFLATION"),    # massive stimulus, reopening
    ("202201", "202212", "STAGFLATION"),  # 40yr-high inflation + rate hikes
    ("202301", "202406", "REFLATION"),    # soft landing, AI boom
    # Extended through current date using pipeline cycle classification (demo: STAGFLATION)
    # Real-world classification: Fed cutting cycle + AI investment boom = REFLATION
    ("202407", "202612", "REFLATION"),    # Fed easing, AI capex, soft landing continues
    ("202701", "202912", "REFLATION"),    # placeholder; update from a02 cycle output
]

# Sector rotation portfolios per regime (from the 9-ticker demo universe)
_REGIME_PORTFOLIO: dict[str, list[str]] = {
    "REFLATION":   ["MSFT", "FCX", "JPM", "KO"],
    "INFLATION":   ["XOM", "CVX", "JPM", "FCX"],
    "STAGFLATION": ["XOM", "CVX", "MPC", "KO"],
    "DEFLATION":   ["KO", "ABBV", "MSFT", "JPM"],
}

# Piecewise risk-free rate (annualized, approximate Fed Funds / T-bill)
# Split 2021/2022 to capture the rate-hike regime shift
def _rf_for_month(ym: str) -> float:
    """Approximate annualized risk-free rate for a given YYYYMM period."""
    if ym >= "202201":
        return 0.045   # ~4.5% during 2022-2024 rate-hike + hold cycle
    return 0.015       # ~1.5% average during 2014-2021 ZIRP era

# ── Fixture path ──────────────────────────────────────────────────────────────

_FIXTURE = Path(__file__).parent.parent / "data/demo_cache/backtest_prices.csv"


class BacktestAgent(Agent):
    name = "backtest"

    def run(self, context: Context) -> AgentOutput:
        if context.demo_mode:
            data = self._run_demo()
        else:
            try:
                data = self._run_live()
            except Exception as exc:
                log.warning("Live backtest failed (%s) — falling back to demo fixture", exc)
                data = self._run_demo()

        context.backtest = data
        m = data.metrics
        rationale = (
            f"10yr backtest ({m.backtest_start[:4]}–{m.backtest_end[:4]}) | "
            f"Strategy CAGR {m.cagr_pct:.1f}% vs SPY {m.benchmark_cagr_pct:.1f}% | "
            f"Alpha {m.alpha_pct:+.1f}% | Sharpe {m.sharpe_ratio:.2f} | "
            f"Max Drawdown {m.max_drawdown_pct:.1f}% | Win Rate {m.win_rate_pct:.0f}% | "
            f"source={data.data_source}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=80.0,
            confidence_label=self._confidence_label(80.0),
            rationale=rationale,
            data=data.model_dump(),
            warnings=[
                "Universe: 8 large-cap tickers (XOM, CVX, FCX, JPM, ABBV, MPC, MSFT, KO) — "
                "survivorship-bias-present fixed universe; does not model delistings or bankruptcies",
                "Regime classification uses hindsight labels — real-time lag of 1–3 months not modeled",
                "Zero transaction costs and slippage modeled",
            ],
            provenance={
                "benchmark": "SPY (S&P 500 ETF, total return, auto-adjusted)",
                "strategy": "Investment Clock sector rotation — monthly equal-weight rebalance",
                "universe": "8 large-cap tickers, fixed (not survivorship-bias-free)",
                "regime_source": "Merrill Lynch Investment Clock (historical phase classification)",
                "risk_free_rate": "piecewise: ~1.5% ann. 2014-2021, ~4.5% ann. 2022-2024",
                "data_source": data.data_source,
                "computed": str(data.computed),
            },
        )

    # ── Demo path (fixture) ───────────────────────────────────────────────────

    def _run_demo(self) -> BacktestData:
        if not _FIXTURE.exists():
            raise RuntimeError(
                f"Backtest fixture not found at {_FIXTURE}. "
                "Run: python -m apm.scripts.fetch_backtest_fixture"
            )
        prices = pd.read_csv(_FIXTURE, index_col="date")
        # Ensure Ticker is the column level name
        prices.columns.name = "Ticker"
        log.info("Backtest: loaded fixture %d months from %s", len(prices), _FIXTURE.name)
        return self._compute_from_prices(
            prices,
            data_source=f"fixture:{_FIXTURE.name} ({len(prices)} months, auto_adjust=True)",
        )

    # ── Live path ─────────────────────────────────────────────────────────────

    def _run_live(self) -> BacktestData:
        import yfinance as yf
        tickers = ["SPY", "XOM", "CVX", "FCX", "JPM", "ABBV", "MPC", "MSFT", "KO"]
        log.info("Downloading 10yr monthly prices for live backtest…")
        raw = yf.download(tickers, period="10y", interval="1mo", auto_adjust=True, progress=False)
        prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        prices = prices.dropna(subset=["SPY"])
        return self._compute_from_prices(
            prices,
            data_source=f"yfinance live ({len(prices)} months, auto_adjust=True)",
        )

    # ── Shared computation ────────────────────────────────────────────────────

    def _compute_from_prices(self, prices: pd.DataFrame, data_source: str) -> BacktestData:
        # Normalise index to DatetimeIndex regardless of CSV vs yfinance source
        if not isinstance(prices.index, pd.DatetimeIndex):
            prices.index = pd.to_datetime(prices.index)

        returns = prices.pct_change().dropna()
        spy_ret = returns["SPY"]

        strategy_monthly: list[float] = []
        dates: list[Any] = []

        for date_idx in returns.index:
            ym = f"{date_idx.year:04d}{date_idx.month:02d}"
            ts = date_idx

            regime = self._regime_for(ym)
            portfolio = _REGIME_PORTFOLIO.get(regime, ["SPY"])
            valid = [t for t in portfolio if t in returns.columns and not pd.isna(returns.at[date_idx, t])]
            port_ret = float(returns.loc[date_idx, valid].mean()) if valid else float(spy_ret.at[date_idx])
            strategy_monthly.append(port_ret)
            dates.append(ts)

        strat = pd.Series(strategy_monthly, index=returns.index)
        bench = spy_ret

        n = len(strat)

        # Piecewise monthly risk-free rate series
        rf_series = pd.Series(
            [_rf_for_month(
                i.replace("-", "")[:6] if isinstance(i, str) else f"{i.year:04d}{i.month:02d}"
            ) / 12 for i in strat.index],
            index=strat.index,
        )
        rf_m = rf_series.mean()  # for Sharpe / Sortino (time-average)

        # CAGR
        cagr = float((1 + strat).prod() ** (12 / n) - 1) * 100
        bench_cagr = float((1 + bench).prod() ** (12 / n) - 1) * 100

        # Alpha + Beta (Jensen's alpha)
        cov_mat = np.cov(strat.values, bench.values)
        beta = float(cov_mat[0, 1] / cov_mat[1, 1]) if cov_mat[1, 1] != 0 else 1.0
        alpha = float((strat.mean() - rf_m - beta * (bench.mean() - rf_m)) * 12) * 100

        # Sharpe & Sortino (using time-average rf as representative scalar)
        excess_rf = strat - rf_m
        sharpe = float(excess_rf.mean() / strat.std() * np.sqrt(12)) if strat.std() > 0 else 0.0
        downside = strat[strat < rf_m]
        sortino = float(excess_rf.mean() / downside.std() * np.sqrt(12)) if len(downside) > 1 else 0.0

        # Max drawdown
        cum = (1 + strat).cumprod()
        roll_max = cum.cummax()
        dd = (cum - roll_max) / roll_max
        max_dd = float(dd.min()) * 100
        calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0.0

        # Win rate
        outperf = int((strat > bench).sum())
        win_rate = float(outperf / n) * 100

        # Annual returns (index is always DatetimeIndex at this point)
        annual_strat = strat.resample("YE").apply(lambda x: float((1 + x).prod() - 1) * 100)
        annual_bench = bench.resample("YE").apply(lambda x: float((1 + x).prod() - 1) * 100)

        annual = []
        for d, s, b in zip(annual_strat.index, annual_strat.values, annual_bench.values):
            ym_yr = f"{d.year:04d}01"
            annual.append(AnnualReturn(
                year=d.year,
                strategy_pct=round(float(s), 1),
                benchmark_pct=round(float(b), 1),
                excess_pct=round(float(s - b), 1),
                regime=self._regime_for(ym_yr),
            ))

        # Top/worst contributors: (ticker, year) pairs ranked by contribution
        contributors = self._rank_contributors(returns, strat)

        start_str = str(returns.index[0].date())
        end_str = str(returns.index[-1].date())

        metrics = BacktestMetrics(
            cagr_pct=round(cagr, 1),
            benchmark_cagr_pct=round(bench_cagr, 1),
            alpha_pct=round(alpha, 1),
            beta=round(beta, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown_pct=round(max_dd, 1),
            calmar_ratio=round(calmar, 2),
            win_rate_pct=round(win_rate, 1),
            backtest_start=start_str,
            backtest_end=end_str,
            total_months=n,
            outperformance_months=outperf,
        )

        return BacktestData(
            strategy_name="Investment Clock Sector Rotation",
            metrics=metrics,
            annual_returns=annual,
            top_contributors=contributors["top"],
            worst_contributors=contributors["worst"],
            methodology=(
                "Monthly equal-weight rotation into regime-favored sectors. "
                "STAGFLATION → Energy/Staples (XOM, CVX, MPC, KO); "
                "INFLATION → Energy/Financials (XOM, CVX, JPM, FCX); "
                "REFLATION → Tech/Materials/Financials (MSFT, FCX, JPM, KO); "
                "DEFLATION → Defensives (KO, ABBV, MSFT, JPM). Benchmark: SPY total return."
            ),
            computed=True,
            data_source=data_source,
        )

    def _rank_contributors(self, returns: pd.DataFrame, strat: pd.Series) -> dict:
        """Identify which ticker-years drove the best and worst excess returns."""
        # returns.index is DatetimeIndex at this point (normalised in _compute_from_prices)
        regime_map: dict[Any, list[str]] = {}
        for idx in returns.index:
            ym = f"{idx.year:04d}{idx.month:02d}"
            regime_map[idx] = _REGIME_PORTFOLIO.get(self._regime_for(ym), [])

        contributions: list[tuple[float, str]] = []
        for date_idx in returns.index:
            tickers_in = regime_map.get(date_idx, [])
            yr = date_idx.year
            for t in tickers_in:
                if t in returns.columns:
                    r = float(returns.at[date_idx, t])
                    if not pd.isna(r):
                        contributions.append((r, f"{t} {yr}"))

        contributions.sort(key=lambda x: x[0])
        worst = [c[1] for c in contributions[:4]]
        top = [c[1] for c in reversed(contributions[-4:])]
        return {"top": top, "worst": worst}

    def _regime_for(self, ym: str) -> str:
        for start, end, regime in _REGIME_PERIODS:
            if start <= ym <= end:
                return regime
        log.warning(
            "_regime_for: %s has no entry in _REGIME_PERIODS — defaulting to REFLATION. "
            "Add an entry covering this period.",
            ym,
        )
        return "REFLATION"

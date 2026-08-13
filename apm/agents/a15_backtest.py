"""
Agent 15 — BacktestAgent
10-year Investment Clock sector-rotation backtest.

Strategy: At each monthly rebalance, equal-weight the 4 SPDR Sector ETFs
favored by the current regime. Phase→ETF mapping lives in
apm/core/phase_sector_map.py — the same table SectorAgent uses for live recs.

Universe (default): 11 SPDR Sector Select ETFs + SPY benchmark.
  Late-inception handling:
    XLC (Communication Services, inception 2018-06): absent months excluded;
         remaining favored ETFs reweighted pro-rata (4→3 names).
    XLRE (Real Estate, inception 2015-10): IYR used as backfill 2014-01 to
         2015-09; backfill documented in data_source provenance string.

Legacy universe: 8 single-stock tickers (XOM, CVX, FCX, JPM, ABBV, MPC,
MSFT, KO) retained for A/B comparison via universe="stocks".

Transaction costs: configurable round-trip cost applied to monthly turnover.
  Default: 10 bps round-trip per rebalance (see _BACKTEST_COSTS).
  Gross and net-of-cost metrics are both reported in BacktestMetrics.

Risk-free rate: piecewise historical (~1.5% ann. 2014-2021, ~4.5% ann.
2022-2024) — avoids the bias of applying current rates to the full period.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from apm.core.agent import (
    Agent, AgentOutput, AnnualReturn, BacktestData, BacktestMetrics,
    Context, RegimeAttribution,
)
from apm.core.phase_sector_map import PHASE_FAVORED_SECTORS, SECTOR_TO_ETF
from apm.core.types import ClockPhase

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_BACKTEST_COSTS = {
    "round_trip_bps": 10,   # 10bps round-trip on sector ETFs (liquid, tight spread)
}

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
    ("202407", "202612", "REFLATION"),    # Fed easing, AI capex, soft landing
    ("202701", "202912", "REFLATION"),    # placeholder; update from a02 cycle output
]

# ── Legacy single-stock universe (retained for A/B comparison) ────────────────

_LEGACY_PORTFOLIO: dict[str, list[str]] = {
    "REFLATION":   ["MSFT", "FCX", "JPM", "KO"],
    "INFLATION":   ["XOM", "CVX", "JPM", "FCX"],
    "STAGFLATION": ["XOM", "CVX", "MPC", "KO"],
    "DEFLATION":   ["KO", "ABBV", "MSFT", "JPM"],
}

# ── ETF universe helpers ──────────────────────────────────────────────────────

# XLC not available before 2018-06; XLRE not available before 2015-10 (use IYR)
_XLC_INCEPTION  = "201806"
_XLRE_INCEPTION = "201510"

def _etfs_for_month(regime_str: str, ym: str) -> list[str]:
    """
    Return the ETF tickers for a given regime and month.
    Handles late-inception ETFs: XLC dropped pre-2018-06 (pro-rata reweight);
    IYR substituted for XLRE pre-2015-10.
    """
    phase = ClockPhase[regime_str]
    etfs = [SECTOR_TO_ETF[s] for s in PHASE_FAVORED_SECTORS[phase]]

    result: list[str] = []
    for etf in etfs:
        if etf == "XLC" and ym < _XLC_INCEPTION:
            continue                        # drop; remaining 3 reweighted pro-rata
        if etf == "XLRE" and ym < _XLRE_INCEPTION:
            result.append("IYR")            # IYR as backfill
        else:
            result.append(etf)
    return result

# ── Piecewise risk-free rate ──────────────────────────────────────────────────

def _rf_for_month(ym: str) -> float:
    """Approximate annualized risk-free rate for a given YYYYMM period."""
    if ym >= "202201":
        return 0.045   # ~4.5% during 2022-2024 rate-hike + hold cycle
    return 0.015       # ~1.5% average during 2014-2021 ZIRP era

# ── Fixture paths ─────────────────────────────────────────────────────────────

_FIXTURE_ETF    = Path(__file__).parent.parent / "data/demo_cache/backtest_prices_etf.csv"
_FIXTURE_STOCKS = Path(__file__).parent.parent / "data/demo_cache/backtest_prices.csv"


class BacktestAgent(Agent):
    name = "backtest"

    def run(self, context: Context) -> AgentOutput:
        universe = getattr(context, "backtest_universe", "etfs")

        if context.demo_mode:
            data = self._run_demo(universe)
        else:
            try:
                data = self._run_live(universe)
            except Exception as exc:
                log.warning("Live backtest failed (%s) — falling back to demo fixture", exc)
                data = self._run_demo(universe)

        context.backtest = data
        m = data.metrics
        rationale = (
            f"10yr backtest ({m.backtest_start[:4]}–{m.backtest_end[:4]}) | "
            f"Universe: {data.universe} | "
            f"Gross CAGR {m.cagr_pct:.1f}% vs SPY {m.benchmark_cagr_pct:.1f}% | "
            f"Net CAGR {m.net_cagr_pct:.1f}% (after {m.cost_bps:.0f}bps cost) | "
            f"Alpha {m.alpha_pct:+.1f}% | Sharpe {m.sharpe_ratio:.2f} | "
            f"Max DD {m.max_drawdown_pct:.1f}% | Win Rate {m.win_rate_pct:.0f}% | "
            f"source={data.data_source}"
        )

        warnings = [
            "Regime classification uses hindsight labels — real-time lag of 1–3 months not modeled",
            f"Transaction costs: {m.cost_bps:.0f}bps round-trip applied; avg turnover {m.avg_turnover_pct:.1f}%/month",
        ]
        if data.universe == "etfs":
            warnings += [
                "XLC (Communication Services) excluded pre-June 2018; remaining 3 favored ETFs equal-weighted",
                "XLRE pre-Oct 2015 replaced by IYR (iShares Real Estate ETF) as backfill",
            ]
        else:
            warnings += [
                "Universe: 8 large-cap tickers — survivorship-bias-present fixed universe",
            ]

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=80.0,
            confidence_label=self._confidence_label(80.0),
            rationale=rationale,
            data=data.model_dump(),
            warnings=warnings,
            provenance={
                "benchmark": "SPY (S&P 500 ETF, total return, auto-adjusted)",
                "strategy": "Investment Clock sector rotation — monthly equal-weight rebalance",
                "universe": data.universe,
                "phase_map": "apm/core/phase_sector_map.py (shared with SectorAgent a04)",
                "regime_source": "Merrill Lynch Investment Clock (historical phase classification)",
                "risk_free_rate": "piecewise: ~1.5% ann. 2014-2021, ~4.5% ann. 2022-2024",
                "transaction_costs": f"{m.cost_bps:.0f}bps round-trip on turnover",
                "data_source": data.data_source,
                "computed": str(data.computed),
            },
        )

    # ── Demo paths ────────────────────────────────────────────────────────────

    def _run_demo(self, universe: str = "etfs") -> BacktestData:
        fixture = _FIXTURE_ETF if universe == "etfs" else _FIXTURE_STOCKS
        if not fixture.exists():
            raise RuntimeError(f"Backtest fixture not found at {fixture}")
        prices = pd.read_csv(fixture, index_col="date")
        prices.columns.name = "Ticker"
        log.info("Backtest: loaded %s fixture %d months from %s", universe, len(prices), fixture.name)
        return self._compute_from_prices(prices, universe=universe,
                                         data_source=f"fixture:{fixture.name} ({len(prices)} months, auto_adjust=True)")

    # ── Live paths ────────────────────────────────────────────────────────────

    def _run_live(self, universe: str = "etfs") -> BacktestData:
        import yfinance as yf
        if universe == "etfs":
            tickers = ["SPY", "XLE", "XLB", "XLI", "XLF", "XLY", "XLP", "XLV",
                       "XLK", "XLC", "XLU", "XLRE", "IYR"]
        else:
            tickers = ["SPY", "XOM", "CVX", "FCX", "JPM", "ABBV", "MPC", "MSFT", "KO"]
        raw = yf.download(tickers, start="2014-01-01", interval="1mo",
                          auto_adjust=True, progress=False)
        prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        prices = prices.dropna(subset=["SPY"])
        return self._compute_from_prices(
            prices, universe=universe,
            data_source=f"yfinance live ({len(prices)} months, auto_adjust=True)",
        )

    # ── Shared computation ────────────────────────────────────────────────────

    def _compute_from_prices(
        self, prices: pd.DataFrame, universe: str, data_source: str
    ) -> BacktestData:
        if not isinstance(prices.index, pd.DatetimeIndex):
            prices.index = pd.to_datetime(prices.index)

        # Only require SPY to be present; per-ticker NaNs (XLC pre-2018, XLRE
        # pre-2015) are handled month-by-month in _etfs_for_month.
        returns = prices.pct_change()
        returns = returns[returns["SPY"].notna()]
        spy_ret = returns["SPY"]

        cost_bps = _BACKTEST_COSTS["round_trip_bps"]
        cost_rate = cost_bps / 10_000

        strategy_gross: list[float] = []
        strategy_net:   list[float] = []
        turnovers:      list[float] = []
        prev_weights:   dict[str, float] = {}

        for date_idx in returns.index:
            ym = f"{date_idx.year:04d}{date_idx.month:02d}"
            regime = self._regime_for(ym)

            if universe == "etfs":
                candidates = _etfs_for_month(regime, ym)
            else:
                candidates = _LEGACY_PORTFOLIO.get(regime, ["SPY"])

            valid = [t for t in candidates
                     if t in returns.columns and not pd.isna(returns.at[date_idx, t])]
            n_pos = len(valid)

            if n_pos == 0:
                port_ret = float(spy_ret.at[date_idx])
                new_weights = {"SPY": 1.0}
            else:
                port_ret = float(returns.loc[date_idx, valid].mean())
                new_weights = {t: 1.0 / n_pos for t in valid}

            # Turnover = Σ|w_new - w_old| / 2  (one-way)
            all_tickers = set(prev_weights) | set(new_weights)
            turnover = sum(
                abs(new_weights.get(t, 0.0) - prev_weights.get(t, 0.0))
                for t in all_tickers
            ) / 2.0

            strategy_gross.append(port_ret)
            strategy_net.append(port_ret - turnover * cost_rate)
            turnovers.append(turnover)
            prev_weights = new_weights

        strat  = pd.Series(strategy_gross, index=returns.index)
        net_s  = pd.Series(strategy_net,   index=returns.index)
        bench  = spy_ret
        n      = len(strat)
        avg_to = float(np.mean(turnovers)) * 100  # as percentage

        rf_series = pd.Series(
            [_rf_for_month(f"{i.year:04d}{i.month:02d}") / 12 for i in strat.index],
            index=strat.index,
        )
        rf_m = rf_series.mean()

        def _metrics(s: pd.Series) -> tuple[float, float, float, float, float, float, float, float]:
            """Return (cagr, alpha, beta, sharpe, sortino, max_dd, calmar, win_rate)."""
            cagr_v  = float((1 + s).prod() ** (12 / n) - 1) * 100
            cov_mat = np.cov(s.values, bench.values)
            beta_v  = float(cov_mat[0, 1] / cov_mat[1, 1]) if cov_mat[1, 1] != 0 else 1.0
            bench_m = float(bench.mean())
            alpha_v = float((s.mean() - rf_m - beta_v * (bench_m - rf_m)) * 12) * 100
            excess  = s - rf_m
            sharpe_v = float(excess.mean() / s.std() * np.sqrt(12)) if s.std() > 0 else 0.0
            # Correct Sortino: downside deviation over ALL months
            down_dev_sq = np.mean(np.minimum(s.values - rf_m, 0.0) ** 2)
            down_dev = float(np.sqrt(down_dev_sq) * np.sqrt(12))
            sortino_v = float(excess.mean() * 12 / down_dev) if down_dev > 0 else 0.0
            cum     = (1 + s).cumprod()
            max_dd_v = float(((cum - cum.cummax()) / cum.cummax()).min()) * 100
            calmar_v = float(cagr_v / abs(max_dd_v)) if max_dd_v != 0 else 0.0
            wr_v    = float((s > bench).sum() / n) * 100
            return cagr_v, alpha_v, beta_v, sharpe_v, sortino_v, max_dd_v, calmar_v, wr_v

        g_cagr, g_alpha, g_beta, g_sharpe, g_sortino, g_max_dd, g_calmar, g_wr = _metrics(strat)
        bench_cagr = float((1 + bench).prod() ** (12 / n) - 1) * 100
        outperf = int((strat > bench).sum())
        n_cagr, n_alpha, _, n_sharpe, *_ = _metrics(net_s)

        # Annual returns
        annual_strat = strat.resample("YE").apply(lambda x: float((1 + x).prod() - 1) * 100)
        annual_bench = bench.resample("YE").apply(lambda x: float((1 + x).prod() - 1) * 100)
        annual = [
            AnnualReturn(
                year=d.year,
                strategy_pct=round(float(s), 1),
                benchmark_pct=round(float(b), 1),
                excess_pct=round(float(s - b), 1),
                regime=self._regime_for(f"{d.year:04d}01"),
            )
            for d, s, b in zip(annual_strat.index, annual_strat.values, annual_bench.values)
        ]

        # Per-regime attribution
        regime_attribution = self._compute_regime_attribution(strat, bench, n)

        # Top/worst contributors
        contributors = self._rank_contributors(returns, strat, universe)

        start_str = str(returns.index[0].date())
        end_str   = str(returns.index[-1].date())

        metrics = BacktestMetrics(
            cagr_pct=round(g_cagr, 1),
            benchmark_cagr_pct=round(bench_cagr, 1),
            alpha_pct=round(g_alpha, 1),
            beta=round(g_beta, 2),
            sharpe_ratio=round(g_sharpe, 2),
            sortino_ratio=round(g_sortino, 2),
            max_drawdown_pct=round(g_max_dd, 1),
            calmar_ratio=round(g_calmar, 2),
            win_rate_pct=round(g_wr, 1),
            backtest_start=start_str,
            backtest_end=end_str,
            total_months=n,
            outperformance_months=outperf,
            net_cagr_pct=round(n_cagr, 1),
            net_alpha_pct=round(n_alpha, 1),
            net_sharpe_ratio=round(n_sharpe, 2),
            avg_turnover_pct=round(avg_to, 1),
            cost_bps=float(cost_bps),
        )

        if universe == "etfs":
            methodology = (
                "Monthly equal-weight rotation into 4 SPDR Sector ETFs per regime "
                "(phase→ETF map: apm/core/phase_sector_map.py). "
                "REFLATION→XLF/XLY/XLK/XLI; INFLATION→XLE/XLB/XLI/XLF; "
                "STAGFLATION→XLE/XLP/XLV/XLU; DEFLATION→XLP/XLV/XLU/XLK. "
                "XLC excluded pre-2018-06 (pro-rata reweight); "
                "IYR substituted for XLRE pre-2015-10. "
                f"Transaction costs: {cost_bps}bps round-trip on monthly turnover."
            )
        else:
            methodology = (
                "Monthly equal-weight rotation into 4 single-stock names per regime "
                "(legacy universe: XOM, CVX, FCX, JPM, ABBV, MPC, MSFT, KO). "
                "Retained for A/B comparison with ETF universe."
            )

        return BacktestData(
            strategy_name="Investment Clock Sector Rotation",
            metrics=metrics,
            annual_returns=annual,
            regime_attribution=regime_attribution,
            top_contributors=contributors["top"],
            worst_contributors=contributors["worst"],
            methodology=methodology,
            universe=universe,
            computed=True,
            data_source=data_source,
        )

    def _compute_regime_attribution(
        self, strat: pd.Series, bench: pd.Series, total_n: int
    ) -> list[RegimeAttribution]:
        """CAGR contribution broken down by regime label."""
        regimes = ["REFLATION", "INFLATION", "STAGFLATION", "DEFLATION"]
        out: list[RegimeAttribution] = []
        for regime in regimes:
            mask = pd.Series([
                self._regime_for(f"{i.year:04d}{i.month:02d}") == regime
                for i in strat.index
            ], index=strat.index)
            s_r = strat[mask]
            b_r = bench[mask]
            m = len(s_r)
            if m == 0:
                continue
            s_cagr = float((1 + s_r).prod() ** (12 / m) - 1) * 100
            b_cagr = float((1 + b_r).prod() ** (12 / m) - 1) * 100
            out.append(RegimeAttribution(
                regime=regime,
                months=m,
                strategy_cagr_pct=round(s_cagr, 1),
                benchmark_cagr_pct=round(b_cagr, 1),
                excess_cagr_pct=round(s_cagr - b_cagr, 1),
            ))
        return out

    def _rank_contributors(
        self, returns: pd.DataFrame, strat: pd.Series, universe: str
    ) -> dict:
        contributions: list[tuple[float, str]] = []
        for date_idx in returns.index:
            ym = f"{date_idx.year:04d}{date_idx.month:02d}"
            regime = self._regime_for(ym)
            if universe == "etfs":
                tickers_in = _etfs_for_month(regime, ym)
            else:
                tickers_in = _LEGACY_PORTFOLIO.get(regime, [])
            for t in tickers_in:
                actual_t = t  # IYR already substituted by _etfs_for_month
                if actual_t in returns.columns:
                    r = float(returns.at[date_idx, actual_t])
                    if not pd.isna(r):
                        contributions.append((r, f"{actual_t} {date_idx.year}"))
        contributions.sort(key=lambda x: x[0])
        return {
            "worst": [c[1] for c in contributions[:4]],
            "top":   [c[1] for c in reversed(contributions[-4:])],
        }

    def _regime_for(self, ym: str) -> str:
        for start, end, regime in _REGIME_PERIODS:
            if start <= ym <= end:
                return regime
        log.warning(
            "_regime_for: %s has no entry in _REGIME_PERIODS — defaulting to REFLATION", ym,
        )
        return "REFLATION"

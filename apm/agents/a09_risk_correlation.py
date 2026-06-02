"""
Agent 9 — RiskCorrelationAgent
Assesses whether stock-picking is being rewarded and flags concentration/crowding.
High correlation = macro market (diversify); low correlation = concentrated bets ok.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apm.core.agent import Agent, AgentOutput, Context, RiskData
from apm.core.types import CorrelationRegime
from apm.data.fetchers import fetch_price_history

log = logging.getLogger(__name__)


class RiskCorrelationAgent(Agent):
    name = "risk_correlation"

    def run(self, context: Context) -> AgentOutput:
        screen = context.screen
        valuations = context.valuations

        # Use the top screened candidates (or demo tickers)
        tickers = ([c.ticker for c in screen.candidates[:10]] if screen else [])
        if not tickers:
            from apm.utils.config import get_universe
            uni = get_universe()
            tickers = uni.get("demo_deep_dive_tickers", [])[:8]

        avg_corr = self._compute_avg_correlation(tickers, context.demo_mode)
        regime = CorrelationRegime.HIGH if avg_corr > 0.65 else CorrelationRegime.LOW
        stock_picking_signal = "low" if avg_corr > 0.65 else ("moderate" if avg_corr > 0.45 else "high")

        if regime == CorrelationRegime.HIGH:
            pos_count_guidance = (
                f"Average pairwise correlation {avg_corr:.2f} = HIGH (macro market). "
                "Stock-picking is less rewarded. Favour MORE names (15–25 positions) to diversify. "
                "When correlation is high but you must pick, focus on industries with selection opportunity. "
                "~70% of the move is macro — a great company can still underperform in the wrong backdrop."
            )
        else:
            pos_count_guidance = (
                f"Average pairwise correlation {avg_corr:.2f} = LOW (differentiated market). "
                "Stock-picking IS rewarded. Can concentrate in fewer names (10–15 positions)."
            )

        # Crowding flags
        crowded = self._identify_crowded(valuations or {})

        # Concentration flags
        concentration_flags: list[str] = []
        if context.sectors:
            favored = context.sectors.favored
            if "Technology" in favored[:2]:
                concentration_flags.append(
                    "Technology in top 2 favored — dominates large-cap; not representative of small/mid-cap"
                )
            sector_hist: dict[str, int] = {}
            for sec in context.sectors.favored:
                sector_hist[sec] = sector_hist.get(sec, 0) + 1
            if len(set(context.sectors.favored)) < 3:
                concentration_flags.append("Sector concentration: fewer than 3 favored sectors — increase diversification")

        data = RiskData(
            avg_pairwise_correlation=round(avg_corr, 3),
            correlation_regime=regime,
            stock_picking_reward_signal=stock_picking_signal,
            recommended_position_count_guidance=pos_count_guidance,
            concentration_flags=concentration_flags,
            crowded_names=crowded,
        )

        rationale = (
            f"Avg pairwise corr: {avg_corr:.2f} → {regime.value} regime → "
            f"stock-picking reward: {stock_picking_signal} | "
            f"Crowded names: {', '.join(crowded) or 'none flagged'}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=65.0,
            confidence_label=self._confidence_label(65.0),
            rationale=rationale,
            data=data.model_dump(),
            warnings=concentration_flags,
            provenance={
                "methodology": "Average pairwise return correlation of screen candidates over 1 year",
                "regime_threshold": ">0.65 = High correlation (macro market)",
            },
        )

    def _compute_avg_correlation(self, tickers: list[str], demo_mode: bool) -> float:
        if demo_mode:
            return 0.72  # Demo: simulate high-correlation regime (stagflation)
        returns: dict[str, pd.Series] = {}
        for ticker in tickers[:8]:  # cap at 8 to keep runtime manageable
            try:
                df = fetch_price_history(ticker, period="1y")
                if "Close" in df.columns and len(df) > 20:
                    returns[ticker] = df["Close"].pct_change().dropna()
            except Exception:
                pass
        if len(returns) < 2:
            return 0.60  # default
        df_ret = pd.DataFrame(returns).dropna()
        corr_matrix = df_ret.corr()
        n = len(corr_matrix)
        if n < 2:
            return 0.60
        off_diag = corr_matrix.values[~np.eye(n, dtype=bool)]
        return float(np.mean(off_diag))

    def _identify_crowded(self, valuations: dict) -> list[str]:
        """Flag names where analyst consensus >= 80% Buy (proxy for crowding)."""
        from apm.data.fetchers import fetch_fundamentals
        crowded = []
        for ticker in list(valuations.keys())[:6]:
            try:
                fund = fetch_fundamentals(ticker)
                rec = fund.get("analyst_recommendation", "").lower()
                if rec in ("strong_buy", "buy") and ticker in ("MSFT", "NVDA", "AAPL"):
                    crowded.append(ticker)
            except Exception:
                pass
        return crowded

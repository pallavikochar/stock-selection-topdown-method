"""
Agent 13 — AnalystAgent
Fetches sell-side analyst consensus: ratings counts, price targets,
and implied upside vs the current price.

Live: yfinance recommendations_summary + info fields.
Demo: pre-seeded data for the 8 demo tickers.
"""

from __future__ import annotations

import logging
from typing import Any

from apm.core.agent import Agent, AgentOutput, AnalystConsensus, Context

log = logging.getLogger(__name__)

_DEMO: dict[str, dict[str, Any]] = {
    "XOM":  {"consensus": "Buy",        "mean_target": 130.5, "high_target": 158.0, "low_target":  96.0, "num_analysts": 29, "buy": 19, "hold": 8, "sell": 2},
    "CVX":  {"consensus": "Buy",        "mean_target": 172.0, "high_target": 208.0, "low_target": 130.0, "num_analysts": 26, "buy": 17, "hold": 7, "sell": 2},
    "FCX":  {"consensus": "Buy",        "mean_target":  52.0, "high_target":  66.0, "low_target":  38.0, "num_analysts": 21, "buy": 14, "hold": 6, "sell": 1},
    "JPM":  {"consensus": "Buy",        "mean_target": 218.0, "high_target": 252.0, "low_target": 178.0, "num_analysts": 28, "buy": 19, "hold": 8, "sell": 1},
    "ABBV": {"consensus": "Buy",        "mean_target": 192.0, "high_target": 228.0, "low_target": 155.0, "num_analysts": 23, "buy": 16, "hold": 6, "sell": 1},
    "MPC":  {"consensus": "Buy",        "mean_target": 218.0, "high_target": 262.0, "low_target": 168.0, "num_analysts": 19, "buy": 14, "hold": 4, "sell": 1},
    "MSFT": {"consensus": "Strong Buy", "mean_target": 480.0, "high_target": 550.0, "low_target": 390.0, "num_analysts": 44, "buy": 36, "hold": 7, "sell": 1},
    "KO":   {"consensus": "Hold",       "mean_target":  66.0, "high_target":  76.0, "low_target":  58.0, "num_analysts": 22, "buy":  9, "hold": 12, "sell": 1},
}


class AnalystAgent(Agent):
    name = "analyst"

    def run(self, context: Context) -> AgentOutput:
        tickers = self._tickers(context)
        results: dict[str, AnalystConsensus] = {}

        if context.demo_mode:
            for t in tickers:
                raw = _DEMO.get(t)
                if raw:
                    results[t] = self._from_raw(t, raw, context)
        else:
            for t in tickers:
                try:
                    results[t] = self._fetch_live(t, context)
                except Exception as exc:
                    log.warning("Analyst fetch failed for %s: %s — using demo data", t, exc)
                    raw = _DEMO.get(t)
                    if raw:
                        results[t] = self._from_raw(t, raw, context)

        context.analyst = results
        buys  = sum(1 for a in results.values() if "buy" in a.consensus.lower())
        holds = sum(1 for a in results.values() if a.consensus.lower() == "hold")
        sells = sum(1 for a in results.values() if "sell" in a.consensus.lower())

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=75.0,
            confidence_label=self._confidence_label(75.0),
            rationale=(
                f"{len(results)} tickers | Analyst consensus — Buy: {buys}, Hold: {holds}, Sell: {sells} | "
                + " | ".join(f"{t}: {a.consensus} (${a.mean_target:.0f} target)" for t, a in list(results.items())[:4])
            ),
            data={k: v.model_dump() for k, v in results.items()},
            warnings=[],
            provenance={"source": "yfinance recommendations_summary + info" if not context.demo_mode else "demo pre-seeded"},
        )

    def _tickers(self, context: Context) -> list[str]:
        if context.recommendations:
            return [r.ticker for r in context.recommendations.ranked]
        if context.fundamentals:
            return list(context.fundamentals.keys())
        return list(_DEMO.keys())

    def _fetch_live(self, ticker: str, context: Context) -> AnalystConsensus:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}

        # Price targets
        mean_t  = info.get("targetMeanPrice")
        high_t  = info.get("targetHighPrice")
        low_t   = info.get("targetLowPrice")
        n_anal  = info.get("numberOfAnalystOpinions", 0) or 0
        rec_key = info.get("recommendationKey", "hold")

        consensus_map = {
            "strong_buy": "Strong Buy", "strongbuy": "Strong Buy",
            "buy": "Buy", "hold": "Hold",
            "sell": "Sell", "strong_sell": "Strong Sell", "underperform": "Sell",
        }
        consensus = consensus_map.get(rec_key.lower().replace(" ", "_"), "Hold")

        # Ratings breakdown from recommendations_summary if available
        buy_c = hold_c = sell_c = 0
        try:
            rs = t.recommendations_summary
            if rs is not None and not rs.empty:
                row = rs.iloc[0]
                buy_c  = int(row.get("strongBuy", 0) or 0) + int(row.get("buy", 0) or 0)
                hold_c = int(row.get("hold", 0) or 0)
                sell_c = int(row.get("sell", 0) or 0) + int(row.get("strongSell", 0) or 0)
        except Exception:
            pass

        current = None
        if context.valuations and ticker in context.valuations:
            current = context.valuations[ticker].current_price

        upside = None
        if mean_t and current and current > 0:
            upside = round((mean_t - current) / current * 100, 1)

        return AnalystConsensus(
            ticker=ticker,
            consensus=consensus,
            mean_target=mean_t,
            high_target=high_t,
            low_target=low_t,
            num_analysts=n_anal,
            buy_count=buy_c,
            hold_count=hold_c,
            sell_count=sell_c,
            upside_to_mean_pct=upside,
        )

    def _from_raw(self, ticker: str, raw: dict, context: Context) -> AnalystConsensus:
        current = None
        if context.valuations and ticker in context.valuations:
            current = context.valuations[ticker].current_price
        mean_t = raw.get("mean_target")
        upside = None
        if mean_t and current and current > 0:
            upside = round((mean_t - current) / current * 100, 1)
        return AnalystConsensus(
            ticker=ticker,
            consensus=raw["consensus"],
            mean_target=mean_t,
            high_target=raw.get("high_target"),
            low_target=raw.get("low_target"),
            num_analysts=raw.get("num_analysts", 0),
            buy_count=raw.get("buy", 0),
            hold_count=raw.get("hold", 0),
            sell_count=raw.get("sell", 0),
            upside_to_mean_pct=upside,
        )

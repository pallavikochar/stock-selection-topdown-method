"""
Agent 6 — ScreenAgent
Greenblatt Magic Formula ranking (EBIT/EV + EBIT/Tangible Assets),
filtered by favored sector + style, with technical-catalyst overlay.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, ScreenCandidate, ScreenData
from apm.data.fetchers import compute_ebit_ev, compute_ebit_tangible_assets, compute_moving_averages, fetch_fundamentals, fetch_price_history
from apm.utils.config import get_holdings, get_universe

log = logging.getLogger(__name__)


class ScreenAgent(Agent):
    name = "screen"

    def run(self, context: Context) -> AgentOutput:
        sectors = context.sectors
        styles = context.styles
        if sectors is None or styles is None:
            raise RuntimeError("ScreenAgent requires Sector + Style agents first")

        universe = get_universe()
        demo_tickers = universe.get("demo_deep_dive_tickers", [])
        holdings_cfg = get_holdings()
        current_holdings = {h["ticker"] for h in holdings_cfg.get("holdings", [])}

        favored_sectors = set(s.replace(" ", "_") for s in sectors.favored)
        favored_box = styles.favored_size_style_box if styles else ""

        # In demo mode use the 8 deep-dive tickers; in live mode use the full universe
        tickers_to_screen = (
            demo_tickers if context.demo_mode
            else [t["ticker"] for s in universe["sectors"].values() for t in s["tickers"]]
        )
        sector_map = {
            t["ticker"]: sector
            for sector, data in universe["sectors"].items()
            for t in data["tickers"]
        }

        raw_scores: list[dict] = []
        for ticker in tickers_to_screen:
            fund = fetch_fundamentals(ticker)
            price_df = fetch_price_history(ticker, period="1y")
            mas = compute_moving_averages(price_df)
            ebit_ev = compute_ebit_ev(fund)
            ebit_ta = compute_ebit_tangible_assets(fund)
            raw_scores.append({
                "ticker": ticker,
                "sector": sector_map.get(ticker, "Unknown"),
                "ebit_ev": ebit_ev,
                "ebit_ta": ebit_ta,
                "ma20": mas.get("ma20"),
                "ma200": mas.get("ma200"),
                "current": mas.get("current") or fund.get("current_price", 0),
                "ev_ebitda": fund.get("ev_ebitda"),
                "pe_fwd": fund.get("pe_fwd"),
                "is_holding": ticker in current_holdings,
            })

        # Rank by EBIT/EV (higher = better) and EBIT/Tangible Assets (higher = better)
        valid = [r for r in raw_scores if r["ebit_ev"] is not None]
        valid.sort(key=lambda x: x["ebit_ev"], reverse=True)
        for i, r in enumerate(valid):
            r["ebit_ev_rank"] = i + 1

        valid2 = [r for r in raw_scores if r["ebit_ta"] is not None]
        valid2.sort(key=lambda x: x["ebit_ta"], reverse=True)
        for i, r in enumerate(valid2):
            r["ebit_ta_rank"] = i + 1

        # Build combined rank
        for r in raw_scores:
            r["combined_rank"] = r.get("ebit_ev_rank", 999) + r.get("ebit_ta_rank", 999)

        raw_scores.sort(key=lambda x: x["combined_rank"])

        # Compute peer median EV/EBITDA for cross-sectional cheapness
        sector_medians: dict[str, float] = {}
        for sector in set(r["sector"] for r in raw_scores):
            vals = [r["ev_ebitda"] for r in raw_scores if r["sector"] == sector and r["ev_ebitda"]]
            if vals:
                sector_medians[sector] = sorted(vals)[len(vals) // 2]

        candidates: list[ScreenCandidate] = []
        for r in raw_scores[:20]:  # top 20 by combined rank
            sector = r["sector"]
            ev_ebitda = r.get("ev_ebitda")
            median = sector_medians.get(sector)
            peer_discount = ((ev_ebitda - median) / median * 100) if ev_ebitda and median else 0.0

            current = r.get("current", 0) or 0
            ma20 = r.get("ma20")
            ma200 = r.get("ma200")
            above_20 = bool(ma20 and current > ma20)
            above_200 = bool(ma200 and current > ma200)
            tech_catalyst = above_20 and above_200

            sector_fit = sector in favored_sectors
            # Style fit: rough proxy — if sector is favored and technicals confirm, style fits
            style_fit = sector_fit and tech_catalyst

            candidates.append(ScreenCandidate(
                ticker=r["ticker"],
                sector=sector,
                magic_formula_rank=r.get("ebit_ev_rank", 999) + r.get("ebit_ta_rank", 999),
                ebit_ev_rank=r.get("ebit_ev_rank", 999),
                ebit_tangible_assets_rank=r.get("ebit_ta_rank", 999),
                combined_rank=r["combined_rank"],
                peer_relative_cheapness_pct=round(peer_discount, 1),
                sector_fit=sector_fit,
                style_fit=style_fit,
                above_20d_ma=above_20,
                above_200d_ma=above_200,
                technical_catalyst=tech_catalyst,
                is_current_holding=r["is_holding"],
                notes=f"EV/EBITDA {ev_ebitda:.1f}x vs peer median {median:.1f}x" if ev_ebitda and median else "",
            ))

        data = ScreenData(
            candidates=candidates,
            universe_size=len(tickers_to_screen),
            filtered_to=len(candidates),
        )

        favored_candidates = [c.ticker for c in candidates if c.sector_fit]
        rationale = (
            f"Screened {len(tickers_to_screen)} tickers | "
            f"Magic Formula top candidates: {', '.join(c.ticker for c in candidates[:5])} | "
            f"In favored sectors: {', '.join(favored_candidates[:5])}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=70.0,
            confidence_label=self._confidence_label(70.0),
            rationale=rationale,
            data=data.model_dump(),
            warnings=[],
            provenance={
                "methodology": "Greenblatt Magic Formula: EBIT/EV + EBIT/Tangible Assets combined rank",
                "valuation_rule": "Cross-sectional vs. current peers (NOT vs. own history)",
            },
        )

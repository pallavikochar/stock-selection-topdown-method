"""
Agent 7 — FundamentalAgent
Qualitative analysis first (it informs the quant, not the other way around).
Porter's Five Forces, industry life cycle, business-model narrative, value drivers.
"""

from __future__ import annotations

import logging
from typing import Any

from apm.core.agent import Agent, AgentOutput, Context, FundamentalData, PorterForces
from apm.core.types import LifeCycleStage
from apm.data.fetchers import fetch_fundamentals
from apm.utils.config import get_universe

log = logging.getLogger(__name__)

# Pre-seeded qualitative profiles for demo tickers
# TUNABLE: Replace with real analysis for each ticker
DEMO_PROFILES: dict[str, dict[str, Any]] = {
    "XOM": {
        "life_cycle": "Mature", "business_model": "Vertically Integrated Oil Major",
        "narrative": "Bully — scale, capital discipline, and integration create durable cost advantages",
        "porter": {
            "threat_of_entry": 1.5, "threat_of_substitutes": 2.5, "buyer_power": 2.0,
            "supplier_power": 2.0, "competitive_rivalry": 3.0,
        },
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Oil price × volume; Permian growth + LNG expansion",
        "margin_driver": "Integration hedges refining margins; cost reduction program $9B savings",
        "reinvestment": "Disciplined — $17B capex, buybacks, progressive dividend; ROIC 14.8%",
        "risks": ["Oil price collapse", "Energy transition speed", "Geopolitical disruption"],
    },
    "CVX": {
        "life_cycle": "Mature", "business_model": "Vertically Integrated Oil Major",
        "narrative": "Bully — strong balance sheet, return-of-capital discipline, Permian optionality",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 2.5, "buyer_power": 2.0,
                   "supplier_power": 2.0, "competitive_rivalry": 3.0},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Oil/gas price + Permian volume growth",
        "margin_driver": "Lower-cost asset base; Permian breakeven ~$50 WTI",
        "reinvestment": "Strong FCF conversion; buyback pace ahead of peers; ROIC 11.8%",
        "risks": ["Oil price", "Hess acquisition integration", "Refining margin volatility"],
    },
    "FCX": {
        "life_cycle": "Mature", "business_model": "Copper-Focused Mining Major",
        "narrative": "Disruptor-adjacent — copper is the key metal for electrification/AI data centers",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 2.0, "buyer_power": 2.5,
                   "supplier_power": 1.5, "competitive_rivalry": 2.5},
        "market_share": "gaining", "margin_outlook": "expanding",
        "revenue_driver": "Copper price × volume; Indonesia ramp (Grasberg); Phoenix Copper leach",
        "margin_driver": "Grasberg underground at full ramp = lowest-quartile cost; byproduct gold/moly credits",
        "reinvestment": "Disciplined; leach ramp is low-cost expansion; ROIC 17.8%",
        "risks": ["Copper price correction", "Indonesia political risk", "Labour disputes"],
    },
    "JPM": {
        "life_cycle": "Mature", "business_model": "Universal Bank / Financial Platform",
        "narrative": "Bully — scale advantages in technology investment and distribution are widening the moat",
        "porter": {"threat_of_entry": 2.0, "threat_of_substitutes": 3.0, "buyer_power": 2.5,
                   "supplier_power": 1.0, "competitive_rivalry": 3.5},
        "market_share": "gaining", "margin_outlook": "compressing",
        "revenue_driver": "NIM × loan growth + fee income (investment banking, asset management)",
        "margin_driver": "NIM near peak; deposit repricing will compress as rates ease",
        "reinvestment": "Heavy technology investment ($17B/yr); buying market share; ROTCE 17%+",
        "risks": ["Credit cycle turn", "NIM compression on rate cuts", "Regulatory capital"],
    },
    "ABBV": {
        "life_cycle": "Growth", "business_model": "Specialty Pharma / Biopharma",
        "narrative": "Better Mousetrap — Humira successor pipeline (Skyrizi, Rinvoq) is exceeding expectations",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 3.0, "buyer_power": 3.0,
                   "supplier_power": 1.5, "competitive_rivalry": 2.5},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Skyrizi + Rinvoq ($25B+ peak sales) offsetting Humira biosimilar erosion",
        "margin_driver": "Royalty cliff behind them; high-margin specialty drugs with pricing power",
        "reinvestment": "R&D + M&A (neuroscience, oncology); FCF yield >10% at current price; ROIC 15.2%",
        "risks": ["Skyrizi/Rinvoq competitive entry", "Pricing pressure (IRA)", "Pipeline failure"],
    },
    "MPC": {
        "life_cycle": "Mature", "business_model": "Independent Refining / Midstream",
        "narrative": "Low-cost — structural advantage in complex refining capacity; midstream through MPLX",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 3.0,
                   "supplier_power": 2.0, "competitive_rivalry": 2.5},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Crack spread × throughput; MPLX fee income",
        "margin_driver": "Nelson Complexity 13.0+ = best-in-class feedstock flexibility; MPLX drops diversify",
        "reinvestment": "Buyback-first capital return; MPLX MLP provides stable fee income; ROIC 22.5%",
        "risks": ["Crack spread compression", "Demand destruction", "Renewable fuel mandates"],
    },
    "MSFT": {
        "life_cycle": "Growth", "business_model": "Enterprise Cloud + AI Platform",
        "narrative": "Disruptor + Bully — Azure + Copilot AI creates switching costs and accelerates TAM expansion",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.0, "buyer_power": 2.5,
                   "supplier_power": 1.5, "competitive_rivalry": 3.5},
        "market_share": "gaining", "margin_outlook": "expanding",
        "revenue_driver": "Azure cloud (>30% growth) + Office 365 seat expansion + AI monetization",
        "margin_driver": "Operating leverage on cloud; Copilot pricing premium; ROIC 29.8%",
        "reinvestment": "Heavy AI capex ($50B+/yr); returns still excellent; buybacks + dividend",
        "risks": ["AI capex cycle risk", "Azure competition (AWS, GCP)", "Regulatory / antitrust"],
    },
    "KO": {
        "life_cycle": "Mature", "business_model": "Global Beverage Brand / Distribution Platform",
        "narrative": "Missionary + Bully — brand moat and 200-country distribution are impossible to replicate",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 3.5, "buyer_power": 3.0,
                   "supplier_power": 2.0, "competitive_rivalry": 3.0},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Pricing power × volume; premium category expansion (energy, water, premium tea)",
        "margin_driver": "Bottler model removes commodity risk; pricing covers commodity costs",
        "reinvestment": "Capital-light; 78% payout ratio; consistent dividend growth; ROIC 11.8%",
        "risks": ["Health/sugar tax regulation", "Currency headwinds", "Pepsi competition"],
    },
}


class FundamentalAgent(Agent):
    name = "fundamental"

    def run(self, context: Context) -> AgentOutput:
        screen = context.screen
        if screen is None:
            raise RuntimeError("FundamentalAgent requires ScreenAgent to run first")

        # Analyse the top screened candidates + current holdings
        universe = get_universe()
        demo_tickers = universe.get("demo_deep_dive_tickers", [])
        tickers = demo_tickers if context.demo_mode else [c.ticker for c in screen.candidates[:8]]

        results: dict[str, FundamentalData] = {}
        for ticker in tickers:
            fund = fetch_fundamentals(ticker)
            profile = DEMO_PROFILES.get(ticker, {})
            results[ticker] = self._analyse(ticker, fund, profile)

        rationale = (
            f"Analysed {len(results)} tickers | "
            + " | ".join(
                f"{t}: {d.industry_life_cycle.value}, Porter={d.porter.overall_score:.1f}/10, Q={d.qualitative_score:.0f}"
                for t, d in list(results.items())[:4]
            )
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=72.0,
            confidence_label=self._confidence_label(72.0),
            rationale=rationale,
            data={k: v.model_dump() for k, v in results.items()},
            warnings=[],
            provenance={"methodology": "Porter's Five Forces + Industry Life Cycle + Business Model Narrative"},
        )

    def _analyse(self, ticker: str, fund: dict, profile: dict) -> FundamentalData:
        p = profile.get("porter", {"threat_of_entry": 3, "threat_of_substitutes": 3,
                                   "buyer_power": 3, "supplier_power": 3, "competitive_rivalry": 3})
        porter_score = 10 - (
            p["threat_of_entry"] + p["threat_of_substitutes"] +
            p["buyer_power"] + p["supplier_power"] + p["competitive_rivalry"]
        ) / 5 * 2  # normalize to 0-10

        porter = PorterForces(
            threat_of_entry=p["threat_of_entry"],
            threat_of_substitutes=p["threat_of_substitutes"],
            buyer_power=p["buyer_power"],
            supplier_power=p["supplier_power"],
            competitive_rivalry=p["competitive_rivalry"],
            market_share_outlook=profile.get("market_share", "stable"),
            margin_outlook=profile.get("margin_outlook", "stable"),
            overall_score=round(max(0, min(10, porter_score)), 1),
        )

        roe = fund.get("roe", 0) or 0
        roic = fund.get("roic", 0) or 0
        revenue_growth = fund.get("revenue_growth_yoy", 0) or 0
        quality_score = (
            min(100, (roe * 200) +                          # ROE contribution
                (roic * 150) +                              # ROIC contribution
                (revenue_growth * 100) +                   # growth contribution
                (porter.overall_score / 10 * 30)          # Porter contribution
            )
        )

        life_cycle_raw = profile.get("life_cycle", "Mature")
        try:
            life_cycle = LifeCycleStage(life_cycle_raw)
        except ValueError:
            life_cycle = LifeCycleStage.MATURE

        return FundamentalData(
            ticker=ticker,
            industry_life_cycle=life_cycle,
            business_model_type=profile.get("business_model", fund.get("industry", "")),
            narrative_quality=profile.get("narrative", "Insufficient data for narrative assessment"),
            porter=porter,
            revenue_growth_driver=profile.get("revenue_driver", ""),
            margin_driver=profile.get("margin_driver", ""),
            reinvestment_efficiency=profile.get("reinvestment", ""),
            key_risks=profile.get("risks", []),
            qualitative_score=round(min(100, max(0, quality_score)), 1),
        )

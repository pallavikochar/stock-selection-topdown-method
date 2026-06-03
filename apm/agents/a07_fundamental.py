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
    "NVDA": {
        "life_cycle": "Growth", "business_model": "AI Accelerated Computing Platform",
        "narrative": "Disruptor — CUDA ecosystem lock-in and data-center AI buildout create a multi-year supercycle",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.0, "buyer_power": 2.0,
                   "supplier_power": 2.0, "competitive_rivalry": 2.0},
        "market_share": "gaining", "margin_outlook": "expanding",
        "revenue_driver": "H100/H200/Blackwell GPU demand; data center >80% of rev; sovereign AI TAM",
        "margin_driver": "Pricing power on AI GPUs; software attach (CUDA, NIM) expanding gross margins",
        "reinvestment": "Heavy R&D + TSMC capacity deposits; ROIC 90%+",
        "risks": ["Hyperscaler capex cycle peak", "AMD/Intel GPU competition", "Export restrictions (China)"],
    },
    "AAPL": {
        "life_cycle": "Mature", "business_model": "Consumer Electronics + Services Platform",
        "narrative": "Bully — ecosystem lock-in and services monetization sustain premium pricing despite hardware maturity",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 2.0,
                   "supplier_power": 2.0, "competitive_rivalry": 3.0},
        "market_share": "stable", "margin_outlook": "expanding",
        "revenue_driver": "iPhone upgrade cycle + Services ($100B+ revenue run-rate growing 15%+)",
        "margin_driver": "Services mix shift (>75% gross margin vs. 35% hardware); Apple Silicon cost reduction",
        "reinvestment": "Capital-light; $110B+ annual buybacks; ROIC 40%+",
        "risks": ["iPhone concentration risk", "App Store regulatory pressure", "China sales exposure"],
    },
    "META": {
        "life_cycle": "Growth", "business_model": "Digital Advertising + Social Platforms",
        "narrative": "Bully — Reels/Threads engagement recovery and AI-driven ad targeting restore growth trajectory",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 3.0, "buyer_power": 3.0,
                   "supplier_power": 1.0, "competitive_rivalry": 3.5},
        "market_share": "stable", "margin_outlook": "expanding",
        "revenue_driver": "Ad price × impression volume; Reels monetization catching Facebook/Instagram",
        "margin_driver": "Year of Efficiency cost cuts; AI-driven ad ROI lifts advertiser spend",
        "reinvestment": "Reality Labs losses ($15B/yr) offset by core FCF; buybacks accelerating; ROIC 28%",
        "risks": ["Regulatory/antitrust breakup risk", "TikTok competition for engagement time", "Reality Labs burn"],
    },
    "LLY": {
        "life_cycle": "Growth", "business_model": "Innovative Biopharma / GLP-1 Platform",
        "narrative": "Disruptor — Mounjaro/Zepbound GLP-1 franchise is redefining obesity and diabetes treatment",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 3.0,
                   "supplier_power": 1.5, "competitive_rivalry": 2.0},
        "market_share": "gaining", "margin_outlook": "expanding",
        "revenue_driver": "Tirzepatide (obesity + diabetes) $50B+ peak sales potential; incretin pipeline depth",
        "margin_driver": "Manufacturing scale-up reducing COGS; pricing power in obesity market",
        "reinvestment": "Massive manufacturing capex ($9B+/yr); pipeline (donanemab, orforglipron); ROIC 22%",
        "risks": ["Novo Nordisk semaglutide competition", "Insurance/PBM coverage decisions", "Manufacturing capacity"],
    },
    "AMZN": {
        "life_cycle": "Growth", "business_model": "E-Commerce + Cloud + Advertising Platform",
        "narrative": "Disruptor + Bully — AWS margin engine funds retail flywheel; advertising is a third high-margin leg",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 2.5,
                   "supplier_power": 1.5, "competitive_rivalry": 3.0},
        "market_share": "gaining", "margin_outlook": "expanding",
        "revenue_driver": "AWS ($100B+ run rate, 17% growth) + advertising ($50B+ growing 20%+)",
        "margin_driver": "AWS and advertising are structurally high-margin; fulfillment cost-per-unit declining",
        "reinvestment": "AWS capex $80B+; AI (Trainium, Bedrock); logistics owned infrastructure; ROIC 17%",
        "risks": ["AWS competition (Azure/GCP)", "FTC antitrust", "Retail margin volatility"],
    },
    "GOOGL": {
        "life_cycle": "Mature", "business_model": "Search Advertising + Cloud + AI Platform",
        "narrative": "Bully — search moat durable despite AI threat; GCP inflecting; Gemini monetization beginning",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 2.5,
                   "supplier_power": 1.5, "competitive_rivalry": 3.0},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Search advertising (89% market share) + YouTube + GCP (28% growth)",
        "margin_driver": "Search remains 60%+ EBIT margin; GCP approaching profitability",
        "reinvestment": "AI capex ($40B+/yr, Tensor chips); Waymo optionality; buybacks $62B/yr; ROIC 24%",
        "risks": ["AI search disruption (ChatGPT/Perplexity)", "DOJ antitrust ruling", "YouTube content competition"],
    },
    "V": {
        "life_cycle": "Mature", "business_model": "Global Payment Network / Digital Infrastructure",
        "narrative": "Bully — two-sided network effect is impossible to replicate; cash-to-card secular shift continues",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 2.5, "buyer_power": 2.0,
                   "supplier_power": 1.0, "competitive_rivalry": 2.5},
        "market_share": "stable", "margin_outlook": "expanding",
        "revenue_driver": "Payment volume growth × take rate; cross-border transaction recovery",
        "margin_driver": "70%+ operating margins; incremental revenue is near-pure profit",
        "reinvestment": "Capital-light; $16B buybacks/yr; Visa Direct new payment flows; ROIC 44%",
        "risks": ["Buy-now-pay-later disintermediation", "Regulatory interchange caps", "Real-time payment alternatives"],
    },
    "UNH": {
        "life_cycle": "Mature", "business_model": "Managed Care + Health Services Platform",
        "narrative": "Bully — Optum vertical integration creates unique data + service advantages across the care continuum",
        "porter": {"threat_of_entry": 2.0, "threat_of_substitutes": 2.5, "buyer_power": 2.5,
                   "supplier_power": 2.0, "competitive_rivalry": 3.0},
        "market_share": "gaining", "margin_outlook": "stable",
        "revenue_driver": "Membership growth × premium rate increases + Optum Health care delivery",
        "margin_driver": "Optum Services (pharmacy + care delivery) cross-sold into insurance members",
        "reinvestment": "Acquisitions (physician groups, surgery centers); ROIC 18%+",
        "risks": ["Medical cost ratio spikes", "Medicare Advantage reimbursement cuts", "Cyber/data breach exposure"],
    },
    "NEE": {
        "life_cycle": "Growth", "business_model": "Regulated Utility + Clean Energy Developer",
        "narrative": "Better Mousetrap — largest renewable energy developer in the US; AI data-center power demand tailwind",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 1.5, "buyer_power": 2.0,
                   "supplier_power": 2.0, "competitive_rivalry": 1.5},
        "market_share": "gaining", "margin_outlook": "stable",
        "revenue_driver": "Regulated FPL rate base growth + NextEra Energy Resources contracted renewables backlog",
        "margin_driver": "Rate case ROE on FPL; long-term PPA contracts lock in margins on renewables",
        "reinvestment": "~$50B 4-year capex plan; wind/solar/storage + transmission; ROIC 9%",
        "risks": ["Rising interest rates (utility valuation compression)", "IRA subsidy uncertainty", "Hurricane damage"],
    },
    "CAT": {
        "life_cycle": "Mature", "business_model": "Capital Goods / Construction & Mining OEM",
        "narrative": "Bully — Services & Parts aftermarket flywheel and pricing power through cycles",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 2.0, "buyer_power": 2.5,
                   "supplier_power": 2.5, "competitive_rivalry": 2.5},
        "market_share": "stable", "margin_outlook": "stable",
        "revenue_driver": "Infrastructure + mining capex cycle; data-center generator demand; emerging-market construction",
        "margin_driver": "Services segment (>60% gross margin) growing 15%+/yr; pricing discipline maintained",
        "reinvestment": "Conservative; buybacks + dividend growth; electrification R&D; ROIC 28%",
        "risks": ["Construction cycle downturn", "China mining slowdown", "Supply chain input costs"],
    },
    "GS": {
        "life_cycle": "Mature", "business_model": "Global Investment Bank / Alternative Assets",
        "narrative": "Bully — IB advisory + trading leverage to deal-making cycle recovery; alternatives AUM growing",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 3.0, "buyer_power": 2.5,
                   "supplier_power": 1.5, "competitive_rivalry": 3.5},
        "market_share": "stable", "margin_outlook": "recovering",
        "revenue_driver": "M&A/IPO cycle revival + FICC trading + Asset & Wealth Management AUM fees",
        "margin_driver": "Consumer business exit removes drag; IB leverage to capital markets reopening",
        "reinvestment": "Capital return focus; alternatives platform scaling; ROTCE 12-14%",
        "risks": ["Deal flow cycle risk", "Trading revenue volatility", "Regulatory capital requirements"],
    },
    "LIN": {
        "life_cycle": "Mature", "business_model": "Industrial Gas / Process Chemistry",
        "narrative": "Bully — long-term on-site contracts and switching costs create recession-resistant cash flows",
        "porter": {"threat_of_entry": 1.0, "threat_of_substitutes": 1.5, "buyer_power": 2.5,
                   "supplier_power": 2.0, "competitive_rivalry": 2.5},
        "market_share": "stable", "margin_outlook": "expanding",
        "revenue_driver": "Volume growth via project backlog + pricing pass-through clauses",
        "margin_driver": "Energy pass-through contracts + mix shift to high-purity electronics gases; EBITDA 40%+",
        "reinvestment": "$3-4B project capex/yr; hydrogen economy investment; buybacks + dividend; ROIC 10%+",
        "risks": ["Industrial production slowdown", "Hydrogen project returns", "Air separation capacity overbuild"],
    },
    "TSLA": {
        "life_cycle": "Growth", "business_model": "EV + Energy + Autonomous Driving Platform",
        "narrative": "Disruptor — FSD/Robotaxi optionality and energy storage create long-duration upside beyond autos",
        "porter": {"threat_of_entry": 2.0, "threat_of_substitutes": 3.0, "buyer_power": 3.0,
                   "supplier_power": 2.5, "competitive_rivalry": 3.5},
        "market_share": "stable", "margin_outlook": "compressed",
        "revenue_driver": "Volume growth (Cybertruck, Model Y refresh, new ~$25K model) + Energy Storage",
        "margin_driver": "Price cuts compressed auto gross margins to 17%; FSD software is high margin",
        "reinvestment": "Gigafactory expansion; Robotaxi network; Optimus robot; ROIC 12%",
        "risks": ["EV demand slowdown + competition (BYD, legacy OEMs)", "FSD regulatory approval", "CEO distraction"],
    },
    "BLK": {
        "life_cycle": "Mature", "business_model": "Asset Management / Aladdin Technology Platform",
        "narrative": "Bully — ETF/passive flows + Aladdin risk platform create fee stability and network effects",
        "porter": {"threat_of_entry": 2.0, "threat_of_substitutes": 3.0, "buyer_power": 3.5,
                   "supplier_power": 1.0, "competitive_rivalry": 3.0},
        "market_share": "gaining", "margin_outlook": "stable",
        "revenue_driver": "AUM growth ($10T+) via net inflows + market appreciation + alternatives expansion",
        "margin_driver": "Passive fee compression offset by alternatives mix shift (higher fee); Aladdin recurring fees",
        "reinvestment": "Acquisitions (GIP, Preqin); technology; ROIC 14%",
        "risks": ["Market downturn (AUM base falls)", "Fee compression in core ETF business", "Passive flow reversal"],
    },
    "PG": {
        "life_cycle": "Mature", "business_model": "Consumer Packaged Goods / Brand Portfolio",
        "narrative": "Bully — portfolio of #1/#2 brands in essential categories with pricing power through inflationary cycles",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 3.0, "buyer_power": 3.5,
                   "supplier_power": 2.0, "competitive_rivalry": 3.5},
        "market_share": "stable", "margin_outlook": "recovering",
        "revenue_driver": "Premium mix shift + volume recovery as pricing cycles fade + emerging market penetration",
        "margin_driver": "Commodity cost tailwind; marketing leverage on scale brands; portfolio pruning complete",
        "reinvestment": "Capital-light; $9B annual buybacks + progressive dividend (67yr streak); ROIC 19%",
        "risks": ["Private label share gains in downturn", "Emerging market FX", "Commodity cost spikes"],
    },
    "HON": {
        "life_cycle": "Mature", "business_model": "Industrial Conglomerate / Software-Defined Automation",
        "narrative": "Bully — software-driven automation and building controls create recurring aftermarket revenue",
        "porter": {"threat_of_entry": 1.5, "threat_of_substitutes": 2.5, "buyer_power": 2.5,
                   "supplier_power": 2.0, "competitive_rivalry": 3.0},
        "market_share": "stable", "margin_outlook": "expanding",
        "revenue_driver": "Aerospace aftermarket + warehouse automation + building efficiency retrofit cycle",
        "margin_driver": "Software & services attach growing; price discipline maintained; EBIT margin >20%",
        "reinvestment": "Portfolio simplification (spin-offs); automation R&D; ROIC 15%+",
        "risks": ["Aerospace build rate cycle", "Spin-off execution risk", "Industrial automation competition"],
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
        tickers = demo_tickers if context.demo_mode else [c.ticker for c in screen.candidates[:25]]

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

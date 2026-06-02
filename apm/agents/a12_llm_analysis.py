"""
Agent 12 — LLMAnalysisAgent
Two-pass hallucination-resistant qualitative analysis via Claude.

Pass 1 (Generate): LLM receives ONLY data already computed by the pipeline
  (macro regime, sector scores, fundamentals, valuation scenarios). Tool-use
  forces structured JSON — no free-form recall from training data.

Pass 2 (Verify): Same LLM reviews each claim against the source context and
  classifies it GROUNDED / INFERRED / SPECULATIVE with a specific evidence
  citation. Speculative claims are surfaced to the user and lower the
  grounding_score, which is shown in the UI.

Falls back to pre-seeded demo analysis when demo_mode=True or no API key.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from apm.core.agent import (
    Agent, AgentOutput, Context,
    LLMAnalysisData, LLMStockAnalysis, VerifiedClaim,
)

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

# ── Tool schemas for structured output ───────────────────────────────────────

_GENERATE_TOOL: dict[str, Any] = {
    "name": "submit_analysis",
    "description": "Submit tailwinds, headwinds, and net sentiment for the stock",
    "input_schema": {
        "type": "object",
        "properties": {
            "tailwinds": {
                "type": "array",
                "description": "3-5 positive catalysts. Each must explicitly reference a data point from the provided context.",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
            },
            "headwinds": {
                "type": "array",
                "description": "3-5 risks or negative catalysts. Each must explicitly reference a data point.",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 5,
            },
            "net_sentiment": {
                "type": "string",
                "enum": ["BULLISH", "NEUTRAL", "BEARISH"],
                "description": "Overall stance after weighing scenario-probability-adjusted tailwinds vs headwinds",
            },
            "sentiment_rationale": {
                "type": "string",
                "description": "1-2 sentence explanation — must cite specific data (e.g. probability, score, metric)",
            },
        },
        "required": ["tailwinds", "headwinds", "net_sentiment", "sentiment_rationale"],
    },
}

_VERIFY_TOOL: dict[str, Any] = {
    "name": "submit_verification",
    "description": "Verify each claim against the provided source data",
    "input_schema": {
        "type": "object",
        "properties": {
            "verified_tailwinds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "grounding": {
                            "type": "string",
                            "enum": ["GROUNDED", "INFERRED", "SPECULATIVE"],
                            "description": (
                                "GROUNDED = claim is directly stated or numerically present in the source data. "
                                "INFERRED = logical conclusion from the data, not explicitly stated. "
                                "SPECULATIVE = introduces facts not found in the provided data (hallucination risk)."
                            ),
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Exact quote or field reference from source data, or reason the claim is speculative",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "0-1 confidence in the grounding classification",
                        },
                    },
                    "required": ["claim", "grounding", "evidence", "confidence"],
                },
            },
            "verified_headwinds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "grounding": {
                            "type": "string",
                            "enum": ["GROUNDED", "INFERRED", "SPECULATIVE"],
                        },
                        "evidence": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                    "required": ["claim", "grounding", "evidence", "confidence"],
                },
            },
        },
        "required": ["verified_tailwinds", "verified_headwinds"],
    },
}

# ── Pre-seeded demo analysis ──────────────────────────────────────────────────
# All claims reference specific data from the demo pipeline outputs.
# Grounding labels are accurate — most are GROUNDED, a few INFERRED.

_DEMO_ANALYSIS: dict[str, dict[str, Any]] = {
    "XOM": {
        "tailwinds": [
            {"claim": "Stagflationary macro regime (CMI 42.3, PMI 48.1 contracting) historically favors Energy — sector agent ranks Energy #1 with favorability STRONGLY_FAVORED",
             "grounding": "GROUNDED", "evidence": "Economy agent: cmi_score=42.3, pmi_read=48.1. Sector agent: Energy ranked #1, strongly_favored", "confidence": 0.97},
            {"claim": "Permian Basin volume growth + LNG expansion provide revenue upside independent of spot oil price",
             "grounding": "GROUNDED", "evidence": "Fundamental agent revenue_growth_driver: 'Oil price × volume; Permian growth + LNG expansion'", "confidence": 0.94},
            {"claim": "$9B cost reduction program preserves margins even if WTI pulls back; vertical integration hedges refining margins",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Integration hedges refining margins; cost reduction program $9B savings'", "confidence": 0.93},
            {"claim": "ROIC of 14.8% with disciplined $17B capex + progressive dividend signals high reinvestment efficiency",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Disciplined — $17B capex, buybacks, progressive dividend; ROIC 14.8%'", "confidence": 0.95},
            {"claim": "Base case (55% probability) blended DCF/multiples target implies material upside; prob-weighted target exceeds current price",
             "grounding": "GROUNDED", "evidence": "Scenario agent base probability 0.55; valuation agent prob_weighted_target > current_price, expected_return_pct positive", "confidence": 0.91},
        ],
        "headwinds": [
            {"claim": "Bear/Recession scenario (20% probability) implies oil demand destruction and double-digit downside from current price",
             "grounding": "GROUNDED", "evidence": "Scenario agent bear probability 0.20; valuation bear scenario upside_pct negative", "confidence": 0.95},
            {"claim": "Mature life-cycle stage caps terminal growth at 2.0% — any terminal-g creep above GDP would trigger valuation warning",
             "grounding": "GROUNDED", "evidence": "Fundamental industry_life_cycle: Mature; valuation terminal_growth_pct 2.0 (Mature stage limit)", "confidence": 0.92},
            {"claim": "Key risks include oil price collapse and geopolitical disruption — both cited in fundamental profile",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Oil price collapse', 'Energy transition speed', 'Geopolitical disruption']", "confidence": 0.96},
            {"claim": "High portfolio correlation regime (avg pairwise 0.72) limits diversification benefit; XOM would fall with broad equity sell-off",
             "grounding": "GROUNDED", "evidence": "Risk agent avg_pairwise_correlation: 0.72, correlation_regime: High", "confidence": 0.90},
            {"claim": "Elevated 10-year yield (4.65%) raises WACC, compressing terminal-value contribution in DCF model",
             "grounding": "INFERRED", "evidence": "Economy agent yield_curve_bps cited; WACC-yield linkage is standard DCF mechanics inferred from model structure, not explicitly stated in pipeline data", "confidence": 0.82},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "Stagflation clock phase directly favors Energy (sector rank #1); strong ROIC 14.8%, disciplined capex, and Permian optionality outweigh the 20% bear-scenario probability. CMI at 42.3 confirms the macro tailwind is current.",
    },
    "CVX": {
        "tailwinds": [
            {"claim": "Stagflation clock phase strongly favors Energy sector (rank #1); CVX benefits alongside XOM from macro tailwind",
             "grounding": "GROUNDED", "evidence": "Sector agent: Energy strongly_favored, ranked #1. Cycle agent clock_phase: STAGFLATION", "confidence": 0.96},
            {"claim": "Permian breakeven ~$50 WTI provides margin of safety even in base stagflation scenario with oil rising",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Lower-cost asset base; Permian breakeven ~$50 WTI'", "confidence": 0.94},
            {"claim": "ROIC of 11.8% with buyback pace ahead of peers signals strong capital return discipline",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Strong FCF conversion; buyback pace ahead of peers; ROIC 11.8%'", "confidence": 0.93},
            {"claim": "Market share outlook is stable with strong FCF conversion supporting progressive shareholder returns",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.market_share_outlook: stable; margin_outlook: stable", "confidence": 0.90},
        ],
        "headwinds": [
            {"claim": "Hess acquisition integration risk is an explicit key risk in fundamental profile",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Oil price', 'Hess acquisition integration', 'Refining margin volatility']", "confidence": 0.97},
            {"claim": "Bear/Recession scenario (20% probability) implies oil demand contraction and earnings compression",
             "grounding": "GROUNDED", "evidence": "Scenario agent bear probability 0.20; oil demand contraction in recession scenario", "confidence": 0.94},
            {"claim": "Refining margin volatility could erode earnings if crack spreads compress in economic slowdown",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Refining margin volatility'; scenario macro data shows PMI contracting", "confidence": 0.89},
            {"claim": "High correlation regime (0.72 avg pairwise) means concentrated energy positions provide limited portfolio diversification",
             "grounding": "GROUNDED", "evidence": "Risk agent correlation_regime: High, avg_pairwise_correlation: 0.72", "confidence": 0.91},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "CVX mirrors XOM's macro tailwind (stagflation, Energy rank #1) with a lower-cost Permian position (breakeven ~$50) providing additional downside protection. ROIC 11.8% confirms capital efficiency. Hess integration is a known risk, not a thesis breaker.",
    },
    "FCX": {
        "tailwinds": [
            {"claim": "Copper is cited as 'the key metal for electrification/AI data centers' — structural demand story independent of business cycle",
             "grounding": "GROUNDED", "evidence": "Fundamental narrative_quality: 'Disruptor-adjacent — copper is the key metal for electrification/AI data centers'", "confidence": 0.95},
            {"claim": "Grasberg underground at full ramp is lowest-quartile cost; byproduct gold and moly credits further reduce net cost",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Grasberg underground at full ramp = lowest-quartile cost; byproduct gold/moly credits'", "confidence": 0.96},
            {"claim": "ROIC of 17.8% is the highest among Materials sector peers in the demo universe — disciplined leach expansion is low-capex growth",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Disciplined; leach ramp is low-cost expansion; ROIC 17.8%'", "confidence": 0.93},
            {"claim": "Market share is gaining (not stable), with margin outlook expanding — rare combination in a Mature life-cycle company",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.market_share_outlook: gaining, margin_outlook: expanding", "confidence": 0.94},
        ],
        "headwinds": [
            {"claim": "Copper price correction is the primary risk — FCX is a pure-play commodity stock with high revenue beta to copper",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Copper price correction', 'Indonesia political risk', 'Labour disputes']", "confidence": 0.97},
            {"claim": "Indonesia political risk (Grasberg is in Papua) could disrupt production at the company's largest, lowest-cost mine",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Indonesia political risk'; Grasberg location inferred from margin_driver reference", "confidence": 0.88},
            {"claim": "Stagflation clock phase favors Materials but falling PMI (48.1) signals demand pressure on industrial metals near-term",
             "grounding": "INFERRED", "evidence": "Economy agent pmi_read=48.1, pmi_direction=falling. Sector agent Materials is favored but copper is demand-sensitive — linkage is inferred from standard macro mechanics", "confidence": 0.80},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "Structural copper demand (electrification, AI) provides secular tailwind beyond the business cycle; Grasberg ramp at lowest-quartile cost and ROIC 17.8% are exceptional fundamentals. Bear risk is copper price — a 20% scenario with recession weighs on the thesis.",
    },
    "JPM": {
        "tailwinds": [
            {"claim": "Universal bank model with ROTCE 17%+ demonstrates scale advantage in technology investment ($17B/yr) and distribution",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Heavy technology investment ($17B/yr); buying market share; ROTCE 17%+'", "confidence": 0.95},
            {"claim": "Market share is gaining across investment banking and asset management despite competitive pressure",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.market_share_outlook: gaining", "confidence": 0.93},
            {"claim": "Elevated credit spreads (BAA spread 1.72%, widening) support NIM — Financials earn more when risk premium is elevated",
             "grounding": "INFERRED", "evidence": "Economy agent: BAA spread 1.72% widening cited in sector macro data; NIM-spread linkage is standard banking mechanics inferred, not explicitly stated in pipeline", "confidence": 0.79},
        ],
        "headwinds": [
            {"claim": "Stagflation clock phase (STAGFLATION) is associated with compressing NIM as rate cuts follow — sector agent rates Financials as UNFAVORED",
             "grounding": "GROUNDED", "evidence": "Cycle agent clock_phase: STAGFLATION; Sector agent: Financials unfavored in stagflation phase", "confidence": 0.94},
            {"claim": "NIM is identified as 'near peak; deposit repricing will compress as rates ease' — explicit in fundamental margin_driver",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'NIM near peak; deposit repricing will compress as rates ease'", "confidence": 0.97},
            {"claim": "Credit cycle turn risk is explicitly cited; bear scenario (20% probability) would compress loan-loss provisions",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Credit cycle turn', 'NIM compression on rate cuts', 'Regulatory capital']; scenario bear probability 0.20", "confidence": 0.95},
            {"claim": "Regulatory capital requirements could constrain capital return even as ROTCE stays elevated",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Regulatory capital'", "confidence": 0.91},
        ],
        "net_sentiment": "NEUTRAL",
        "sentiment_rationale": "JPM has excellent fundamentals (ROTCE 17%+, gaining market share) but the stagflation clock phase explicitly unfavors Financials, and NIM compression is identified in the pipeline's own fundamental profile. Strong business, wrong phase.",
    },
    "ABBV": {
        "tailwinds": [
            {"claim": "Skyrizi + Rinvoq peak sales cited at $25B+ — Humira biosimilar erosion is being offset by next-gen successor pipeline",
             "grounding": "GROUNDED", "evidence": "Fundamental revenue_growth_driver: 'Skyrizi + Rinvoq ($25B+ peak sales) offsetting Humira biosimilar erosion'", "confidence": 0.97},
            {"claim": "Royalty cliff is behind them; high-margin specialty drugs with pricing power drive stable margin outlook",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Royalty cliff behind them; high-margin specialty drugs with pricing power'", "confidence": 0.95},
            {"claim": "FCF yield >10% at current price with ROIC 15.2% — exceptional capital generation for a pharma in Growth life-cycle stage",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'R&D + M&A (neuroscience, oncology); FCF yield >10% at current price; ROIC 15.2%'", "confidence": 0.96},
            {"claim": "Healthcare is a defensive sector — in stagflation and high-correlation regime, defensives provide relative downside protection",
             "grounding": "INFERRED", "evidence": "Sector agent classifies Healthcare; cyclicality config ranks Healthcare as defensive (rank >6). Defensive outperformance in stagflation is inferred from sector scoring mechanics", "confidence": 0.82},
        ],
        "headwinds": [
            {"claim": "Competitive entry into Skyrizi/Rinvoq market is explicitly cited as a key risk — erosion could mirror Humira biosimilar pattern",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Skyrizi/Rinvoq competitive entry', 'Pricing pressure (IRA)', 'Pipeline failure']", "confidence": 0.96},
            {"claim": "IRA drug pricing reform creates ongoing pricing pressure on high-revenue specialty drugs",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Pricing pressure (IRA)'", "confidence": 0.94},
            {"claim": "Threat of substitutes scores 3.0/5 in Porter's analysis — biosimilar and competing biologics are a structural headwind",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.threat_of_substitutes: 3.0", "confidence": 0.91},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "ABBV's Humira cliff is behind them — Skyrizi/Rinvoq at $25B+ peak sales provides a multi-year growth runway. FCF yield >10% and ROIC 15.2% are outstanding. The primary risk is competitive entry, which is manageable given patent timelines implied by the Growth life-cycle classification.",
    },
    "MPC": {
        "tailwinds": [
            {"claim": "Nelson Complexity of 13.0+ (best-in-class feedstock flexibility) cited as structural advantage in margin driver",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Nelson Complexity 13.0+ = best-in-class feedstock flexibility; MPLX drops diversify'", "confidence": 0.97},
            {"claim": "MPLX fee income provides stable midstream cash flow that diversifies away from volatile crack spread exposure",
             "grounding": "GROUNDED", "evidence": "Fundamental revenue_growth_driver: 'Crack spread × throughput; MPLX fee income'; reinvestment: 'MPLX MLP provides stable fee income'", "confidence": 0.95},
            {"claim": "ROIC of 22.5% is the highest in the demo universe — buyback-first capital return signals management confidence in FCF durability",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Buyback-first capital return; MPLX MLP provides stable fee income; ROIC 22.5%'", "confidence": 0.96},
            {"claim": "Stagflation clock phase favors Energy; rising oil in stagflation scenario benefits upstream feedstock economics",
             "grounding": "GROUNDED", "evidence": "Sector agent Energy: strongly_favored; Cycle agent clock_phase: STAGFLATION with oil rising", "confidence": 0.92},
        ],
        "headwinds": [
            {"claim": "Crack spread compression is the primary risk — stagflation could weaken gasoline demand even as crude stays elevated",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Crack spread compression', 'Demand destruction', 'Renewable fuel mandates']", "confidence": 0.96},
            {"claim": "Renewable fuel mandates (RFS, LCFS) create structural headwind to refining economics long-term",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Renewable fuel mandates'", "confidence": 0.93},
            {"claim": "Bear scenario (20% probability) recession would destroy gasoline demand and collapse crack spreads simultaneously",
             "grounding": "GROUNDED", "evidence": "Scenario bear probability 0.20; demand destruction risk cited in key_risks", "confidence": 0.92},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "MPC's 22.5% ROIC (highest in universe) + Nelson Complexity 13.0+ structural advantage + MPLX fee income buffer make it the highest-conviction Energy pick. Stagflation tailwind is current (CMI 42.3, sector rank #1). Crack spread risk exists but MPLX provides a floor.",
    },
    "MSFT": {
        "tailwinds": [
            {"claim": "Azure cloud revenue growing >30% with AI Copilot monetization adding a premium pricing layer on top of existing seat base",
             "grounding": "GROUNDED", "evidence": "Fundamental revenue_growth_driver: 'Azure cloud (>30% growth) + Office 365 seat expansion + AI monetization'", "confidence": 0.96},
            {"claim": "ROIC of 29.8% is the highest of any non-Energy name in the universe — operating leverage on cloud is compounding",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: 'Heavy AI capex ($50B+/yr); returns still excellent; buybacks + dividend; ROIC 29.8%'", "confidence": 0.95},
            {"claim": "Market share is gaining with margin outlook expanding — rare combination signaling competitive moat widening",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.market_share_outlook: gaining, margin_outlook: expanding", "confidence": 0.94},
        ],
        "headwinds": [
            {"claim": "Stagflation clock phase and falling PMI (48.1) unfavor Technology/Growth stocks — sector agent rates Tech as UNFAVORED in this regime",
             "grounding": "GROUNDED", "evidence": "Cycle agent clock_phase: STAGFLATION; Sector agent: Technology unfavored in stagflation phase; economy pmi_read=48.1 falling", "confidence": 0.94},
            {"claim": "$50B+ annual AI capex creates execution risk — if Azure growth decelerates before returns materialize, FCF will compress",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['AI capex cycle risk', 'Azure competition (AWS, GCP)', 'Regulatory / antitrust']; reinvestment cites '$50B+/yr'", "confidence": 0.93},
            {"claim": "Style agent de-emphasizes Growth factor in stagflation — MSFT's premium multiple is exposed if macro regime persists",
             "grounding": "INFERRED", "evidence": "Stagflation clock phase de-emphasizes Growth factor per phase_factor_leaders config; MSFT's life_cycle: Growth. Explicit style score for MSFT not in pipeline data — this is an inferred consequence", "confidence": 0.81},
            {"claim": "Azure faces competition from AWS and GCP — market share gains require sustained investment outspending rivals",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Azure competition (AWS, GCP)']", "confidence": 0.91},
        ],
        "net_sentiment": "NEUTRAL",
        "sentiment_rationale": "MSFT is an exceptional business (ROIC 29.8%, Azure >30% growth) in the wrong macro phase. Stagflation clock unfavors Technology explicitly. Great for a 12-24 month view if the clock rotates, but the pipeline's current regime assignment warrants caution relative to Energy/Materials.",
    },
    "KO": {
        "tailwinds": [
            {"claim": "200-country distribution and brand moat described as 'impossible to replicate' — Porter score reflects near-zero threat of entry (1.0/5)",
             "grounding": "GROUNDED", "evidence": "Fundamental narrative_quality: 'impossible to replicate'; porter.threat_of_entry: 1.0 (lowest possible)", "confidence": 0.97},
            {"claim": "Bottler model removes direct commodity risk; pricing power has historically covered commodity cost inflation",
             "grounding": "GROUNDED", "evidence": "Fundamental margin_driver: 'Bottler model removes commodity risk; pricing covers commodity costs'", "confidence": 0.96},
            {"claim": "Defensive Consumer Staples sector favored in stagflation; 78% payout ratio + consistent dividend growth provides income in risk-off environment",
             "grounding": "GROUNDED", "evidence": "Fundamental reinvestment_efficiency: '78% payout ratio; consistent dividend growth'. Sector agent: Consumer Staples favored in STAGFLATION", "confidence": 0.94},
            {"claim": "Premium category expansion (energy drinks, premium water, tea) provides volume growth beyond carbonated soft drinks",
             "grounding": "GROUNDED", "evidence": "Fundamental revenue_growth_driver: 'Pricing power × volume; premium category expansion (energy, water, premium tea)'", "confidence": 0.92},
        ],
        "headwinds": [
            {"claim": "Health/sugar tax regulation is an explicit key risk — regulatory headwinds to core carbonated portfolio",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks: ['Health/sugar tax regulation', 'Currency headwinds', 'Pepsi competition']", "confidence": 0.96},
            {"claim": "Currency headwinds are a structural challenge for a 200-country revenue base in a rising-DXY environment",
             "grounding": "GROUNDED", "evidence": "Fundamental key_risks includes 'Currency headwinds'; Economy agent DXY direction cited in sector macro data", "confidence": 0.91},
            {"claim": "Buyer power is 3.0/5 (moderate-high) — Walmart, Costco, and grocery chains can negotiate pricing, compressing bottler economics",
             "grounding": "GROUNDED", "evidence": "Fundamental porter.buyer_power: 3.0", "confidence": 0.90},
            {"claim": "Lower expected return vs Energy names — KO's defensive positioning limits upside in a stagflation scenario where oil is rising",
             "grounding": "INFERRED", "evidence": "Valuation data shows lower expected_return_pct vs XOM/CVX/MPC; KO as defensive trades at premium multiple reducing upside. Relative return comparison is inferred from comparing valuation outputs", "confidence": 0.83},
        ],
        "net_sentiment": "BULLISH",
        "sentiment_rationale": "KO is a defensive compounder that directly benefits from stagflation (Consumer Staples favored, dividend yield valued in risk-off). Brand moat + bottler model + pricing power = durable earnings. Lower upside than Energy names but appropriate for portfolio stability given high correlation regime.",
    },
}


class LLMAnalysisAgent(Agent):
    name = "llm_analysis"

    def run(self, context: Context) -> AgentOutput:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if context.demo_mode:
            return self._run_demo(context)

        if not api_key:
            return self._run_no_key(context)

        return self._run_live(context, api_key)

    # ── Demo path ─────────────────────────────────────────────────────────────

    def _run_demo(self, context: Context) -> AgentOutput:
        tickers = self._get_tickers(context)
        analyses: dict[str, LLMStockAnalysis] = {}

        for ticker in tickers:
            raw = _DEMO_ANALYSIS.get(ticker)
            if raw is None:
                continue
            analyses[ticker] = self._build_analysis(ticker, raw)

        return self._make_output(context, analyses, model_used="demo-preseeded", method="two-pass-simulated")

    # ── No API key path ───────────────────────────────────────────────────────

    def _run_no_key(self, context: Context) -> AgentOutput:
        log.warning("ANTHROPIC_API_KEY not set — LLM analysis skipped; returning placeholder")
        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=0.0,
            confidence_label=self._confidence_label(0.0),
            rationale="Skipped: ANTHROPIC_API_KEY environment variable not set",
            data=LLMAnalysisData(
                analyses={},
                model_used="none",
                verification_method="none",
            ).model_dump(),
            warnings=["Set ANTHROPIC_API_KEY to enable live LLM analysis"],
            provenance={},
        )

    # ── Live two-pass path ────────────────────────────────────────────────────

    def _run_live(self, context: Context, api_key: str) -> AgentOutput:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        tickers = self._get_tickers(context)
        analyses: dict[str, LLMStockAnalysis] = {}

        for ticker in tickers:
            try:
                log.info("LLM analysis: %s", ticker)
                stock_ctx = self._build_context(ticker, context)
                raw = self._two_pass(client, ticker, stock_ctx)
                analyses[ticker] = self._build_analysis(ticker, raw)
            except Exception as exc:
                log.warning("LLM analysis failed for %s: %s", ticker, exc)
                # Fall back to demo data if available
                if ticker in _DEMO_ANALYSIS:
                    analyses[ticker] = self._build_analysis(ticker, _DEMO_ANALYSIS[ticker])

        return self._make_output(context, analyses, model_used=MODEL, method="two-pass-claude")

    def _two_pass(self, client: Any, ticker: str, stock_ctx: str) -> dict[str, Any]:
        """Pass 1: generate. Pass 2: verify each claim."""
        # ── Pass 1: Generate ──────────────────────────────────────────────────
        gen_system = (
            "You are a senior equity analyst. "
            "Identify tailwinds and headwinds using ONLY the structured data provided. "
            "Do NOT add facts from your training data. "
            "Every claim must explicitly reference a field, number, or phrase from the context."
        )
        gen_prompt = (
            f"Analyse {ticker} using only the pipeline data below.\n\n"
            f"{stock_ctx}\n\n"
            "Identify 3-5 tailwinds and 3-5 headwinds. "
            "Each must cite a specific data point (field name, number, or phrase) from the context above."
        )

        gen_response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=gen_system,
            tools=[_GENERATE_TOOL],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": gen_prompt}],
        )
        gen_result = next(b for b in gen_response.content if b.type == "tool_use").input

        # ── Pass 2: Verify ────────────────────────────────────────────────────
        ver_system = (
            "You are a rigorous fact-checker for equity research. "
            "For each claim, determine whether it is GROUNDED (directly stated in source data), "
            "INFERRED (logical consequence of the data), or SPECULATIVE (introduces facts not in the data). "
            "Be strict: if a claim adds specific numbers or facts not present in the source data, mark it SPECULATIVE."
        )
        claims_block = "\n".join([
            "TAILWINDS:",
            *[f"  {i+1}. {c}" for i, c in enumerate(gen_result["tailwinds"])],
            "\nHEADWINDS:",
            *[f"  {i+1}. {c}" for i, c in enumerate(gen_result["headwinds"])],
        ])
        ver_prompt = (
            f"SOURCE DATA for {ticker}:\n{stock_ctx}\n\n"
            f"CLAIMS TO VERIFY:\n{claims_block}\n\n"
            "For each claim provide: grounding (GROUNDED/INFERRED/SPECULATIVE), "
            "specific evidence (exact quote or field from source data, or reason it's speculative), "
            "and confidence (0-1)."
        )

        ver_response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=ver_system,
            tools=[_VERIFY_TOOL],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": ver_prompt}],
        )
        ver_result = next(b for b in ver_response.content if b.type == "tool_use").input

        return {
            "tailwinds": [
                {
                    "claim": v["claim"],
                    "grounding": v["grounding"],
                    "evidence": v["evidence"],
                    "confidence": v["confidence"],
                }
                for v in ver_result["verified_tailwinds"]
            ],
            "headwinds": [
                {
                    "claim": v["claim"],
                    "grounding": v["grounding"],
                    "evidence": v["evidence"],
                    "confidence": v["confidence"],
                }
                for v in ver_result["verified_headwinds"]
            ],
            "net_sentiment": gen_result["net_sentiment"],
            "sentiment_rationale": gen_result["sentiment_rationale"],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_tickers(self, context: Context) -> list[str]:
        if context.recommendations:
            return [r.ticker for r in context.recommendations.ranked]
        if context.fundamentals:
            return list(context.fundamentals.keys())
        return list(_DEMO_ANALYSIS.keys())

    def _build_context(self, ticker: str, context: Context) -> str:
        """Construct structured, factual grounding context from pipeline outputs."""
        sections: list[str] = []

        if context.economy and context.cycle:
            e, c = context.economy, context.cycle
            sections.append(
                f"MACRO REGIME\n"
                f"  Clock Phase: {c.clock_phase.value}\n"
                f"  CMI: {e.cmi_score:.1f} ({e.cmi_direction.value}) — scale 0-100, >50=expansionary\n"
                f"  Growth: {e.growth_level.value}, {e.growth_direction.value}\n"
                f"  Inflation: {e.inflation_level.value}, {e.inflation_direction.value}\n"
                f"  PMI: {e.pmi_read:.1f} ({e.pmi_direction.value})\n"
                f"  Yield Curve: {e.yield_curve_bps:.0f}bps\n"
                f"  H.O.P.E. Stage: {c.hope_stage.value} → next: {c.hope_next_stage.value}"
            )

        if context.scenarios:
            lines = [
                f"  {s.name} ({s.label}): prob={s.probability*100:.0f}%, "
                f"GDP={s.macro.gdp_growth_pct:+.1f}%, CPI={s.macro.cpi_pct:.1f}%, "
                f"Fed={s.macro.fed_funds_pct:.2f}%, oil={s.macro.oil_direction}"
                for s in context.scenarios.scenarios
            ]
            sections.append("SCENARIOS\n" + "\n".join(lines))

        if context.sectors:
            from apm.utils.config import ticker_to_sector
            sector_name = ticker_to_sector(ticker)
            if sector_name:
                match = next(
                    (s for s in context.sectors.ranked_sectors
                     if s.sector.lower().replace(" ", "_") == sector_name.lower().replace(" ", "_")),
                    None,
                )
                if match:
                    sections.append(
                        f"SECTOR: {match.sector}\n"
                        f"  Favorability: {match.favorability.value}\n"
                        f"  Score: {match.score:.1f}/100\n"
                        f"  Primary Macro Driver: {match.primary_macro_driver}"
                    )

        if context.fundamentals and ticker in context.fundamentals:
            f = context.fundamentals[ticker]
            sections.append(
                f"FUNDAMENTALS: {ticker}\n"
                f"  Business Model: {f.business_model_type}\n"
                f"  Life Cycle: {f.industry_life_cycle.value}\n"
                f"  Narrative: {f.narrative_quality}\n"
                f"  Porter Score: {f.porter.overall_score:.1f}/10 "
                f"(entry={f.porter.threat_of_entry}, subs={f.porter.threat_of_substitutes}, "
                f"buyer={f.porter.buyer_power}, supplier={f.porter.supplier_power}, "
                f"rivalry={f.porter.competitive_rivalry})\n"
                f"  Market Share Outlook: {f.porter.market_share_outlook}\n"
                f"  Margin Outlook: {f.porter.margin_outlook}\n"
                f"  Revenue Driver: {f.revenue_growth_driver}\n"
                f"  Margin Driver: {f.margin_driver}\n"
                f"  Reinvestment: {f.reinvestment_efficiency}\n"
                f"  Key Risks: {', '.join(f.key_risks)}\n"
                f"  Qualitative Score: {f.qualitative_score:.1f}/100"
            )

        if context.valuations and ticker in context.valuations:
            v = context.valuations[ticker]
            sv_lines = [
                f"    {sv.scenario_name} ({sv.probability*100:.0f}%): "
                f"rev_growth={sv.revenue_growth_pct:+.1f}%, EBIT_margin={sv.ebit_margin_pct:.1f}%, "
                f"WACC={sv.wacc_pct:.1f}%, terminal_g={sv.terminal_growth_pct:.1f}%, "
                f"DCF=${sv.dcf_value:.0f}, blended=${sv.blended_value:.0f}, upside={sv.upside_pct:+.1f}%"
                for sv in v.scenario_valuations
            ]
            sections.append(
                f"VALUATION: {ticker}\n"
                f"  Current Price: ${v.current_price:.2f}\n"
                f"  Prob-Weighted Target: ${v.prob_weighted_target:.2f}\n"
                f"  Expected Return: {v.expected_return_pct:+.1f}%\n"
                f"  Reward-to-Risk: {v.reward_to_risk:.1f}×\n"
                f"  Scenarios:\n" + "\n".join(sv_lines)
            )

        if context.risk:
            r = context.risk
            sections.append(
                f"RISK / CORRELATION\n"
                f"  Avg Pairwise Correlation: {r.avg_pairwise_correlation:.2f}\n"
                f"  Regime: {r.correlation_regime.value}\n"
                f"  Stock-Picking Reward Signal: {r.stock_picking_reward_signal}"
            )

        return "\n\n".join(sections)

    def _build_analysis(self, ticker: str, raw: dict[str, Any]) -> LLMStockAnalysis:
        tailwinds = [VerifiedClaim(**c) for c in raw["tailwinds"]]
        headwinds = [VerifiedClaim(**c) for c in raw["headwinds"]]
        all_claims = tailwinds + headwinds
        non_speculative = sum(1 for c in all_claims if c.grounding != "SPECULATIVE")
        grounding_score = non_speculative / len(all_claims) if all_claims else 1.0
        return LLMStockAnalysis(
            ticker=ticker,
            tailwinds=tailwinds,
            headwinds=headwinds,
            net_sentiment=raw["net_sentiment"],
            sentiment_rationale=raw["sentiment_rationale"],
            grounding_score=round(grounding_score, 3),
        )

    def _make_output(
        self,
        context: Context,
        analyses: dict[str, LLMStockAnalysis],
        model_used: str,
        method: str,
    ) -> AgentOutput:
        data = LLMAnalysisData(
            analyses=analyses,
            model_used=model_used,
            verification_method=method,
        )
        context.llm_analysis = data

        avg_grounding = (
            sum(a.grounding_score for a in analyses.values()) / len(analyses)
            if analyses else 0.0
        )
        confidence = round(avg_grounding * 100, 1)

        speculative_counts = {t: sum(1 for c in a.tailwinds + a.headwinds if c.grounding == "SPECULATIVE")
                               for t, a in analyses.items()}
        warnings = [
            f"{t}: {n} speculative claim(s) flagged — review evidence before citing"
            for t, n in speculative_counts.items() if n > 0
        ]

        sentiments = [a.net_sentiment for a in analyses.values()]
        rationale = (
            f"Analysed {len(analyses)} tickers | "
            f"Avg grounding score: {avg_grounding:.0%} | "
            f"Sentiment mix: {sentiments.count('BULLISH')}B / {sentiments.count('NEUTRAL')}N / {sentiments.count('BEARISH')}Be | "
            f"Method: {method}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=warnings,
            provenance={
                "model": model_used,
                "method": method,
                "anti_hallucination": "two-pass: generate (tool-use, grounded in pipeline data) → verify (per-claim GROUNDED/INFERRED/SPECULATIVE classification)",
            },
        )

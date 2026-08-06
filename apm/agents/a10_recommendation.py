"""
Agent 10 — RecommendationAgent
Synthesizes all upstream agent outputs into ranked recommendations with
transparent confidence scores. Macro/cycle carry the heaviest weight (~70% rule).
"""

from __future__ import annotations

import logging

from apm.core.agent import (
    Agent, AgentOutput, ConfidenceBreakdown, Context, RecommendationsData, StockRecommendation,
)
from apm.core.types import Action, ConfidenceLabel, CorrelationRegime
from apm.utils.config import get_holdings, get_valuation_defaults, get_weights

log = logging.getLogger(__name__)


class RecommendationAgent(Agent):
    name = "recommendations"

    def run(self, context: Context) -> AgentOutput:
        for req in ("economy", "cycle", "scenarios", "sectors", "styles",
                    "screen", "fundamentals", "valuations", "risk"):
            if getattr(context, req) is None:
                raise RuntimeError(f"RecommendationAgent requires {req} agent output")

        weights = get_weights()
        holdings_cfg = get_holdings()
        current_holdings = {h["ticker"] for h in holdings_cfg.get("holdings", [])}
        holdings_by_group = {h["ticker"]: h.get("group", "other") for h in holdings_cfg.get("holdings", [])}

        ranked: list[StockRecommendation] = []
        for ticker, val in context.valuations.items():
            fund = context.fundamentals.get(ticker)
            if fund is None:
                continue

            breakdown, total_conf = self._compute_confidence(
                ticker, val, fund, context, weights
            )

            action = self._determine_action(ticker, val, total_conf, current_holdings)
            replaces = self._determine_replacement(ticker, action, holdings_by_group, context)
            label = self._confidence_label(total_conf)
            warnings = self._collect_warnings(val, breakdown)
            thesis = self._write_thesis(ticker, val, fund, action, context)

            ranked.append(StockRecommendation(
                ticker=ticker,
                action=action,
                current_price=val.current_price,
                prob_weighted_target=val.prob_weighted_target,
                expected_return_pct=val.expected_return_pct,
                reward_to_risk=val.reward_to_risk,
                conviction_score=round(total_conf, 1),
                conviction_label=label,
                conviction_breakdown=breakdown,
                replaces_ticker=replaces,
                thesis=thesis,
                scenario_table=val.scenario_valuations,
                warnings=warnings,
            ))

        ranked.sort(key=lambda r: r.conviction_score, reverse=True)

        data = RecommendationsData(
            ranked=ranked,
            correlation_regime=context.risk.correlation_regime,
            recommended_position_count_rationale=context.risk.recommended_position_count_guidance,
            as_of_date=context.as_of_date,
        )

        n_buy  = sum(1 for r in ranked if r.action == Action.BUY)
        n_hold = sum(1 for r in ranked if r.action == Action.HOLD)
        n_sell = sum(1 for r in ranked if r.action == Action.SELL)
        avg_confidence = sum(r.conviction_score for r in ranked) / len(ranked) if ranked else 0
        rationale = (
            f"{len(ranked)} stocks | "
            f"Buy: {n_buy} | Hold: {n_hold} | Sell: {n_sell} | "
            f"Avg confidence: {avg_confidence:.1f} | "
            f"Top: {', '.join(r.ticker for r in ranked[:3])}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=avg_confidence,
            confidence_label=self._confidence_label(avg_confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=[w for r in ranked for w in r.warnings],
            provenance={"weights_source": "config/weights.yaml"},
        )

    def _compute_confidence(
        self, ticker: str, val, fund, context: Context, weights: dict
    ) -> tuple[ConfidenceBreakdown, float]:
        w = weights["score_components"]
        p = weights["penalties"]

        # 1. Macro/cycle conviction (30 pts)
        economy = context.economy
        cycle = context.cycle
        cmi_clear = abs(economy.cmi_score - 50) > 10  # CMI meaningfully above/below 50
        clock_clean = cycle.phase_fit_confidence > 65
        macro_score = w["macro_cycle_conviction"]["weight"] * (
            (economy.phase_readiness_confidence / 100) * 0.5 +
            (cycle.phase_fit_confidence / 100) * 0.5
        )

        # 2. Sector fit (20 pts)
        favored_sectors = set(s.replace(" ", "_") for s in context.sectors.favored)
        stock_sector = (context.fundamentals.get(ticker, {}) or fund).industry_life_cycle  # reuse
        from apm.data.fetchers import fetch_fundamentals
        raw_fund = fetch_fundamentals(ticker)
        sector = raw_fund.get("sector", "").replace(" ", "_")
        in_favored = sector in favored_sectors
        sector_score = w["sector_fit"]["weight"] * (1.0 if in_favored else 0.4)

        # 3. Style/factor fit (15 pts) — zero and renormalize when screen data absent
        screen_candidate = next((c for c in context.screen.candidates if c.ticker == ticker), None)
        if screen_candidate is None:
            style_score = 0.0
            renorm_factor = 100.0 / (100 - w["style_factor_fit"]["weight"] - w["technical_catalyst"]["weight"])
        else:
            style_score = w["style_factor_fit"]["weight"] * (0.7 if screen_candidate.style_fit else 0.3)
            renorm_factor = 1.0

        # 4. Reward-to-risk (15 pts)
        rr = val.reward_to_risk
        rr_score = w["reward_to_risk"]["weight"] * min(1.0, rr / 4.0)

        # 5. Fundamental quality (8 pts)
        fund_score = w["fundamental_quality"]["weight"] * (fund.qualitative_score / 100)

        # 6. Cross-sectional valuation (5 pts) — negative discount = cheaper than peers
        discount = val.cross_sectional_discount_pct
        val_score = w["cross_sectional_valuation"]["weight"] * (
            1.0 if discount < -10 else (0.6 if discount < 0 else 0.2)
        )

        # 7. Technical catalyst (4 pts)
        tech_score = (
            0.0 if screen_candidate is None
            else w["technical_catalyst"]["weight"] * (1.0 if screen_candidate.technical_catalyst else 0.3)
        )

        # 8. Stock-picking regime (3 pts)
        regime = context.risk.correlation_regime
        regime_score = w["stock_picking_regime"]["weight"] * (
            0.5 if regime == CorrelationRegime.HIGH else 1.0
        )

        # Penalties
        no_down_penalty = -p["no_downside_scenario"]["max_deduction"] if not val.has_downside_scenario else 0
        terminal_g_penalty = -p["terminal_g_warning"]["max_deduction"] if val.terminal_g_warning else 0
        crowding_penalty = -p["crowding"]["max_deduction"] if ticker in context.risk.crowded_names else 0
        # Theme-not-universal: check if any favored factor fails cross-universe
        bad_factors = [f for f in context.styles.favored_factors if not f.cross_universe_holds]
        theme_penalty = -p["theme_not_universal"]["max_deduction"] if bad_factors else 0

        breakdown = ConfidenceBreakdown(
            macro_cycle_conviction=round(macro_score, 1),
            sector_fit=round(sector_score, 1),
            style_factor_fit=round(style_score, 1),
            reward_to_risk=round(rr_score, 1),
            fundamental_quality=round(fund_score, 1),
            cross_sectional_valuation=round(val_score, 1),
            technical_catalyst=round(tech_score, 1),
            stock_picking_regime=round(regime_score, 1),
            no_downside_scenario_penalty=round(no_down_penalty, 1),
            crowding_penalty=round(crowding_penalty, 1),
            terminal_g_warning_penalty=round(terminal_g_penalty, 1),
            theme_not_universal_penalty=round(theme_penalty, 1),
            renormalization_factor=round(renorm_factor, 4),
        )

        return breakdown, breakdown.total

    def _determine_action(
        self, ticker: str, val, confidence: float, current_holdings: set
    ) -> Action:
        d = get_valuation_defaults()
        if ticker in current_holdings:
            if (confidence < d["sell_confidence_max"]
                    or val.expected_return_pct < d["sell_return_max_pct"]
                    or val.reward_to_risk < d["hold_rr_min"]):
                return Action.SELL
            return Action.HOLD
        if (confidence >= d["buy_confidence_min"]
                and val.expected_return_pct > d["buy_return_min_pct"]
                and val.reward_to_risk > d["buy_rr_min"]):
            return Action.BUY
        if confidence < d["sell_confidence_max"] - 10 or val.expected_return_pct < -5:
            return Action.SELL
        return Action.HOLD

    def _determine_replacement(
        self, ticker: str, action: Action, holdings_by_group: dict, context: Context
    ) -> str | None:
        """For BUY: suggest which holding (same sector group) to fund with."""
        if action != Action.BUY:
            return None
        from apm.data.fetchers import fetch_fundamentals
        fund = fetch_fundamentals(ticker)
        sector = fund.get("sector", "")
        target_group = (
            "growth" if sector in ("Energy", "Materials", "Financials", "Technology", "Industrials")
            else "defensive"
        )
        candidates = [t for t, g in holdings_by_group.items() if g == target_group]
        return candidates[0] if candidates else None

    def _collect_warnings(self, val, breakdown: ConfidenceBreakdown) -> list[str]:
        warns = []
        if not val.has_downside_scenario:
            warns.append("No downside scenario — model integrity warning (-15 pts penalty applied)")
        if val.terminal_g_warning:
            warns.append(f"Terminal growth rate warning: {val.terminal_g_warning_msg}")
        if breakdown.crowding_penalty < 0:
            warns.append("Crowding detected — consensus Buy reduces marginal value of recommendation")
        return warns

    def _write_thesis(self, ticker: str, val, fund, action: Action, context: Context) -> str:
        economy = context.economy
        cycle = context.cycle
        sectors = context.sectors
        styles = context.styles
        from apm.data.fetchers import fetch_fundamentals
        raw = fetch_fundamentals(ticker)
        sector = raw.get("sector", "")

        top_factors = [f.factor_name for f in styles.favored_factors[:2]]

        return (
            f"Economy shows growth {economy.growth_level.value} & {economy.growth_direction.value} / "
            f"inflation {economy.inflation_direction.value} (CMI {economy.cmi_score:.0f}) → "
            f"Investment Clock: {cycle.clock_phase.value} (H.O.P.E.: {cycle.hope_stage.value}) → "
            f"Sector: {sector} {'✓ favored' if sector.replace(' ','_') in {s.replace(' ','_') for s in sectors.favored} else '✗ not favored'} → "
            f"Style: {', '.join(top_factors)} → "
            f"{ticker} ({action.value}): {fund.narrative_quality}. "
            f"DCF/multiples blended target ${val.prob_weighted_target:.0f} "
            f"({val.expected_return_pct:+.1f}% expected return; R:R {val.reward_to_risk:.1f}x). "
            f"Risks: {', '.join(fund.key_risks[:2])}."
        )

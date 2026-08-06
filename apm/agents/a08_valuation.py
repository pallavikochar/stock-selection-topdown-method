"""
Agent 8 — ValuationAgent
DCF in 6 steps + Credit Suisse / Mauboussin steady-state multiples,
run per scenario. Enforces: ≥1 scenario shows lower price.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from apm.core.agent import Agent, AgentOutput, Context, ScenarioValuation, ValuationData
from apm.core.types import LifeCycleStage
from apm.data.fetchers import fetch_fundamentals
from apm.utils.config import get_universe, get_valuation_assumptions, get_valuation_defaults
from apm.utils.sector_ratios import (
    get_valuation_weights, sector_cross_sectional, sector_third_valuation,
)

log = logging.getLogger(__name__)

# Shorthand for the valuation assumptions YAML (cached after first load)
def _va() -> dict:
    return get_valuation_assumptions()


# Sector-average operating margins used when yfinance doesn't provide one
_SECTOR_MARGIN_DEFAULTS: dict[str, float] = {
    "Technology": 0.22,
    "Communication_Services": 0.20,
    "Health_Care": 0.18,
    "Financials": 0.28,     # net interest margin proxy; not directly comparable
    "Energy": 0.13,
    "Materials": 0.11,
    "Industrials": 0.12,
    "Consumer_Discretionary": 0.10,
    "Consumer_Staples": 0.10,
    "Utilities": 0.15,
    "Real_Estate": 0.25,
}


def _parse_guidance_adjustment(text: str) -> float:
    """
    Extract a bounded ±2% rev_growth adjustment from management guidance text.
    Uses keyword frequency as a lightweight sentiment signal — no extra LLM call.
    """
    t = text.lower()
    pos = sum(t.count(w) for w in [
        "raised", "increased guidance", "exceeded", "beat consensus", "accelerat",
        "strong demand", "robust", "above expectations", "raised outlook",
        "outperform", "ahead of", "record revenue",
    ])
    neg = sum(t.count(w) for w in [
        "lowered", "cut guidance", "miss", "below expectations", "headwinds",
        "challenging", "decelerat", "soften", "reduced guidance", "below forecast",
        "shortfall", "cautious",
    ])
    net = pos - neg
    if net >= 2:
        return 0.02
    if net == 1:
        return 0.01
    if net <= -2:
        return -0.02
    if net == -1:
        return -0.01
    return 0.0


# Perpetuity growth rate bounds — read from valuation_defaults.json
def _terminal_g_map() -> dict[str, float]:
    d = get_valuation_defaults()
    return {
        "Startup": d["terminal_g_startup"] / 100,
        "Growth":  d["terminal_g_growth"]  / 100,
        "Mature":  d["terminal_g_mature"]  / 100,
        "Decline": d["terminal_g_decline"] / 100,
    }


class ValuationAgent(Agent):
    name = "valuation"

    def run(self, context: Context) -> AgentOutput:
        scenarios = context.scenarios
        fundamentals = context.fundamentals
        economy = context.economy
        if scenarios is None or fundamentals is None:
            raise RuntimeError("ValuationAgent requires Scenario + Fundamental agents first")

        self._defaults = get_valuation_defaults()
        risk_free = (economy.yield_curve_bps / 10000 + 0.0465) if economy else 0.0465
        universe = get_universe()
        demo_tickers = universe.get("demo_deep_dive_tickers", [])
        tickers = demo_tickers if context.demo_mode else list(fundamentals.keys())

        results: dict[str, ValuationData] = {}
        all_warnings: list[str] = []

        for ticker in tickers:
            fund_data = fundamentals.get(ticker)
            raw_fund = fetch_fundamentals(ticker)
            if fund_data is None:
                continue
            if not raw_fund.get("market_cap") and not raw_fund.get("revenue_ttm"):
                log.warning("%s: no fundamental data — skipping valuation", ticker)
                continue
            val, warns = self._value_ticker(
                ticker, raw_fund, fund_data, scenarios, risk_free
            )
            results[ticker] = val
            all_warnings.extend(warns)

        rationale = " | ".join(
            f"{t}: pw_target=${v.prob_weighted_target:.0f} ({v.expected_return_pct:+.1f}%)"
            + f" R:R={v.reward_to_risk:.1f}x"
            for t, v in list(results.items())[:4]
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=68.0,
            confidence_label=self._confidence_label(68.0),
            rationale=rationale,
            data={k: v.model_dump() for k, v in results.items()},
            warnings=all_warnings,
            provenance={
                "methodology": "DCF (6-step) + Credit Suisse/Mauboussin steady-state multiples per scenario",
                "risk_free_rate": f"{risk_free:.2%}",
                "valuation_rule": "Cross-sectional vs. current peers; valuation is a condition, not a catalyst",
            },
        )

    def _value_ticker(
        self,
        ticker: str,
        raw_fund: dict,
        fund_data: Any,
        scenarios: Any,
        risk_free: float,
    ) -> tuple[ValuationData, list[str]]:
        current_price = raw_fund.get("current_price", 0) or 0
        sector = raw_fund.get("sector", "Technology")
        life_cycle = fund_data.industry_life_cycle.value
        terminal_g_max = _terminal_g_map().get(life_cycle, self._defaults["terminal_g_mature"] / 100)

        scenario_vals: list[ScenarioValuation] = []
        warnings: list[str] = []
        prices: list[float] = []

        # Company-specific base growth (YoY actual; analyst-consensus forward)
        company_rev_growth_raw = raw_fund.get("revenue_growth_yoy") or 0.0
        # Cap near-term hypergrowth at 60% — it never sustains full 5 years
        company_rev_growth = min(abs(company_rev_growth_raw), 0.60) * (
            1 if company_rev_growth_raw >= 0 else -1
        )

        # Forward EPS from analyst consensus — preferred over TTM/shares calc
        forward_eps_raw = raw_fund.get("forward_eps")

        # RAG: retrieve management guidance before the scenario loop so the
        # directional adjustment can be applied to rev_growth in each scenario
        from apm.agents.a16_research import _rag_context
        rag_guidance = _rag_context(
            f"What revenue guidance did management give for {ticker}?",
            ticker=ticker,
        )
        rag_adj = _parse_guidance_adjustment(rag_guidance) if rag_guidance else 0.0
        if rag_guidance:
            adj_str = f"{rag_adj:+.0%}" if rag_adj != 0.0 else "neutral (no adjustment)"
            warnings.append(
                f"RAG guidance [{ticker}] → {adj_str}: {rag_guidance[:150]}"
            )

        shares = raw_fund.get("shares_outstanding", 0) or 1e9
        tax_rate = self._defaults["tax_rate_pct"] / 100
        sector_key = sector.replace(" ", "_")
        sales_to_capital = _va()["sales_to_capital"].get(sector_key, 0.60)
        reinv_cap = _va()["dcf"]["reinvestment_cap_pct"] / 100
        revenue = raw_fund.get("revenue_ttm", 0) or 1e9
        market_cap = raw_fund.get("market_cap", 0) or 1e10
        debt = raw_fund.get("total_debt", 0) or 0
        cash = raw_fund.get("cash", 0) or 0
        beta = raw_fund.get("beta", 1.0) or 1.0
        wacc_premium = _va()["wacc_premium"].get(sector_key, 0.030)
        equity_premium = self._defaults["equity_risk_premium"] / 100

        for scenario in scenarios.scenarios:
            macro = scenario.macro
            # Step 1: Revenue growth — blend company-specific growth with macro scenario
            # macro scenario determines how quickly growth decelerates toward macro baseline
            macro_growth = macro.revenue_growth_pct / 100
            # Bull scenario: company growth sustained; bear: mean-reverts to macro baseline
            scenario_blend = {
                "expanding": 0.85,   # bull — mostly company's own growth
                "stable":    0.60,   # base — moderate mean-reversion
                "compressing": 0.30, # bear — compress hard toward macro
            }.get(macro.market_multiple_path, 0.60)
            raw_growth = company_rev_growth * scenario_blend + macro_growth * (1 - scenario_blend)
            rev_growth = max(macro_growth, raw_growth) if raw_growth > 0 else raw_growth
            # Apply bounded RAG guidance adjustment (±2% max; already logged above)
            rev_growth = max(-0.30, min(0.80, rev_growth + rag_adj))

            # Step 2: Operating margin — base margin adjusted for scenario inflation
            base_margin = raw_fund.get("operating_margin")
            if base_margin is None:
                fallback = _SECTOR_MARGIN_DEFAULTS.get(sector_key, 0.12)
                log.warning(
                    "%s: operating_margin missing — using sector default %.0f%% (%s)",
                    ticker, fallback * 100, sector,
                )
                warnings.append(
                    f"{ticker}: operating_margin not available; "
                    f"using sector average {fallback:.0%} for {sector}"
                )
                base_margin = fallback
            if macro.margin_trajectory == "compressed":
                margin = base_margin * 0.92
            elif macro.margin_trajectory == "recovering":
                margin = base_margin * 1.05
            elif macro.margin_trajectory == "collapsing":
                margin = base_margin * 0.75
            elif macro.margin_trajectory == "expanding":
                margin = base_margin * 1.10
            else:
                margin = base_margin

            # Step 3: FCFF = NOPAT - Reinvestment
            ebit = revenue * margin
            nopat = ebit * (1 - tax_rate)
            reinvestment = min(
                (revenue * abs(rev_growth)) / max(sales_to_capital, 0.1),
                nopat * reinv_cap,
            )
            fcff = nopat - reinvestment

            # Step 4: WACC
            cost_of_equity = risk_free + beta * equity_premium
            cost_of_debt_after_tax = (risk_free + wacc_premium) * (1 - tax_rate)
            total_cap = market_cap + debt
            we = market_cap / total_cap if total_cap else 0.8
            wd = debt / total_cap if total_cap else 0.2
            wacc = cost_of_equity * we + cost_of_debt_after_tax * wd

            # Step 5: Terminal value — warn if g too high
            terminal_g = min(
                terminal_g_max,
                rev_growth * 0.3,  # terminal g ≤ 30% of near-term growth (sanity check)
            )
            terminal_g_warn = terminal_g > min(0.03, risk_free)
            if terminal_g_warn:
                warnings.append(
                    f"{ticker}/{scenario.label}: terminal g={terminal_g:.2%} may exceed sustainable bound"
                )

            # Bear case: also compress the multiple (per course requirement)
            multiple_adj = 1.0
            if macro.market_multiple_path == "compressing":
                multiple_adj = self._defaults["bear_multiple_adj"]
            elif macro.market_multiple_path == "expanding":
                multiple_adj = self._defaults["bull_multiple_adj"]

            # Step 5b: Terminal value uses year-5 FCFF as base (not current FCFF)
            fcff_year5 = fcff * (1 + rev_growth) ** 5
            if wacc <= terminal_g:
                pv_tv = fcff_year5 * _va()["dcf"]["tv_fallback_multiple"] / (1 + wacc) ** 5
            else:
                tv = fcff_year5 * (1 + terminal_g) / (wacc - terminal_g)
                pv_tv = tv / (1 + wacc) ** 5

            # Step 6: PV of 5-year growing FCFF stream + PV of terminal value
            pv_stream = fcff * sum((1 + rev_growth) ** t / (1 + wacc) ** t for t in range(1, 6))
            dcf_value_firm = pv_stream + pv_tv
            dcf_value_equity = (dcf_value_firm - debt + cash)
            dcf_per_share = max(1.0, dcf_value_equity / shares) if shares else 1.0

            # Multiples: sector-median forward P/E
            # Prefer analyst-consensus forward EPS; fall back to TTM/shares * scenario growth
            base_pe = _va()["forward_pe"].get(sector_key, 18.0)
            rate_adj = max(0.7, 1.0 - (risk_free - 0.04) * _va()["rate_pe_sensitivity"])
            lc_adj = _va()["lifecycle_pe_adj"].get(life_cycle, 1.0)
            sector_pe = base_pe * rate_adj * multiple_adj * lc_adj
            if forward_eps_raw and forward_eps_raw > 0:
                # Use analyst forward EPS directly — already a 1-year forward estimate
                fwd_eps = forward_eps_raw * multiple_adj
            else:
                ttm_eps = raw_fund.get("net_income_ttm", 0) / shares if shares else 0
                fwd_eps = ttm_eps * (1 + macro.earnings_growth_pct / 100)
            multiples_per_share = max(1.0, sector_pe * fwd_eps) if fwd_eps > 0 else 1.0

            # Sector-specific third valuation leg
            third_val, _ = sector_third_valuation(
                raw_fund, sector, life_cycle, cost_of_equity, terminal_g,
                macro.earnings_growth_pct,
            )
            has_third = third_val > 0
            dcf_w, mult_w, third_w = get_valuation_weights(sector_key, life_cycle, has_third)
            blended = (
                dcf_per_share * dcf_w
                + multiples_per_share * mult_w
                + (third_val * third_w if has_third else 0)
            )
            upside_pct = (blended - current_price) / current_price * 100 if current_price else 0

            scenario_vals.append(ScenarioValuation(
                scenario_name=scenario.label,
                probability=scenario.probability,
                revenue_growth_pct=macro.revenue_growth_pct,
                ebit_margin_pct=margin * 100,
                wacc_pct=wacc * 100,
                terminal_growth_pct=terminal_g * 100,
                dcf_value=round(dcf_per_share, 2),
                multiples_value=round(multiples_per_share, 2),
                blended_value=round(blended, 2),
                upside_pct=round(upside_pct, 1),
            ))
            prices.append(blended)

        has_downside = any(v.blended_value < current_price for v in scenario_vals)
        if not has_downside:
            warnings.append(
                f"{ticker}: NO scenario shows price below current ${current_price:.0f} — model integrity warning"
            )

        # Probability-weighted target
        pw_target = sum(v.blended_value * v.probability for v in scenario_vals)
        expected_return = (pw_target - current_price) / current_price * 100 if current_price else 0

        # Reward to risk: weighted upside / weighted downside
        w_upside = sum(v.probability * max(0, v.upside_pct) for v in scenario_vals)
        w_downside = sum(v.probability * max(0, -v.upside_pct) for v in scenario_vals)
        r_r = w_upside / w_downside if w_downside > 0 else w_upside / 1.0

        # Cross-sectional: sector-appropriate multiple (P/B for Financials; EV/EBITDA otherwise)
        stock_ev_ebit, peer_median, cross_sectional_discount = sector_cross_sectional(
            raw_fund, sector
        )

        return ValuationData(
            ticker=ticker,
            current_price=round(current_price, 2),
            prob_weighted_target=round(pw_target, 2),
            expected_return_pct=round(expected_return, 1),
            max_upside_pct=round(max(v.upside_pct for v in scenario_vals), 1),
            max_downside_pct=round(min(v.upside_pct for v in scenario_vals), 1),
            reward_to_risk=round(r_r, 1),
            scenario_valuations=scenario_vals,
            has_downside_scenario=has_downside,
            terminal_g_warning=any("terminal g" in w for w in warnings),
            terminal_g_warning_msg=next(
                (w for w in warnings if "terminal g" in w), None
            ),
            peer_ev_ebit_median=peer_median,
            stock_ev_ebit=round(stock_ev_ebit, 1),
            cross_sectional_discount_pct=round(cross_sectional_discount, 1),
        ), warnings

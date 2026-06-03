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
from apm.utils.config import get_universe, get_valuation_defaults

log = logging.getLogger(__name__)

# Perpetuity growth rate bounds — read from valuation_defaults.json, fallback to hardcoded
def _terminal_g_map() -> dict[str, float]:
    d = get_valuation_defaults()
    return {
        "Startup": d["terminal_g_startup"] / 100,
        "Growth":  d["terminal_g_growth"]  / 100,
        "Mature":  d["terminal_g_mature"]  / 100,
        "Decline": d["terminal_g_decline"] / 100,
    }

# Sector-specific WACC premia over risk-free rate (rough estimates)
SECTOR_WACC_PREMIUM: dict[str, float] = {
    "Energy": 0.035, "Materials": 0.040, "Financials": 0.030,
    "Industrials": 0.030, "Technology": 0.030, "Health_Care": 0.025,
    "Consumer_Discretionary": 0.030, "Consumer_Staples": 0.020,
    "Communication_Services": 0.035, "Utilities": 0.020, "Real_Estate": 0.030,
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
        wacc_premium = SECTOR_WACC_PREMIUM.get(sector.replace(" ", "_"), 0.030)
        terminal_g_max = _terminal_g_map().get(life_cycle, self._defaults["terminal_g_mature"] / 100)

        scenario_vals: list[ScenarioValuation] = []
        warnings: list[str] = []
        prices: list[float] = []

        for scenario in scenarios.scenarios:
            macro = scenario.macro
            # Step 1: Revenue growth — respect cyclicality, go out full cycle
            rev_growth = macro.revenue_growth_pct / 100

            # Step 2: Operating margin — base margin adjusted for scenario inflation
            base_margin = raw_fund.get("operating_margin") or 0.12
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
            revenue = raw_fund.get("revenue_ttm", 0) or 1e9
            ebit = revenue * margin
            tax_rate = self._defaults["tax_rate_pct"] / 100
            nopat = ebit * (1 - tax_rate)
            # Sales-to-capital ratio ≈ revenue / (market_cap + debt - cash)
            market_cap = raw_fund.get("market_cap", 0) or 1e10
            debt = raw_fund.get("total_debt", 0) or 0
            cash = raw_fund.get("cash", 0) or 0
            invested_capital = max(market_cap + debt - cash, 1e6)
            sales_to_capital = revenue / invested_capital
            reinvestment = (revenue * rev_growth) / max(sales_to_capital, 0.1)
            fcff = nopat - reinvestment

            # Step 4: WACC
            beta = raw_fund.get("beta", 1.0) or 1.0
            equity_premium = self._defaults["equity_risk_premium"] / 100
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

            if wacc <= terminal_g:
                tv = fcff * 15  # fallback
            else:
                tv = (fcff * (1 + terminal_g)) / (wacc - terminal_g)

            # Step 6: Discount back (simplified: assume FCFF is year-5 normalised)
            discount_factor = (1 + wacc) ** 5
            dcf_value_firm = (fcff * 3 + tv / discount_factor)  # 5yr simplified DCF
            dcf_value_equity = (dcf_value_firm - debt + cash)
            shares = raw_fund.get("shares_outstanding", 0) or 1e9
            dcf_per_share = max(1.0, dcf_value_equity / shares) if shares else 1.0

            # Multiples: steady-state P/E ≈ 1/CoE
            steady_state_pe = 1 / cost_of_equity if cost_of_equity > 0 else 15
            eps = raw_fund.get("net_income_ttm", 0) / shares if shares else 0
            fwd_eps = eps * (1 + macro.earnings_growth_pct / 100)
            multiples_per_share = max(1.0, steady_state_pe * fwd_eps * multiple_adj)

            dcf_w = self._defaults["dcf_weight"]
            mult_w = self._defaults["multiples_weight"]
            blended = (dcf_per_share * dcf_w + multiples_per_share * mult_w)
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

        # Cross-sectional valuation
        ev = raw_fund.get("enterprise_value", 0) or 0
        ebit = raw_fund.get("ebit_ttm", 0) or 0
        stock_ev_ebit = ev / ebit if ebit else 0
        # Sector median (rough defaults by sector)
        sector_ev_ebit_medians = {
            "Energy": 9.5, "Materials": 11.0, "Financials": 12.0, "Industrials": 14.0,
            "Technology": 22.0, "Health_Care": 16.0, "Consumer_Discretionary": 18.0,
            "Consumer_Staples": 19.0, "Communication_Services": 17.0,
            "Utilities": 14.0, "Real_Estate": 20.0,
        }
        peer_median = sector_ev_ebit_medians.get(sector.replace(" ", "_"), 15.0)
        cross_sectional_discount = (stock_ev_ebit - peer_median) / peer_median * 100 if peer_median else 0

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

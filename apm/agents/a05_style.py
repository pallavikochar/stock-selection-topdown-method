"""
Agent 5 — StyleAgent
Picks favored factors/styles for the current phase from Piper's factor-cycle map.
Encodes the size/style cyclicality spectrum and the dividend-yield-is-cyclical warning.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, FactorRecommendation, StyleData
from apm.core.types import ClockPhase, MarketCyclePhase
from apm.utils.config import get_factor_macro_corr, get_phase_factor_leaders, get_size_style_cyclicality

log = logging.getLogger(__name__)

# Map clock phase → market cycle phase for factor lookup
CLOCK_TO_MARKET: dict[str, str] = {
    "REFLATION": "Recovery",
    "INFLATION": "Expansion",
    "STAGFLATION": "Quality",
    "DEFLATION": "Trough",
    "UNKNOWN": "Quality",
}

# Value vs. Growth read by inflation direction
VALUE_GROWTH_READ: dict[str, str] = {
    "rising": (
        "FAVOR VALUE over Growth — growth-vs-value is largely a decision about inflation. "
        "Rising inflation compresses long-duration growth multiples; value stocks carry "
        "shorter duration and benefit from rising nominal earnings."
    ),
    "falling": (
        "FAVOR GROWTH over Value — falling inflation re-rates long-duration growth assets "
        "and supports multiple expansion."
    ),
    "stable": (
        "NEUTRAL on value vs. growth — inflation stable; other factors dominate."
    ),
}


class StyleAgent(Agent):
    name = "style"

    def run(self, context: Context) -> AgentOutput:
        economy = context.economy
        cycle = context.cycle
        if economy is None or cycle is None:
            raise RuntimeError("StyleAgent requires Economy + Cycle agents to run first")

        phase_key = cycle.clock_phase.value  # e.g. "STAGFLATION"
        market_phase = CLOCK_TO_MARKET.get(phase_key, "Quality")

        phase_cfg = get_phase_factor_leaders()["phase_factor_leaders"].get(market_phase, {})
        factor_corr = get_factor_macro_corr()["factors"]
        size_cfg = get_size_style_cyclicality()

        # Build favored factors
        favored_factors: list[FactorRecommendation] = []
        for f in phase_cfg.get("favored_factors", []):
            name = f["name"]
            corr_entry = factor_corr.get(name.replace(" ", "_"), {})
            classification = corr_entry.get("classification", "unknown")
            cross_universe = self._cross_universe_check(name, cycle.clock_phase)
            favored_factors.append(FactorRecommendation(
                factor_name=name,
                classification=classification,
                rationale=f.get("rationale", ""),
                weight=f.get("weight", 0.25),
                cross_universe_holds=cross_universe,
            ))

        avoid = phase_cfg.get("avoid_factors", [])

        # Size/style box: pick most appropriate for phase
        size_style_box = self._pick_size_style_box(cycle.clock_phase, size_cfg)

        val_growth = VALUE_GROWTH_READ.get(economy.inflation_direction.value, VALUE_GROWTH_READ["stable"])

        dividend_warning = (
            "WARNING: High Dividend Yield is a CYCLICAL factor (positive beta/leverage correlation). "
            "Dividend ETFs carry large sector biases (Utilities, Financials, Energy). "
            "Do not assume dividend yield = defensive."
        )

        # Cross-universe check: flag factors that only work in one slice
        theme_warnings = [
            f"Factor '{f.factor_name}' does not hold cross-universe — apply a penalty"
            for f in favored_factors if not f.cross_universe_holds
        ]

        data = StyleData(
            favored_factors=favored_factors,
            avoid_factors=avoid,
            favored_size_style_box=size_style_box,
            value_vs_growth_read=val_growth,
            dividend_yield_warning=dividend_warning,
            phase=MarketCyclePhase(market_phase),
        )

        rationale = (
            f"Phase: {market_phase} (from {phase_key} clock) | "
            f"Favored: {', '.join(f.factor_name for f in favored_factors)} | "
            f"Avoid: {', '.join(avoid)} | "
            f"Size/Style box: {size_style_box} | "
            f"Value vs. Growth: {val_growth[:60]}…"
        )

        confidence = 72.0 if all(f.cross_universe_holds for f in favored_factors) else 60.0
        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=theme_warnings,
            provenance={
                "factor_leaders_source": "config/phase_factor_leaders.yaml (Piper Sandler)",
                "factor_corr_source": "config/factor_macro_corr.yaml",
                "size_style_source": "config/size_style_cyclicality.yaml",
            },
        )

    def _cross_universe_check(self, factor_name: str, phase: ClockPhase) -> bool:
        """
        Simplified check: countercyclical factors tend to hold cross-universe in late cycle.
        Cyclical factors in early recovery also tend to hold cross-universe.
        Flag as False if factor is cycle-direction mismatched.
        """
        factor_corr = get_factor_macro_corr()["factors"]
        entry = factor_corr.get(factor_name.replace(" ", "_"), {})
        classification = entry.get("classification", "unknown")
        late_cycle = phase in (ClockPhase.STAGFLATION, ClockPhase.DEFLATION)
        if late_cycle and classification == "cyclical":
            return False  # cyclical factor in late cycle may only work in some sectors
        early_cycle = phase in (ClockPhase.REFLATION, ClockPhase.INFLATION)
        if early_cycle and classification == "countercyclical":
            return False
        return True

    def _pick_size_style_box(self, phase: ClockPhase, size_cfg: dict) -> str:
        spectrum = size_cfg.get("spectrum_most_to_least_cyclical", [])
        if phase == ClockPhase.REFLATION:
            entry = next((e for e in spectrum if e["rank"] == 1), {})
        elif phase == ClockPhase.INFLATION:
            entry = next((e for e in spectrum if e["rank"] == 3), {})
        elif phase == ClockPhase.STAGFLATION:
            entry = next((e for e in spectrum if e["rank"] == 8), {})
        else:  # DEFLATION / Trough
            entry = next((e for e in spectrum if e["rank"] == 9), {})
        return entry.get("box", "Large Cap Blend")

"""
Agent 2 — CycleAgent
Maps EconomyAgent output to an Investment Clock phase and H.O.P.E. stage.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, CycleData
from apm.core.types import ClockPhase, Direction, GrowthLevel, HopeStage, MarketCyclePhase
from apm.data.fetchers import get_macro_snapshot
from apm.utils.config import get_economic_view, get_hope_sequence

log = logging.getLogger(__name__)

# Merrill Lynch Investment Clock mapping
# (growth_level, growth_direction, inflation_direction) -> ClockPhase
CLOCK_MAP: dict[tuple, ClockPhase] = {
    ("below_trend", "rising", "falling"): ClockPhase.REFLATION,
    ("above_trend", "rising", "rising"): ClockPhase.INFLATION,
    ("above_trend", "falling", "rising"): ClockPhase.STAGFLATION,
    ("below_trend", "falling", "falling"): ClockPhase.DEFLATION,
    # Borderline cases — assign to nearest quadrant
    ("above_trend", "rising", "falling"): ClockPhase.INFLATION,   # expansion, disinflation
    ("below_trend", "rising", "rising"): ClockPhase.REFLATION,    # recovery with inflation
    ("above_trend", "falling", "falling"): ClockPhase.DEFLATION,  # slowdown, disinflation
    ("below_trend", "falling", "rising"): ClockPhase.DEFLATION,   # worst quadrant
}

# Clock phase → JPM market cycle phase
CLOCK_TO_MARKET: dict[ClockPhase, MarketCyclePhase] = {
    ClockPhase.REFLATION: MarketCyclePhase.RECOVERY,
    ClockPhase.INFLATION: MarketCyclePhase.EXPANSION,
    ClockPhase.STAGFLATION: MarketCyclePhase.QUALITY,
    ClockPhase.DEFLATION: MarketCyclePhase.TROUGH,
}


class CycleAgent(Agent):
    name = "cycle"

    def run(self, context: Context) -> AgentOutput:
        economy = context.economy
        if economy is None:
            raise RuntimeError("CycleAgent requires EconomyAgent to run first")

        cfg = get_economic_view()
        override = cfg.get("overrides", {}).get("force_clock_phase")

        # Determine clock phase
        if override:
            clock_phase = ClockPhase(override)
            confidence_penalty = 0  # forced — not penalised but noted
        else:
            key = (
                economy.growth_level.value,
                economy.growth_direction.value,
                economy.inflation_direction.value,
            )
            clock_phase = CLOCK_MAP.get(key, ClockPhase.UNKNOWN)
            confidence_penalty = 10 if clock_phase == ClockPhase.UNKNOWN else 0

        market_phase = CLOCK_TO_MARKET.get(clock_phase, MarketCyclePhase.GROWTH_SLOWDOWN)

        # H.O.P.E. stage
        hope_cfg_override = cfg.get("overrides", {}).get("force_hope_stage")
        if hope_cfg_override:
            hope_stage = HopeStage(hope_cfg_override)
        else:
            hope_stage = self._determine_hope_stage(context)

        hope_next = self._next_hope_stage(hope_stage)
        inflecting = self._inflecting_indicators(hope_stage, context)
        rotation = self._rotation_direction(clock_phase)

        # Confidence: how cleanly does the data fit one quadrant?
        fit_confidence = max(0.0, self._phase_fit_confidence(economy, clock_phase) - confidence_penalty)

        data = CycleData(
            clock_phase=clock_phase,
            market_cycle_phase=market_phase,
            hope_stage=hope_stage,
            hope_next_stage=hope_next,
            hope_inflecting_indicators=inflecting,
            rotation_direction=rotation,
            phase_fit_confidence=fit_confidence,
        )

        rationale = (
            f"Investment Clock: {clock_phase.value} "
            f"(growth {economy.growth_level.value} & {economy.growth_direction.value}; "
            f"inflation {economy.inflation_direction.value}) → "
            f"Market cycle: {market_phase.value} | "
            f"H.O.P.E. stage: {hope_stage.value} → next: {hope_next.value} | "
            f"Inflecting: {', '.join(inflecting[:3]) or 'none identified'}"
        )

        warnings = []
        if clock_phase == ClockPhase.UNKNOWN:
            warnings.append("Clock phase ambiguous — data straddles two quadrants")
        if hope_stage == HopeStage.EMPLOYMENT and clock_phase == ClockPhase.STAGFLATION:
            warnings.append("Late H.O.P.E. + Stagflation = cycle turn likely imminent")

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=fit_confidence,
            confidence_label=self._confidence_label(fit_confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=warnings,
            provenance={
                "clock_methodology": "Merrill Lynch Investment Clock (growth level/direction × inflation direction)",
                "market_cycle_source": "JPM / Piper Sandler phase map",
                "hope_source": "Piper Sandler Field Guide — rate-transmission sequence",
            },
        )

    def _determine_hope_stage(self, context: Context) -> HopeStage:
        """Locate the economy in the H.O.P.E. transmission sequence."""
        snap = get_macro_snapshot()
        nahb = snap.get("nahb_index", 50)
        permits_yoy_declining = snap.get("conference_board_lei_yoy_pct", 0) < -1.0
        ism_no = snap.get("ism_new_orders", 50)
        payrolls = snap.get("nonfarm_payrolls_mom_k", 200)

        # Housing has turned if NAHB < 50 and permits declining
        housing_turned = nahb < 50 and permits_yoy_declining

        # Orders turning if ISM NO < 50
        orders_turning = ism_no < 50

        # Employment still strong if payrolls > 150k (last to turn)
        employment_ok = payrolls > 150

        if not housing_turned:
            return HopeStage.HOUSING
        elif housing_turned and not orders_turning:
            return HopeStage.HOUSING  # housing turned, orders not yet
        elif orders_turning and employment_ok:
            return HopeStage.ORDERS   # orders turning, employment intact = Profits next
        elif orders_turning and not employment_ok:
            return HopeStage.PROFITS  # profits being cut, employment lagging
        else:
            return HopeStage.EMPLOYMENT

    def _next_hope_stage(self, current: HopeStage) -> HopeStage:
        sequence = [HopeStage.HOUSING, HopeStage.ORDERS, HopeStage.PROFITS, HopeStage.EMPLOYMENT]
        try:
            idx = sequence.index(current)
            return sequence[idx + 1] if idx + 1 < len(sequence) else HopeStage.HOUSING
        except ValueError:
            return HopeStage.ORDERS

    def _inflecting_indicators(self, stage: HopeStage, context: Context) -> list[str]:
        snap = get_macro_snapshot()
        if stage == HopeStage.HOUSING:
            return [f"NAHB={snap.get('nahb_index',43)}", "Building Permits declining YoY"]
        if stage == HopeStage.ORDERS:
            return [f"ISM New Orders={snap.get('ism_new_orders',48.1)}", "Cap Goods orders softening"]
        if stage == HopeStage.PROFITS:
            return ["EPS estimate revisions turning negative", "Industrial Production slowing"]
        if stage == HopeStage.EMPLOYMENT:
            return [f"Initial Claims rising ({snap.get('initial_claims_k',228)}k)", "Payrolls decelerating"]
        return []

    def _rotation_direction(self, phase: ClockPhase) -> str:
        if phase in (ClockPhase.INFLATION, ClockPhase.STAGFLATION):
            return "clockwise"   # peak cycle → late cycle
        if phase in (ClockPhase.DEFLATION, ClockPhase.REFLATION):
            return "clockwise"   # trough → early recovery
        return "stable"

    def _phase_fit_confidence(self, economy, phase: ClockPhase) -> float:
        if phase == ClockPhase.UNKNOWN:
            return 45.0
        # Higher confidence if economy signals are large and coherent
        cmi = economy.cmi_score
        if phase == ClockPhase.STAGFLATION and cmi < 50:
            return 78.0
        if phase == ClockPhase.DEFLATION and cmi < 35:
            return 82.0
        if phase == ClockPhase.INFLATION and cmi > 60:
            return 80.0
        if phase == ClockPhase.REFLATION and cmi > 55:
            return 75.0
        return 62.0

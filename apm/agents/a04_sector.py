"""
Agent 4 — SectorAgent
Ranks the 11 GICS sectors for the current phase using hard correlations
from the Piper Sandler Field Guide. Scores sectors by macro-variable alignment.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, SectorData, SectorScore
from apm.core.types import ClockPhase, Favorability
from apm.data.fetchers import get_macro_snapshot
from apm.utils.config import get_sector_cyclicality, get_sector_macro_corr

log = logging.getLogger(__name__)

# Direction of each macro variable in current demo scenario
# Agents read from context.economy; this is the mapping from variable to "good for"
VARIABLE_DIRECTION = {
    # positive corr + variable rising = favored; negative corr + variable rising = unfavored
    "ten_year_yield": "rising",     # rates rising
    "wti_oil": "rising",            # oil rising
    "us_pmi": "falling",            # PMI falling (contractionary)
    "dxy": "stable",
    "retail_sales": "falling",      # consumer under pressure
    "copper": "stable",
    "baa_spread": "widening",       # spreads widening
}


class SectorAgent(Agent):
    name = "sector"

    def run(self, context: Context) -> AgentOutput:
        economy = context.economy
        cycle = context.cycle
        if economy is None or cycle is None:
            raise RuntimeError("SectorAgent requires Economy + Cycle agents to run first")

        snap = get_macro_snapshot()
        corr_cfg = get_sector_macro_corr()["correlations"]
        cyc_cfg = get_sector_cyclicality()["order_most_to_least_cyclical"]

        # Determine variable directions from live economy
        var_dirs = self._get_variable_directions(economy, snap)

        scored: list[SectorScore] = []
        for sector_name, corrs in corr_cfg.items():
            score, primary_driver, supporting, alignment = self._score_sector(
                sector_name, corrs, var_dirs, cycle.clock_phase, cyc_cfg
            )
            scored.append(SectorScore(
                sector=sector_name.replace("_", " "),
                favorability=self._score_to_favorability(score),
                score=round(score, 1),
                primary_macro_driver=primary_driver,
                supporting_drivers=supporting,
                correlation_alignment=alignment,
            ))

        scored.sort(key=lambda s: s.score, reverse=True)
        favored = [s.sector for s in scored if s.favorability in (Favorability.FAVORED, Favorability.STRONGLY_FAVORED)]
        unfavored = [s.sector for s in scored if s.favorability in (Favorability.UNFAVORED, Favorability.STRONGLY_UNFAVORED)]

        data = SectorData(
            ranked_sectors=scored,
            favored=favored,
            unfavored=unfavored,
            phase=cycle.clock_phase,
        )

        rationale = (
            f"Phase: {cycle.clock_phase.value} | "
            f"Macro drivers: rates {var_dirs.get('ten_year_yield','?')} / "
            f"oil {var_dirs.get('wti_oil','?')} / "
            f"PMI {var_dirs.get('us_pmi','?')} / "
            f"spreads {var_dirs.get('baa_spread','?')} | "
            f"Favored: {', '.join(favored[:4])} | Unfavored: {', '.join(unfavored[:3])}"
        )

        confidence = self._compute_confidence(scored)
        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=[],
            provenance={
                "correlations_source": "config/sector_macro_corr.yaml (Piper Sandler Field Guide)",
                "variable_directions": str(var_dirs),
            },
        )

    def _get_variable_directions(self, economy, snap: dict) -> dict[str, str]:
        return {
            "ten_year_yield": "rising" if snap.get("ten_year_yield_pct", 4.5) > 4.0 else "falling",
            "wti_oil": "rising" if snap.get("wti_crude_usd", 75) > 75 else "falling",
            "us_pmi": "falling" if economy.pmi_read < 50 else "rising",
            "dxy": "rising" if snap.get("dxy", 100) > 100 else "falling",
            "retail_sales": "falling" if economy.growth_direction.value == "falling" else "rising",
            "copper": "stable",
            "baa_spread": "widening" if snap.get("baa_credit_spread_pct", 1.5) > 1.5 else "tightening",
        }

    def _score_sector(
        self, sector: str, corrs: dict, var_dirs: dict, phase: ClockPhase, cyc_cfg: list
    ) -> tuple[float, str, list[str], dict]:
        score = 50.0  # base
        alignment: dict[str, float] = {}
        driver_scores: dict[str, float] = {}

        var_map = {
            "ten_year_yield": ("ten_year_yield", "rates"),
            "wti_oil": ("wti_oil", "oil"),
            "us_pmi": ("us_pmi", "PMI"),
            "dxy": ("dxy", "USD"),
            "retail_sales": ("retail_sales", "retail"),
            "copper": ("copper", "copper"),
            "baa_spread": ("baa_spread", "spreads"),
        }

        for var_key, (dir_key, label) in var_map.items():
            corr = corrs.get(var_key)
            if corr is None:
                continue
            direction = var_dirs.get(dir_key, "stable")
            if direction == "rising":
                contribution = corr * 15  # positive corr + rising = good
            elif direction == "falling" or direction == "widening":
                contribution = -corr * 15  # positive corr + falling = bad
            else:
                contribution = 0
            score += contribution
            alignment[label] = round(contribution, 1)
            driver_scores[label] = abs(contribution)

        # Cyclicality adjustment based on phase
        rank_entry = next((e for e in cyc_cfg if e["sector"] == sector.replace("_", " ")), None)
        if rank_entry:
            rank = rank_entry["rank"]  # 1=most cyclical, 11=most defensive
            is_cyclical = rank <= 5
            if phase in (ClockPhase.INFLATION, ClockPhase.REFLATION):
                score += (6 - rank) * 2  # cyclicals get bonus in expansion
            elif phase in (ClockPhase.STAGFLATION, ClockPhase.DEFLATION):
                score += (rank - 6) * 2  # defensives get bonus in contraction

        score = max(0, min(100, score))

        if driver_scores:
            primary_driver_key = max(driver_scores, key=driver_scores.get)
            primary_driver = f"{primary_driver_key} ({alignment.get(primary_driver_key, 0):+.1f})"
        else:
            primary_driver = "no primary driver identified"

        exclude_key = primary_driver_key if driver_scores else None
        supporting = [
            f"{k}: {v:+.1f}"
            for k, v in sorted(alignment.items(), key=lambda x: abs(x[1]), reverse=True)
            if k != exclude_key
        ][:3]

        return score, primary_driver, supporting, alignment

    def _score_to_favorability(self, score: float) -> Favorability:
        if score >= 70:
            return Favorability.STRONGLY_FAVORED
        if score >= 58:
            return Favorability.FAVORED
        if score >= 43:
            return Favorability.NEUTRAL
        if score >= 30:
            return Favorability.UNFAVORED
        return Favorability.STRONGLY_UNFAVORED

    def _compute_confidence(self, scored: list[SectorScore]) -> float:
        spread = scored[0].score - scored[-1].score if scored else 0
        return round(min(85.0, 50 + spread * 0.5), 1)

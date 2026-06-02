"""
Agent 3 — ScenarioAgent
Loads the unified scenario set, validates probabilities sum to 1.0,
and produces per-scenario macro assumptions consumed by ValuationAgent.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, Scenario, ScenarioMacro, ScenariosData
from apm.utils.config import get_scenarios

log = logging.getLogger(__name__)


class ScenarioAgent(Agent):
    name = "scenario"

    def run(self, context: Context) -> AgentOutput:
        raw = get_scenarios()
        scenarios: list[Scenario] = []
        labels = ["base_case", "bull_case", "bear_case"]

        for label in labels:
            cfg = raw.get(label)
            if cfg is None:
                continue
            macro_cfg = cfg["macro"]
            scenario = Scenario(
                name=label,
                label=cfg["name"],
                probability=cfg["probability"],
                macro=ScenarioMacro(
                    gdp_growth_pct=macro_cfg["gdp_growth_pct"],
                    revenue_growth_pct=macro_cfg["revenue_growth_pct"],
                    cpi_pct=macro_cfg["cpi_pct"],
                    fed_funds_pct=macro_cfg["fed_funds_pct"],
                    ten_year_yield_pct=macro_cfg["ten_year_yield_pct"],
                    margin_trajectory=macro_cfg["margin_trajectory"],
                    market_multiple_path=macro_cfg["market_multiple_path"],
                    earnings_growth_pct=macro_cfg["earnings_growth_pct"],
                    credit_spread_direction=macro_cfg["credit_spread_direction"],
                    oil_direction=macro_cfg["oil_direction"],
                    pmi_direction=macro_cfg["pmi_direction"],
                ),
            )
            scenarios.append(scenario)

        data = ScenariosData(
            scenarios=scenarios,
            base_case_name=raw["base_case"]["name"],
        )  # Pydantic validator fires here — raises if sum != 1.0

        total_prob = sum(s.probability for s in scenarios)
        rationale = (
            f"{len(scenarios)} scenarios loaded: "
            + " | ".join(f"{s.label} {s.probability:.0%}" for s in scenarios)
            + f" | Total: {total_prob:.3f}"
        )

        warnings = []
        base = next((s for s in scenarios if s.name == "base_case"), None)
        if base:
            bull_down = [s for s in scenarios if s.name != "base_case" and
                         s.macro.gdp_growth_pct < base.macro.gdp_growth_pct]
            if not bull_down:
                warnings.append("No scenario with GDP below base — add a bear case")

        confidence = 90.0  # scenarios are config-driven; confidence is in the process, not the data

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=rationale,
            data=data.model_dump(),
            warnings=warnings,
            provenance={"source": "config/scenarios.yaml"},
        )

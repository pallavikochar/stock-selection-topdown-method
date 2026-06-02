"""Tests: scenario validation, probability sum, base-case consistency."""

import pytest
from apm.agents.a03_scenario import ScenarioAgent
from apm.core.agent import Context, ScenariosData


def make_context(demo=True):
    return Context(run_id="test", demo_mode=demo, as_of_date="2026-06-02")


def test_probabilities_sum_to_one():
    ctx = make_context()
    agent = ScenarioAgent()
    output = agent.run(ctx)
    data = ScenariosData.model_validate(output.data)
    total = sum(s.probability for s in data.scenarios)
    assert abs(total - 1.0) < 0.001, f"Probabilities sum to {total}, not 1.0"


def test_base_case_present():
    ctx = make_context()
    output = ScenarioAgent().run(ctx)
    data = ScenariosData.model_validate(output.data)
    assert any(s.name == "base_case" for s in data.scenarios)


def test_has_downside_scenario():
    """At least one scenario must have lower GDP than base case (bear case)."""
    ctx = make_context()
    output = ScenarioAgent().run(ctx)
    data = ScenariosData.model_validate(output.data)
    base = next(s for s in data.scenarios if s.name == "base_case")
    bear_candidates = [s for s in data.scenarios if s.macro.gdp_growth_pct < base.macro.gdp_growth_pct]
    assert len(bear_candidates) >= 1, "No scenario has GDP below base case"


def test_invalid_probabilities_raise():
    """ScenariosData validator must reject probabilities that don't sum to 1."""
    from apm.core.agent import Scenario, ScenarioMacro
    from pydantic import ValidationError
    macro = ScenarioMacro(
        gdp_growth_pct=2.0, revenue_growth_pct=5.0, cpi_pct=3.0,
        fed_funds_pct=5.0, ten_year_yield_pct=4.5, margin_trajectory="stable",
        market_multiple_path="flat", earnings_growth_pct=8.0,
        credit_spread_direction="stable", oil_direction="stable", pmi_direction="stable",
    )
    with pytest.raises(ValidationError):
        ScenariosData(
            scenarios=[Scenario(name="a", label="A", probability=0.80, macro=macro)],
            base_case_name="a",
        )


def test_confidence_in_range():
    ctx = make_context()
    output = ScenarioAgent().run(ctx)
    assert 0 <= output.confidence <= 100

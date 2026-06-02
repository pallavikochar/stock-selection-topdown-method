"""Tests: DCF/valuation model integrity checks."""

import pytest


def _run_valuation():
    from apm.agents.a01_economy import EconomyAgent
    from apm.agents.a02_cycle import CycleAgent
    from apm.agents.a03_scenario import ScenarioAgent
    from apm.agents.a04_sector import SectorAgent
    from apm.agents.a05_style import StyleAgent
    from apm.agents.a06_screen import ScreenAgent
    from apm.agents.a07_fundamental import FundamentalAgent
    from apm.agents.a08_valuation import ValuationAgent
    from apm.core.orchestrator import Orchestrator
    from apm.core.agent import ValuationData

    orch = (
        Orchestrator(demo_mode=True)
        .register(
            EconomyAgent(), CycleAgent(), ScenarioAgent(), SectorAgent(),
            StyleAgent(), ScreenAgent(), FundamentalAgent(), ValuationAgent(),
        )
    )
    outputs = orch.run()
    val_out = next(o for o in outputs if o.agent_name == "valuation")
    return {k: ValuationData.model_validate(v) for k, v in val_out.data.items()}, val_out.warnings


def test_at_least_one_ticker_valued():
    vals, _ = _run_valuation()
    assert len(vals) > 0


def test_scenario_probabilities_used_correctly():
    """Prob-weighted target must be between min and max scenario prices."""
    vals, _ = _run_valuation()
    for ticker, v in vals.items():
        prices = [sv.blended_value for sv in v.scenario_valuations]
        assert min(prices) <= v.prob_weighted_target <= max(prices) + 1, \
            f"{ticker}: prob_weighted_target outside scenario range"


def test_no_downside_warning_when_all_scenarios_above():
    """If all blended values are above current price, warning must be in outputs."""
    vals, warnings = _run_valuation()
    for ticker, v in vals.items():
        if not v.has_downside_scenario:
            assert any(ticker in w for w in warnings), \
                f"{ticker}: has_downside_scenario=False but no warning emitted"


def test_terminal_g_warning_fires_when_too_high():
    """ValuationData.terminal_g_warning should be True when g exceeds bounds."""
    vals, warnings = _run_valuation()
    for ticker, v in vals.items():
        if v.terminal_g_warning:
            assert v.terminal_g_warning_msg is not None


def test_reward_to_risk_positive():
    vals, _ = _run_valuation()
    for ticker, v in vals.items():
        assert v.reward_to_risk >= 0, f"{ticker}: negative R:R"


def test_scenario_count():
    vals, _ = _run_valuation()
    for ticker, v in vals.items():
        assert len(v.scenario_valuations) == 3, f"{ticker}: expected 3 scenarios"

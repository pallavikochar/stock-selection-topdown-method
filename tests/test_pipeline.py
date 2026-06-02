"""Tests: full Economy → Recommendation pipeline on demo data."""

import pytest
from apm.core.agent import Context, EconomyData, CycleData, ScenariosData, SectorData
from apm.core.types import ClockPhase


def _run_full_pipeline():
    from apm.agents.a01_economy import EconomyAgent
    from apm.agents.a02_cycle import CycleAgent
    from apm.agents.a03_scenario import ScenarioAgent
    from apm.agents.a04_sector import SectorAgent
    from apm.agents.a05_style import StyleAgent
    from apm.agents.a06_screen import ScreenAgent
    from apm.agents.a07_fundamental import FundamentalAgent
    from apm.agents.a08_valuation import ValuationAgent
    from apm.agents.a09_risk_correlation import RiskCorrelationAgent
    from apm.agents.a10_recommendation import RecommendationAgent
    from apm.core.orchestrator import Orchestrator

    orch = (
        Orchestrator(demo_mode=True)
        .register(
            EconomyAgent(), CycleAgent(), ScenarioAgent(), SectorAgent(),
            StyleAgent(), ScreenAgent(), FundamentalAgent(), ValuationAgent(),
            RiskCorrelationAgent(), RecommendationAgent(),
        )
    )
    return orch.run()


def test_pipeline_runs_end_to_end():
    outputs = _run_full_pipeline()
    assert len(outputs) == 10  # all 10 agents (no ReportAgent in this test)
    for o in outputs:
        assert 0 <= o.confidence <= 100, f"{o.agent_name} confidence out of range"


def test_economy_agent_isolated():
    from apm.agents.a01_economy import EconomyAgent
    ctx = Context(run_id="t", demo_mode=True, as_of_date="2026-06-02")
    output = EconomyAgent().run(ctx)
    data = EconomyData.model_validate(output.data)
    assert data.cmi_score >= 0
    assert data.pmi_read > 0


def test_cycle_agent_isolated():
    from apm.agents.a01_economy import EconomyAgent
    from apm.agents.a02_cycle import CycleAgent
    from apm.core.orchestrator import Orchestrator
    ctx = Context(run_id="t", demo_mode=True, as_of_date="2026-06-02")
    economy_out = EconomyAgent().run(ctx)
    ctx.economy = EconomyData.model_validate(economy_out.data)
    output = CycleAgent().run(ctx)
    data = CycleData.model_validate(output.data)
    assert data.clock_phase in list(ClockPhase)


def test_sector_ranking_respects_cyclicality():
    """In Stagflation, Energy and Materials should be in the top half."""
    outputs = _run_full_pipeline()
    sector_out = next(o for o in outputs if o.agent_name == "sector")
    data = SectorData.model_validate(sector_out.data)
    ranked = [s.sector for s in data.ranked_sectors]
    top_half = ranked[: len(ranked) // 2]
    assert any("Energy" in s for s in top_half), "Energy should be in top half in Stagflation"


def test_high_correlation_guidance():
    """In demo (high-correlation regime), guidance should mention MORE names."""
    outputs = _run_full_pipeline()
    risk_out = next(o for o in outputs if o.agent_name == "risk_correlation")
    guidance = risk_out.data["recommended_position_count_guidance"]
    assert "MORE" in guidance.upper() or "15" in guidance, "High-corr regime should suggest more positions"


def test_no_downside_warning_fires():
    """If all scenario prices are above current, a warning must be emitted."""
    outputs = _run_full_pipeline()
    val_out = next(o for o in outputs if o.agent_name == "valuation")
    for ticker, val_data in val_out.data.items():
        if not val_data.get("has_downside_scenario"):
            assert any("NO scenario" in w or "no downside" in w.lower() for w in val_out.warnings), \
                f"{ticker}: missing no-downside warning"


def test_recommendation_confidence_in_range():
    outputs = _run_full_pipeline()
    rec_out = next(o for o in outputs if o.agent_name == "recommendations")
    for r in rec_out.data.get("ranked", []):
        conf = r["confidence_numeric"]
        assert 0 <= conf <= 100, f"{r['ticker']}: confidence {conf} out of range"

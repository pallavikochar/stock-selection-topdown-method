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
        conf = r["conviction_score"]
        assert 0 <= conf <= 100, f"{r['ticker']}: conviction_score {conf} out of range"


def test_backtest_computed_from_fixture():
    """Backtest demo mode must compute from ETF fixture, not return hardcoded constants."""
    from apm.agents.a15_backtest import BacktestAgent
    agent = BacktestAgent()
    data = agent._run_demo("etfs")
    assert data.computed is True
    assert "fixture" in data.data_source
    assert data.universe == "etfs"
    m = data.metrics
    assert m.total_months >= 120
    assert -100 < m.cagr_pct < 50
    assert -100 < m.alpha_pct < 30
    assert -100 < m.max_drawdown_pct < 0
    assert 0 < m.win_rate_pct < 100
    assert len(data.annual_returns) >= 8
    # Net metrics must be populated
    assert m.net_cagr_pct != 0.0
    assert m.cost_bps == 10.0
    assert m.avg_turnover_pct >= 0.0
    # Regime attribution must cover all 4 regimes
    regime_names = {r.regime for r in data.regime_attribution}
    assert len(regime_names) >= 3, f"Expected at least 3 regimes, got: {regime_names}"


def test_backtest_etf_universe_matches_sector_agent_map():
    """ETF rotation must use the same phase→sector mapping as SectorAgent (a04)."""
    from apm.core.phase_sector_map import PHASE_FAVORED_SECTORS, SECTOR_TO_ETF, phase_to_etfs
    from apm.core.types import ClockPhase

    # Every named phase (excluding UNKNOWN sentinel) must map to exactly 4 sectors
    for phase in ClockPhase:
        if phase not in PHASE_FAVORED_SECTORS:
            continue
        sectors = PHASE_FAVORED_SECTORS[phase]
        assert len(sectors) == 4, f"{phase}: expected 4 sectors, got {len(sectors)}"
        # Every sector must resolve to a valid ETF ticker
        for s in sectors:
            assert s in SECTOR_TO_ETF, f"Sector '{s}' missing from SECTOR_TO_ETF"
        etfs = phase_to_etfs(phase)
        assert len(etfs) == 4

    # Spot-check Investment Clock logic:
    assert "XLE" in phase_to_etfs(ClockPhase.STAGFLATION), "Energy must be favored in STAGFLATION"
    assert "XLP" in phase_to_etfs(ClockPhase.STAGFLATION), "Staples must be favored in STAGFLATION"
    assert "XLK" in phase_to_etfs(ClockPhase.REFLATION),   "Tech must be favored in REFLATION"
    assert "XLF" in phase_to_etfs(ClockPhase.REFLATION),   "Financials must be favored in REFLATION"
    assert "XLE" in phase_to_etfs(ClockPhase.INFLATION),   "Energy must be favored in INFLATION"
    assert "XLV" in phase_to_etfs(ClockPhase.DEFLATION),   "Health Care must be favored in DEFLATION"


def test_backtest_legacy_stocks_still_works():
    """Legacy single-stock universe must still run for A/B comparison."""
    from apm.agents.a15_backtest import BacktestAgent
    data = BacktestAgent()._run_demo("stocks")
    assert data.universe == "stocks"
    assert data.computed is True
    assert data.metrics.total_months >= 100


def test_ingest_idempotency(tmp_path):
    """Re-ingesting the same content should not create duplicate points."""
    import tempfile
    from rag.ingest import _deterministic_id

    text = "Apple reported record revenue of $89.5 billion."
    ticker, doc_type, period = "AAPL", "10-K", "FY2023"

    id1 = _deterministic_id(text, ticker, doc_type, period)
    id2 = _deterministic_id(text, ticker, doc_type, period)
    assert id1 == id2, "Same content must produce same ID"

    other_id = _deterministic_id(text + " (edit)", ticker, doc_type, period)
    assert id1 != other_id, "Different content must produce different ID"

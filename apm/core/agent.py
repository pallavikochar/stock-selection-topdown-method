"""
Agent ABC, AgentOutput, and Context — the shared contracts for the entire pipeline.

Every agent:
  1. Implements Agent.run(context) -> AgentOutput
  2. Reads what it needs from Context (already populated by upstream agents)
  3. Appends its typed output to Context and returns AgentOutput
  4. Can be run in isolation via Orchestrator.run_single() against cached upstream outputs
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from apm.core.types import (
    Action,
    ClockPhase,
    ConfidenceLabel,
    CorrelationRegime,
    Direction,
    Favorability,
    GrowthLevel,
    HopeStage,
    InflationLevel,
    LifeCycleStage,
    MarketCyclePhase,
)

OUTPUT_DIR = Path("output/agents")


# ── Per-agent typed output payloads ──────────────────────────────────────────


class EconomyData(BaseModel):
    growth_level: GrowthLevel
    growth_direction: Direction
    inflation_level: InflationLevel
    inflation_direction: Direction
    cmi_score: float = Field(description="Composite Macro Indicator 0–100; >50 = expansionary")
    cmi_direction: Direction
    lei_trajectory: str
    cost_of_money_read: str
    cost_of_goods_read: str
    pmi_read: float
    pmi_direction: Direction
    yield_curve_bps: float
    phase_readiness_confidence: float


class CycleData(BaseModel):
    clock_phase: ClockPhase
    market_cycle_phase: MarketCyclePhase
    hope_stage: HopeStage
    hope_next_stage: HopeStage
    hope_inflecting_indicators: list[str]
    rotation_direction: str  # "clockwise" | "counterclockwise" | "stable"
    phase_fit_confidence: float


class ScenarioMacro(BaseModel):
    gdp_growth_pct: float
    revenue_growth_pct: float
    cpi_pct: float
    fed_funds_pct: float
    ten_year_yield_pct: float
    margin_trajectory: str
    market_multiple_path: str
    earnings_growth_pct: float
    credit_spread_direction: str
    oil_direction: str
    pmi_direction: str


class Scenario(BaseModel):
    name: str
    label: str
    probability: float
    macro: ScenarioMacro


class ScenariosData(BaseModel):
    scenarios: list[Scenario]
    base_case_name: str

    @model_validator(mode="after")
    def probabilities_sum_to_one(self) -> "ScenariosData":
        total = sum(s.probability for s in self.scenarios)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scenario probabilities sum to {total:.4f}, must be 1.0")
        return self


class SectorScore(BaseModel):
    sector: str
    favorability: Favorability
    score: float  # 0–100
    primary_macro_driver: str
    supporting_drivers: list[str]
    correlation_alignment: dict[str, float]  # variable -> relevant corr value


class SectorData(BaseModel):
    ranked_sectors: list[SectorScore]  # sorted by score desc
    favored: list[str]
    unfavored: list[str]
    phase: ClockPhase


class FactorRecommendation(BaseModel):
    factor_name: str
    classification: str  # cyclical | countercyclical
    rationale: str
    weight: float
    cross_universe_holds: bool


class StyleData(BaseModel):
    favored_factors: list[FactorRecommendation]
    avoid_factors: list[str]
    favored_size_style_box: str
    value_vs_growth_read: str  # "growth-vs-value is largely a decision about inflation"
    dividend_yield_warning: str
    phase: MarketCyclePhase


class ScreenCandidate(BaseModel):
    ticker: str
    sector: str
    magic_formula_rank: int
    ebit_ev_rank: int
    ebit_tangible_assets_rank: int
    combined_rank: int
    peer_relative_cheapness_pct: float  # % discount vs. sector median EV/EBIT
    sector_fit: bool
    style_fit: bool
    above_20d_ma: bool
    above_200d_ma: bool
    technical_catalyst: bool
    is_current_holding: bool
    notes: str


class ScreenData(BaseModel):
    candidates: list[ScreenCandidate]  # sorted by combined_rank
    universe_size: int
    filtered_to: int


class PorterForces(BaseModel):
    threat_of_entry: float      # 0–5 (5 = high threat = bad for incumbent)
    threat_of_substitutes: float
    buyer_power: float
    supplier_power: float
    competitive_rivalry: float
    market_share_outlook: str   # "gaining" | "stable" | "losing"
    margin_outlook: str         # "expanding" | "stable" | "compressing"
    overall_score: float        # 0–10 (10 = strongest competitive position)


class FundamentalData(BaseModel):
    ticker: str
    industry_life_cycle: LifeCycleStage
    business_model_type: str
    narrative_quality: str
    porter: PorterForces
    revenue_growth_driver: str
    margin_driver: str
    reinvestment_efficiency: str
    key_risks: list[str]
    qualitative_score: float  # 0–100


class ScenarioValuation(BaseModel):
    scenario_name: str
    probability: float
    revenue_growth_pct: float
    ebit_margin_pct: float
    wacc_pct: float
    terminal_growth_pct: float
    dcf_value: float
    multiples_value: float
    blended_value: float
    upside_pct: float  # vs. current price; can be negative


class ValuationData(BaseModel):
    ticker: str
    current_price: float
    prob_weighted_target: float
    expected_return_pct: float
    max_upside_pct: float
    max_downside_pct: float
    reward_to_risk: float
    scenario_valuations: list[ScenarioValuation]
    has_downside_scenario: bool
    terminal_g_warning: bool
    terminal_g_warning_msg: Optional[str] = None
    peer_ev_ebit_median: float
    stock_ev_ebit: float
    cross_sectional_discount_pct: float  # negative = cheaper than peers


class RiskData(BaseModel):
    avg_pairwise_correlation: float
    correlation_regime: CorrelationRegime
    stock_picking_reward_signal: str  # "high" | "moderate" | "low"
    recommended_position_count_guidance: str
    concentration_flags: list[str]
    crowded_names: list[str]


class ConfidenceBreakdown(BaseModel):
    macro_cycle_conviction: float
    sector_fit: float
    style_factor_fit: float
    reward_to_risk: float
    fundamental_quality: float
    cross_sectional_valuation: float
    technical_catalyst: float
    stock_picking_regime: float
    no_downside_scenario_penalty: float
    crowding_penalty: float
    terminal_g_warning_penalty: float
    theme_not_universal_penalty: float

    @property
    def total(self) -> float:
        return max(
            0.0,
            min(
                100.0,
                (
                    self.macro_cycle_conviction
                    + self.sector_fit
                    + self.style_factor_fit
                    + self.reward_to_risk
                    + self.fundamental_quality
                    + self.cross_sectional_valuation
                    + self.technical_catalyst
                    + self.stock_picking_regime
                    + self.no_downside_scenario_penalty
                    + self.crowding_penalty
                    + self.terminal_g_warning_penalty
                    + self.theme_not_universal_penalty
                ),
            ),
        )


class StockRecommendation(BaseModel):
    ticker: str
    action: Action
    current_price: float
    prob_weighted_target: float
    expected_return_pct: float
    reward_to_risk: float
    confidence_numeric: float
    confidence_label: ConfidenceLabel
    confidence_breakdown: ConfidenceBreakdown
    replaces_ticker: Optional[str]
    thesis: str  # traceable Economy → Cycle → Sector → Style → Stock
    scenario_table: list[ScenarioValuation]
    warnings: list[str]


class RecommendationsData(BaseModel):
    ranked: list[StockRecommendation]
    correlation_regime: CorrelationRegime
    recommended_position_count_rationale: str
    as_of_date: str


# ── Shared Context passed down the chain ─────────────────────────────────────


class Context(BaseModel):
    """Shared state object. Each agent reads upstream outputs and appends its own."""

    model_config = {"arbitrary_types_allowed": True}

    run_id: str
    demo_mode: bool = False
    tickers: list[str] = Field(default_factory=list)
    as_of_date: str

    # Populated sequentially by each agent
    economy: Optional[EconomyData] = None
    cycle: Optional[CycleData] = None
    scenarios: Optional[ScenariosData] = None
    sectors: Optional[SectorData] = None
    styles: Optional[StyleData] = None
    screen: Optional[ScreenData] = None
    fundamentals: Optional[dict[str, FundamentalData]] = None
    valuations: Optional[dict[str, ValuationData]] = None
    risk: Optional[RiskData] = None
    recommendations: Optional[RecommendationsData] = None


# ── AgentOutput — every agent writes one of these ────────────────────────────


class AgentOutput(BaseModel):
    agent_name: str
    run_id: str
    as_of_date: str
    confidence: float = Field(ge=0.0, le=100.0)
    confidence_label: ConfidenceLabel
    rationale: str
    data: Any
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)

    def persist(self, output_dir: Path = OUTPUT_DIR) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.agent_name}.json"
        path.write_text(self.model_dump_json(indent=2))
        return path

    @classmethod
    def load(cls, agent_name: str, output_dir: Path = OUTPUT_DIR) -> "AgentOutput":
        path = output_dir / f"{agent_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"No cached output for agent '{agent_name}' at {path}")
        return cls.model_validate_json(path.read_text())


# ── Agent ABC ─────────────────────────────────────────────────────────────────


class Agent(ABC):
    """Abstract base class for all pipeline agents."""

    name: str  # must match the filename slug, e.g. "economy"

    @abstractmethod
    def run(self, context: Context) -> AgentOutput:
        """Execute analysis; return structured AgentOutput and mutate context."""
        ...

    @staticmethod
    def _confidence_label(score: float) -> ConfidenceLabel:
        if score >= 75:
            return ConfidenceLabel.HIGH
        if score >= 51:
            return ConfidenceLabel.MEDIUM
        return ConfidenceLabel.LOW

    def _load_demo_output(self, output_dir: Path = OUTPUT_DIR) -> Optional[AgentOutput]:
        """Return cached demo output if it exists, else None."""
        try:
            return AgentOutput.load(self.name, output_dir)
        except FileNotFoundError:
            return None

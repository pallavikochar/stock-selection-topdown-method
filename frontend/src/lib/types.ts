// Mirror of backend Pydantic schemas — kept in sync with apm/core/agent.py

export type Direction = "rising" | "falling" | "stable";
export type GrowthLevel = "above_trend" | "below_trend";
export type InflationLevel = "low" | "moderate" | "elevated" | "high";
export type ClockPhase = "REFLATION" | "INFLATION" | "STAGFLATION" | "DEFLATION" | "UNKNOWN";
export type MarketCyclePhase = "Trough" | "Recovery" | "Expansion" | "Quality" | "Growth_Slowdown";
export type HopeStage = "Housing" | "Orders" | "Profits" | "Employment" | "Unknown";
export type ConfidenceLabel = "Low" | "Medium" | "High";
export type Favorability = "strongly_favored" | "favored" | "neutral" | "unfavored" | "strongly_unfavored";
export type Action = "Buy" | "Hold" | "Replace" | "Avoid";
export type CorrelationRegime = "High" | "Low";

export interface EconomyData {
  growth_level: GrowthLevel;
  growth_direction: Direction;
  inflation_level: InflationLevel;
  inflation_direction: Direction;
  cmi_score: number;
  cmi_direction: Direction;
  lei_trajectory: string;
  cost_of_money_read: string;
  cost_of_goods_read: string;
  pmi_read: number;
  pmi_direction: Direction;
  yield_curve_bps: number;
  phase_readiness_confidence: number;
}

export interface CycleData {
  clock_phase: ClockPhase;
  market_cycle_phase: MarketCyclePhase;
  hope_stage: HopeStage;
  hope_next_stage: HopeStage;
  hope_inflecting_indicators: string[];
  rotation_direction: string;
  phase_fit_confidence: number;
}

export interface ScenarioMacro {
  gdp_growth_pct: number;
  revenue_growth_pct: number;
  cpi_pct: number;
  fed_funds_pct: number;
  ten_year_yield_pct: number;
  margin_trajectory: string;
  market_multiple_path: string;
  earnings_growth_pct: number;
  credit_spread_direction: string;
  oil_direction: string;
  pmi_direction: string;
}

export interface Scenario {
  name: string;
  label: string;
  probability: number;
  macro: ScenarioMacro;
}

export interface SectorScore {
  sector: string;
  favorability: Favorability;
  score: number;
  primary_macro_driver: string;
  supporting_drivers: string[];
  correlation_alignment: Record<string, number>;
}

export interface ScenarioValuation {
  scenario_name: string;
  probability: number;
  revenue_growth_pct: number;
  ebit_margin_pct: number;
  wacc_pct: number;
  terminal_growth_pct: number;
  dcf_value: number;
  multiples_value: number;
  blended_value: number;
  upside_pct: number;
}

export interface ConfidenceBreakdown {
  macro_cycle_conviction: number;
  sector_fit: number;
  style_factor_fit: number;
  reward_to_risk: number;
  fundamental_quality: number;
  cross_sectional_valuation: number;
  technical_catalyst: number;
  stock_picking_regime: number;
  no_downside_scenario_penalty: number;
  crowding_penalty: number;
  terminal_g_warning_penalty: number;
  theme_not_universal_penalty: number;
}

export interface StockRecommendation {
  ticker: string;
  action: Action;
  current_price: number;
  prob_weighted_target: number;
  expected_return_pct: number;
  reward_to_risk: number;
  confidence_numeric: number;
  confidence_label: ConfidenceLabel;
  confidence_breakdown: ConfidenceBreakdown;
  replaces_ticker: string | null;
  thesis: string;
  scenario_table: ScenarioValuation[];
  warnings: string[];
}

export interface AgentOutput<T = unknown> {
  agent_name: string;
  run_id: string;
  as_of_date: string;
  confidence: number;
  confidence_label: ConfidenceLabel;
  rationale: string;
  data: T;
  warnings: string[];
  provenance: Record<string, string>;
}

export interface FunnelSummary {
  funnel: Record<string, {
    confidence: number;
    confidence_label: ConfidenceLabel;
    rationale: string;
    warnings: string[];
  }>;
  as_of_date: string | null;
}

export interface RecommendationsData {
  ranked: StockRecommendation[];
  correlation_regime: CorrelationRegime;
  recommended_position_count_rationale: string;
  as_of_date: string;
}

export type Grounding = "GROUNDED" | "INFERRED" | "SPECULATIVE";
export type Sentiment = "BULLISH" | "NEUTRAL" | "BEARISH";

export interface VerifiedClaim {
  claim: string;
  grounding: Grounding;
  evidence: string;
  confidence: number;
}

export interface LLMStockAnalysis {
  ticker: string;
  tailwinds: VerifiedClaim[];
  headwinds: VerifiedClaim[];
  net_sentiment: Sentiment;
  sentiment_rationale: string;
  grounding_score: number;
}

export interface LLMAnalysisData {
  analyses: Record<string, LLMStockAnalysis>;
  model_used: string;
  verification_method: string;
}

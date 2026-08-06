// Mirror of backend Pydantic schemas — kept in sync with apm/core/agent.py

export type Direction = "rising" | "falling" | "stable";
export type GrowthLevel = "above_trend" | "below_trend";
export type InflationLevel = "low" | "moderate" | "elevated" | "high";
export type ClockPhase = "REFLATION" | "INFLATION" | "STAGFLATION" | "DEFLATION" | "UNKNOWN";
export type MarketCyclePhase = "Trough" | "Recovery" | "Expansion" | "Quality" | "Growth_Slowdown";
export type HopeStage = "Housing" | "Orders" | "Profits" | "Employment" | "Unknown";
export type ConfidenceLabel = "Low" | "Medium" | "High";
export type Favorability = "strongly_favored" | "favored" | "neutral" | "unfavored" | "strongly_unfavored";
export type Action = "Buy" | "Hold" | "Sell";
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
  renormalization_factor?: number;
}

export interface StockRecommendation {
  ticker: string;
  action: Action;
  current_price: number;
  prob_weighted_target: number;
  expected_return_pct: number;
  reward_to_risk: number;
  conviction_score: number;
  conviction_label: ConfidenceLabel;
  conviction_breakdown: ConfidenceBreakdown;
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

// ── Analyst (a13) ──────────────────────────────────────────────────────────
export interface AnalystConsensus {
  ticker: string;
  consensus: string;
  mean_target: number | null;
  high_target: number | null;
  low_target: number | null;
  num_analysts: number;
  buy_count: number;
  hold_count: number;
  sell_count: number;
  upside_to_mean_pct: number | null;
}

// ── SEC Filings (a14) ───────────────────────────────────────────────────────
export interface AnnualFinancials {
  year: number;
  revenue: number | null;
  gross_profit: number | null;
  operating_income: number | null;
  net_income: number | null;
  operating_cf: number | null;
  capex: number | null;
  free_cash_flow: number | null;
  eps_basic: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
}

export interface SECFilingsData {
  ticker: string;
  annual: AnnualFinancials[];
  revenue_cagr_3yr_pct: number | null;
  fcf_yield_pct: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  return_on_equity_pct: number | null;
  latest_10k_period: string | null;
  latest_10q_period: string | null;
}

// ── Backtest (a15) ──────────────────────────────────────────────────────────
export interface AnnualReturn {
  year: number;
  strategy_pct: number;
  benchmark_pct: number;
  excess_pct: number;
  regime: string;
}

export interface BacktestMetrics {
  cagr_pct: number;
  benchmark_cagr_pct: number;
  alpha_pct: number;
  beta: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  calmar_ratio: number;
  win_rate_pct: number;
  backtest_start: string;
  backtest_end: string;
  total_months: number;
  outperformance_months: number;
}

export interface BacktestData {
  strategy_name: string;
  metrics: BacktestMetrics;
  annual_returns: AnnualReturn[];
  top_contributors: string[];
  worst_contributors: string[];
  methodology: string;
}

// ── Single-ticker analysis ─────────────────────────────────────────────────
export interface TickerAnalysis {
  ticker: string;
  as_of_date: string;
  recommendation: StockRecommendation | null;
  valuation: {
    current_price: number;
    prob_weighted_target: number;
    expected_return_pct: number;
    reward_to_risk: number;
    scenario_valuations: ScenarioValuation[];
  } | null;
  fundamental: {
    industry_life_cycle: string;
    business_model_type: string;
    narrative_quality: string;
    key_risks: string[];
    qualitative_score: number;
    porter: PorterForces;
  } | null;
}

// ── LLM Analysis (a12) ─────────────────────────────────────────────────────
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

// ── Fundamental / Porter (a07) ────────────────────────────────────────────
export interface PorterForces {
  threat_of_entry: number;
  threat_of_substitutes: number;
  buyer_power: number;
  supplier_power: number;
  competitive_rivalry: number;
  market_share_outlook: string;
  margin_outlook: string;
  overall_score: number;
}

export interface FundamentalProfile {
  ticker: string;
  industry_life_cycle: string;
  business_model_type: string;
  narrative_quality: string;
  porter: PorterForces;
  revenue_growth_driver: string;
  margin_driver: string;
  reinvestment_efficiency: string;
  key_risks: string[];
  qualitative_score: number;
}

// ── Style & Factor (a05) ───────────────────────────────────────────────────
export interface StyleFactor {
  factor_name: string;
  classification: string;
  rationale: string;
  weight: number;
  cross_universe_holds: boolean;
}

export interface StyleData {
  favored_factors: StyleFactor[];
  avoid_factors: string[];
  favored_size_style_box: string;
  value_vs_growth_read: string;
  dividend_yield_warning: string;
  phase: string;
}

// ── RAG ────────────────────────────────────────────────────────────────────
export type ScoreLabel = "high" | "medium" | "low";

export interface RagSource {
  text: string;
  ticker: string | null;
  doc_type: string;
  period: string | null;
  score: number;
  citation: string;
  score_label: ScoreLabel;
}

export interface RagQueryResult {
  answer: string;
  sources: RagSource[];
  query: string;
  avg_score: number;
}

export interface RagCollectionStats {
  name: string;
  doc_count: number;
  tickers: string[];
}

export interface RagCollectionsResponse {
  collections: RagCollectionStats[];
}

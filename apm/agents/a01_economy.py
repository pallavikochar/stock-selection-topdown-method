"""
Agent 1 — EconomyAgent
Produces a growth + inflation read and LEI forecast.
Implements the Piper Sandler Cost-of-Money / Cost-of-Goods lead-lag framework
and builds a Composite Macro Indicator (CMI) across Growth, Liquidity, Inflation, Sentiment.
"""

from __future__ import annotations

import logging

from apm.core.agent import Agent, AgentOutput, Context, EconomyData
from apm.core.types import ConfidenceLabel, Direction, GrowthLevel, InflationLevel
from apm.data.fetchers import get_macro_snapshot
from apm.utils.config import get_economic_view

log = logging.getLogger(__name__)


class EconomyAgent(Agent):
    name = "economy"

    def run(self, context: Context) -> AgentOutput:
        if context.demo_mode:
            return self._run_demo(context)
        return self._run_live(context)

    # ── Demo mode ─────────────────────────────────────────────────────────────

    def _run_demo(self, context: Context) -> AgentOutput:
        snap = get_macro_snapshot()
        return self._build_output(snap, context.run_id, context.as_of_date)

    # ── Live mode ─────────────────────────────────────────────────────────────

    def _run_live(self, context: Context) -> AgentOutput:
        cfg = get_economic_view()
        snap = {
            "growth_level": cfg["growth"]["level"],
            "growth_direction": cfg["growth"]["direction"],
            "inflation_level": cfg["inflation"]["level"],
            "inflation_direction": cfg["inflation"]["direction"],
            "ism_new_orders": cfg["leading_indicators"]["ism_new_orders"],
            "ism_prices_paid": cfg["leading_indicators"]["ism_prices_paid"],
            "yield_curve_2s10s_bps": cfg["leading_indicators"]["yield_curve_2s10s_bps"],
            "conference_board_lei_yoy_pct": cfg["leading_indicators"]["conference_board_lei_yoy_pct"],
            "michigan_sentiment": cfg["leading_indicators"]["michigan_sentiment"],
            "ten_year_yield_pct": cfg["market"]["ten_year_yield_pct"],
            "fed_funds_pct": cfg["market"]["fed_funds_pct"],
            "wti_crude_usd": cfg["market"]["wti_crude_usd"],
            "baa_credit_spread_pct": cfg["market"]["baa_credit_spread_pct"],
            "vix": cfg["market"]["vix"],
            "cmi_score": None,
            "cmi_direction": None,
        }
        snap["cmi_score"], snap["cmi_direction"] = self._compute_cmi(snap)
        return self._build_output(snap, context.run_id, context.as_of_date)

    # ── Core logic ────────────────────────────────────────────────────────────

    def _build_output(self, snap: dict, run_id: str, as_of_date: str) -> AgentOutput:
        growth_level = GrowthLevel(snap.get("growth_level", "above_trend"))
        growth_direction = Direction(snap.get("growth_direction", "falling"))
        inflation_level = InflationLevel(snap.get("inflation_level", "elevated"))
        inflation_direction = Direction(snap.get("inflation_direction", "rising"))

        pmi = snap.get("ism_new_orders")
        if pmi is None:
            raise RuntimeError(
                "ism_new_orders (PMI) is required but missing from macro snapshot. "
                "Set FRED_API_KEY for live data or populate config/economic_view.yaml. "
                "A 50.0 default sits exactly on the expansion/contraction discontinuity "
                "and makes clock-phase assignment meaningless."
            )
        pmi_dir = Direction.FALLING if pmi < 50 else Direction.RISING
        cmi = snap.get("cmi_score") or self._compute_cmi(snap)[0]
        cmi_dir_raw = snap.get("cmi_direction", "falling")
        cmi_dir = Direction(cmi_dir_raw) if cmi_dir_raw else Direction.FALLING

        # Cost of money: 10yr yield + fed funds + yield curve
        _DEFAULTS = {"ten_year_yield_pct": 4.65, "fed_funds_pct": 5.25,
                     "yield_curve_2s10s_bps": -15, "wti_crude_usd": 78.0,
                     "ism_prices_paid": 55.0, "conference_board_lei_yoy_pct": -2.1}
        data_gaps = [k for k, v in _DEFAULTS.items() if snap.get(k) is None]
        if data_gaps:
            log.warning("a01_economy: substituting hardcoded defaults for missing keys: %s", data_gaps)
        ten_yr = snap.get("ten_year_yield_pct") if snap.get("ten_year_yield_pct") is not None else 4.65
        fed = snap.get("fed_funds_pct") if snap.get("fed_funds_pct") is not None else 5.25
        yc = snap.get("yield_curve_2s10s_bps") if snap.get("yield_curve_2s10s_bps") is not None else -15
        if ten_yr > 4.0 or fed > 4.0:
            cost_of_money = "tight — weighing on multiples and credit"
        elif ten_yr < 2.5:
            cost_of_money = "loose — accommodative for risk assets"
        else:
            cost_of_money = "neutral"

        # Cost of goods: oil + prices paid
        wti = snap.get("wti_crude_usd") if snap.get("wti_crude_usd") is not None else 78.0
        pp = snap.get("ism_prices_paid") if snap.get("ism_prices_paid") is not None else 55.0
        if wti > 90 or pp > 60:
            cost_of_goods = "elevated — margin pressure for non-energy sectors"
        elif wti < 60 and pp < 45:
            cost_of_goods = "falling — relief for margins"
        else:
            cost_of_goods = "moderate"

        # LEI trajectory
        lei_yoy = snap.get("conference_board_lei_yoy_pct") if snap.get("conference_board_lei_yoy_pct") is not None else -2.1
        if lei_yoy < -1.5:
            lei_trajectory = f"contracting (CB LEI {lei_yoy:+.1f}% YoY) — recessionary signal in 6–12 months"
        elif lei_yoy < 0:
            lei_trajectory = f"slowing ({lei_yoy:+.1f}% YoY) — growth deceleration ahead"
        else:
            lei_trajectory = f"expanding ({lei_yoy:+.1f}% YoY)"

        # Confidence: how cleanly the indicators agree
        confidence = self._compute_confidence(snap)

        data = EconomyData(
            growth_level=growth_level,
            growth_direction=growth_direction,
            inflation_level=inflation_level,
            inflation_direction=inflation_direction,
            cmi_score=round(cmi, 1),
            cmi_direction=cmi_dir,
            lei_trajectory=lei_trajectory,
            cost_of_money_read=cost_of_money,
            cost_of_goods_read=cost_of_goods,
            pmi_read=pmi,
            pmi_direction=pmi_dir,
            yield_curve_bps=yc,
            phase_readiness_confidence=confidence,
        )

        context_str = (
            f"Growth: {growth_level.value} & {growth_direction.value} | "
            f"Inflation: {inflation_level.value} & {inflation_direction.value} | "
            f"PMI={pmi:.1f} | CMI={cmi:.1f} {cmi_dir.value} | "
            f"Cost of Money: {cost_of_money} | Cost of Goods: {cost_of_goods} | "
            f"LEI: {lei_trajectory}"
        )

        from apm.agents.a16_research import _rag_context
        rag = _rag_context(
            "What is the Fed's current stance on interest rates and forward guidance?",
            doc_type="fed_minutes",
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=run_id,
            as_of_date=as_of_date,
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=context_str,
            data=data.model_dump(),
            warnings=self._build_warnings(snap),
            provenance={
                "pmi_source": "ISM / config/economic_view.yaml",
                "lei_source": "Conference Board / FRED",
                "cmi_methodology": "z-score diffusion across Growth(30%), Liquidity(25%), Inflation(25%), Sentiment(20%)",
                **({"rag_fed_context": rag} if rag else {}),
            },
        )

    def _compute_cmi(self, snap: dict) -> tuple[float, str]:
        """
        Composite Macro Indicator: z-score-normalised diffusion across 4 groups.
        TUNABLE: Group weights are in provenance; change here if methodology shifts.
        Returns (score 0-100, direction "rising"|"falling").
        """
        pmi = snap.get("ism_new_orders")
        if pmi is None:
            raise RuntimeError("ism_new_orders (PMI) missing from macro snapshot")
        lei_yoy = snap.get("conference_board_lei_yoy_pct", 0.0)
        sentiment = snap.get("michigan_sentiment", 70.0)
        baa = snap.get("baa_credit_spread_pct", 1.5)
        ten_yr = snap.get("ten_year_yield_pct", 4.5)
        vix = snap.get("vix", 18.0)
        prices_paid = snap.get("ism_prices_paid", 55.0)

        # Normalise each to 0–100 scale (higher = more expansionary)
        growth_score = max(0, min(100, (pmi - 35) / (65 - 35) * 100))
        lei_score = max(0, min(100, (lei_yoy + 10) / 20 * 100))
        liquidity_score = max(0, min(100, (1.0 - (baa - 0.5) / 5.0) * 100))  # tighter spreads = higher
        rate_score = max(0, min(100, (1.0 - (ten_yr - 1.0) / 6.0) * 100))    # lower rates = higher
        sentiment_score = max(0, min(100, (sentiment - 40) / (110 - 40) * 100))
        vix_score = max(0, min(100, (1.0 - (vix - 10) / 50.0) * 100))         # lower VIX = higher
        inflation_score = max(0, min(100, (1.0 - (prices_paid - 40) / 50.0) * 100))  # lower PP = higher

        # Weighted composite: Growth 30%, Liquidity 25%, Inflation 25%, Sentiment 20%
        composite = (
            0.30 * ((growth_score + lei_score) / 2)
            + 0.25 * ((liquidity_score + rate_score) / 2)
            + 0.25 * inflation_score
            + 0.20 * ((sentiment_score + vix_score) / 2)
        )
        direction = "rising" if composite > 50 else "falling"
        return round(composite, 1), direction

    def _compute_confidence(self, snap: dict) -> float:
        """How clearly do LEIs, PMI, LEI, sentiment, spreads all agree?"""
        signals = []
        pmi = snap.get("ism_new_orders")
        if pmi is None:
            raise RuntimeError("ism_new_orders (PMI) missing from macro snapshot")
        signals.append(1 if pmi < 50 else -1)  # expect contraction given stage
        lei_yoy = snap.get("conference_board_lei_yoy_pct", 0.0)
        signals.append(1 if lei_yoy < 0 else -1)
        cmi = snap.get("cmi_score")
        if cmi:
            signals.append(1 if cmi < 50 else -1)
        agreement = abs(sum(signals)) / len(signals)  # 0 = split, 1 = unanimous
        return round(50 + agreement * 40, 1)  # 50–90 range

    def _build_warnings(self, snap: dict) -> list[str]:
        warnings = []
        pmi = snap.get("ism_new_orders")
        if pmi is None:
            raise RuntimeError("ism_new_orders (PMI) missing from macro snapshot")
        prices_paid = snap.get("ism_prices_paid", 55.0)
        if pmi < 50 and prices_paid > 55:
            warnings.append("Stagflationary signal: PMI contracting while Prices Paid elevated")
        yc = snap.get("yield_curve_2s10s_bps", 0)
        if yc < -50:
            warnings.append(f"Yield curve deeply inverted ({yc}bps) — recession probability elevated in 12–18m")
        return warnings

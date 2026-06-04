"""
Sector-specific ratio analysis — Wall Street practitioner conventions.
Each sector has primary valuation multiples and quality ratios analysts actually use.
Provides sector-aware quality scoring and a third valuation leg beyond DCF + P/E.
"""

from __future__ import annotations

from typing import Any

from apm.utils.config import get_valuation_assumptions


def _va() -> dict:
    return get_valuation_assumptions()


# ── Sector quality scoring ────────────────────────────────────────────────────


def sector_quality_score(raw_fund: dict[str, Any], sector: str, life_cycle: str) -> float:
    """
    0–100 quality score using sector-appropriate ratios.
    Called from FundamentalAgent; replaces the generic ROE/ROIC formula
    for the ratio component of qualitative_score (porter is blended in by the caller).
    """
    sk = sector.replace(" ", "_")
    roe            = raw_fund.get("roe") or 0
    roa            = raw_fund.get("roa") or 0
    gross_margin   = raw_fund.get("gross_margin") or 0
    op_margin      = raw_fund.get("operating_margin") or 0
    net_margin     = raw_fund.get("net_margin") or 0
    rev_growth     = raw_fund.get("revenue_growth_yoy") or 0
    de             = raw_fund.get("debt_to_equity") or 0
    price_to_book  = raw_fund.get("price_to_book") or 0
    payout         = raw_fund.get("payout_ratio") or 0
    div_yield      = raw_fund.get("dividend_yield") or 0
    market_cap     = raw_fund.get("market_cap") or 1e10
    fcf            = raw_fund.get("free_cash_flow") or 0
    revenue        = raw_fund.get("revenue_ttm") or 1e9

    # dividendYield from yfinance is returned as percentage (e.g. 2.91 = 2.91%); normalize to decimal
    div_yield = _norm_ratio(div_yield)

    score = 0.0

    if sk == "Financials":
        # ROE is the primary franchise-quality metric for banks
        score += _sr(roe,   [(0.18, 35), (0.15, 28), (0.12, 18), (0.10, 10), (0, 0)])
        # P/B vs Gordon-fair-value P/B: fair P/B = ROE / COE (COE ≈ 10%)
        fair_pb = roe / 0.10 if roe > 0 else 1.0
        pb_rel = price_to_book / fair_pb if (fair_pb and price_to_book) else 1.5
        score += _sr(1.0 / max(pb_rel, 0.1),
                     [(1.4, 22), (1.1, 16), (0.9, 10), (0.7, 4), (0, 0)])
        # ROA: profitability per dollar of assets (1%+ is strong for banks)
        score += _sr(roa,   [(0.015, 15), (0.012, 12), (0.010, 8), (0.008, 4), (0, 0)])
        # Net margin as earnings quality
        score += _sr(net_margin, [(0.30, 8), (0.20, 5), (0.10, 2), (0, 0)])

    elif sk == "Technology":
        # Gross margin signals asset-light moat (software premium)
        score += _sr(gross_margin, [(0.75, 30), (0.65, 24), (0.50, 15), (0.35, 7), (0, 0)])
        # Revenue growth = TAM capture / product-market fit
        score += _sr(rev_growth,   [(0.25, 25), (0.15, 18), (0.10, 12), (0.05, 5), (0, 0)])
        # Operating leverage
        score += _sr(op_margin,    [(0.30, 20), (0.20, 14), (0.10, 7), (0, 0)])
        # Rule of 40 (rev growth + op margin); SaaS benchmark ≥ 40%
        r40 = rev_growth + op_margin
        score += _sr(r40,          [(0.60, 15), (0.40, 10), (0.20, 5), (0, 0)])

    elif sk == "Health_Care":
        # Gross margin: patent-protected drugs command 80%+ margins
        score += _sr(gross_margin, [(0.75, 30), (0.65, 22), (0.50, 12), (0.35, 5), (0, 0)])
        # Operating margin after R&D investment
        score += _sr(op_margin,    [(0.25, 25), (0.15, 18), (0.08, 10), (0, 0)])
        # Revenue growth: pipeline contribution
        score += _sr(rev_growth,   [(0.15, 20), (0.10, 14), (0.05, 7), (0, 2)])
        # FCF margin: cash available after pipeline investment
        fcf_margin = fcf / revenue
        score += _sr(fcf_margin,   [(0.20, 15), (0.10, 10), (0.05, 5), (0, 0)])

    elif sk in ("Energy", "Materials"):
        # FCF yield is the primary metric for commodity businesses
        fcf_yield = fcf / market_cap if market_cap else 0
        score += _sr(fcf_yield,    [(0.12, 35), (0.08, 25), (0.05, 15), (0.02, 7), (0, 0)])
        # Operating margin (production cost efficiency)
        score += _sr(op_margin,    [(0.25, 25), (0.15, 18), (0.08, 10), (0, 0)])
        # ROA (return on physical assets)
        score += _sr(roa,          [(0.12, 20), (0.08, 14), (0.05, 8), (0, 0)])
        # Dividend coverage (payout < 50% = well-covered)
        if payout > 0:
            score += _sr(1 - payout, [(0.70, 10), (0.50, 7), (0.30, 3), (0, 0)])

    elif sk in ("Utilities", "Real_Estate"):
        # Dividend yield: income investors' primary lens
        score += _sr(div_yield,    [(0.050, 30), (0.040, 22), (0.035, 14), (0.025, 7), (0, 0)])
        # Payout sustainability (regulated utilities: ≤ 85% is safe)
        if payout > 0:
            score += _sr(1 - payout, [(0.20, 25), (0.15, 18), (0.10, 10), (0, 0)])
        # Leverage guard (D/E over 200 = concern; negative = not penalised)
        if de > 0:
            de_score = max(0, 25 - max(0, (de - 150) / 150 * 25))
        else:
            de_score = 15  # unknown → neutral
        score += de_score
        # Rate-base / revenue growth
        score += _sr(rev_growth,   [(0.10, 10), (0.07, 7), (0.04, 4), (0, 0)])

    elif sk in ("Consumer_Discretionary", "Consumer_Staples"):
        # Gross margin: pricing power and brand moat
        score += _sr(gross_margin, [(0.55, 28), (0.45, 20), (0.35, 12), (0.25, 5), (0, 0)])
        score += _sr(op_margin,    [(0.20, 25), (0.15, 18), (0.08, 10), (0, 0)])
        score += _sr(rev_growth,   [(0.12, 20), (0.08, 14), (0.04, 8), (0, 2)])
        score += _sr(roe,          [(0.25, 15), (0.18, 10), (0.12, 5), (0, 0)])

    elif sk == "Industrials":
        # Operating margin = pricing discipline + aftermarket mix
        score += _sr(op_margin,    [(0.20, 30), (0.15, 22), (0.10, 14), (0.05, 7), (0, 0)])
        score += _sr(roe,          [(0.25, 25), (0.18, 18), (0.12, 10), (0, 0)])
        score += _sr(rev_growth,   [(0.12, 20), (0.08, 14), (0.04, 8), (0, 2)])
        fcf_margin = fcf / revenue
        score += _sr(fcf_margin,   [(0.12, 15), (0.08, 10), (0.04, 5), (0, 0)])

    elif sk == "Communication_Services":
        # Mix of telco (yield) and digital-ad (margin) — gross margin leads
        score += _sr(gross_margin, [(0.65, 28), (0.50, 20), (0.35, 12), (0.20, 5), (0, 0)])
        score += _sr(rev_growth,   [(0.12, 22), (0.08, 16), (0.04, 8), (0, 2)])
        score += _sr(op_margin,    [(0.25, 20), (0.15, 14), (0.08, 7), (0, 0)])
        fcf_yield = fcf / market_cap if market_cap else 0
        score += _sr(fcf_yield,    [(0.06, 20), (0.04, 14), (0.02, 7), (0, 0)])

    else:  # Generic fallback
        score += _sr(roe,          [(0.20, 30), (0.15, 22), (0.10, 12), (0, 0)])
        score += _sr(gross_margin, [(0.50, 25), (0.35, 18), (0.20, 10), (0, 0)])
        score += _sr(rev_growth,   [(0.12, 20), (0.08, 14), (0.04, 8), (0, 2)])
        score += _sr(op_margin,    [(0.15, 15), (0.10, 10), (0.05, 5), (0, 0)])

    return round(min(100.0, max(0.0, score)), 1)


def _sr(value: float, thresholds: list[tuple[float, float]]) -> float:
    """Score-range helper: return score for first threshold value meets or exceeds."""
    for threshold, score in thresholds:
        if value >= threshold:
            return score
    return 0.0


def _norm_ratio(value: float) -> float:
    """
    Normalize a ratio that may be stored as percentage (e.g. 3.5) or decimal (0.035).
    Heuristic: values > 0.30 are treated as percentage form for yield/margin/growth fields.
    Covers dividend yield, ROE, ROA, payout ratio, margins (all should be 0.0–0.30 in decimal).
    """
    return value / 100 if value > 0.30 else value


# ── Sector-specific third valuation leg ──────────────────────────────────────
# (All numeric constants below are loaded from config/valuation_assumptions.yaml)


def sector_third_valuation(
    raw_fund: dict[str, Any],
    sector: str,
    life_cycle: str,
    cost_of_equity: float,
    terminal_g: float,
    earnings_growth_pct: float,
) -> tuple[float, str]:
    """
    Return (per_share_value, method_label) for a sector-appropriate third valuation leg.
    Returns (0.0, "") if no sector-specific method applies (caller uses 2-leg blend).

    Methods:
      Financials              — Gordon Growth P/B
      Utilities / Real_Estate — Dividend Discount Model
      Energy / Materials      — EV/EBITDA
      Growth or Startup Tech  — EV/Sales
    """
    sk = sector.replace(" ", "_")
    shares      = raw_fund.get("shares_outstanding") or 1e9
    price       = raw_fund.get("current_price") or 0
    pb          = raw_fund.get("price_to_book") or 0
    roe         = raw_fund.get("roe") or 0
    div_yield   = raw_fund.get("dividend_yield") or 0
    payout      = raw_fund.get("payout_ratio") or 0
    net_income  = raw_fund.get("net_income_ttm") or 0
    market_cap  = raw_fund.get("market_cap") or 1e10
    debt        = raw_fund.get("total_debt") or 0
    cash        = raw_fund.get("cash") or 0
    ebit        = raw_fund.get("ebit_ttm") or 0
    revenue     = raw_fund.get("revenue_ttm") or 1e9

    if shares <= 0:
        return 0.0, ""

    # dividendYield from yfinance is returned as percentage (e.g. 2.91 = 2.91%); normalize to decimal
    div_yield = _norm_ratio(div_yield)

    # ── Gordon Growth P/B (Financials) ───────────────────────────────────────
    if sk == "Financials":
        if pb > 0 and price > 0 and roe > 0 and cost_of_equity > terminal_g:
            bv_per_share = price / pb
            intrinsic_pb = roe / (cost_of_equity - terminal_g)
            gordon_price = bv_per_share * intrinsic_pb
            return round(max(1.0, gordon_price), 2), "Gordon P/B"

    # ── Dividend Discount Model (Utilities, REITs) ───────────────────────────
    elif sk in ("Utilities", "Real_Estate"):
        if div_yield > 0 and price > 0:
            dps = div_yield * price
        elif payout > 0 and shares > 0:
            dps = (net_income * payout) / shares
        else:
            return 0.0, ""
        dps_next = dps * (1 + terminal_g)
        if cost_of_equity > terminal_g:
            ddm_price = dps_next / (cost_of_equity - terminal_g)
            return round(max(1.0, ddm_price), 2), "DDM"

    # ── EV/EBITDA (Energy, Materials) ────────────────────────────────────────
    elif sk in ("Energy", "Materials"):
        da_mult = _va()["third_leg"]["da_multipliers"].get(sk, 1.30)
        sector_multiple = _va()["third_leg"]["ev_ebitda_multiples"].get(sk, 9.0)
        # Scenario earnings growth scales the multiple ±40% pass-through
        growth_adj = 1.0 + (earnings_growth_pct / 100) * 0.40
        adj_multiple = max(5.0, sector_multiple * growth_adj)
        ebitda_est = ebit * da_mult if ebit > 0 else 0
        if ebitda_est > 0:
            target_ev = ebitda_est * adj_multiple
            equity_value = target_ev - debt + cash
            return round(max(1.0, equity_value / shares), 2), "EV/EBITDA"

    # ── EV/Sales (High-growth Tech / Comms) ──────────────────────────────────
    elif sk in ("Technology", "Communication_Services") and life_cycle in ("Growth", "Startup"):
        ev_sales_cfg = _va()["third_leg"]["ev_sales_multiples"]
        base_m = ev_sales_cfg.get(sk, {}).get(life_cycle, 6.0)
        # Rate compression: every 100bps above 8% COE reduces multiple ~8pts
        rate_adj = max(0.6, 1.0 - (cost_of_equity - 0.08) * 8)
        adj_multiple = base_m * rate_adj
        if revenue > 0:
            target_ev = revenue * adj_multiple
            equity_value = target_ev - debt + cash
            return round(max(1.0, equity_value / shares), 2), "EV/Sales"

    return 0.0, ""


def get_valuation_weights(sector_key: str, life_cycle: str, has_third_leg: bool) -> tuple[float, float, float]:
    """
    Return (dcf_weight, multiples_weight, third_leg_weight) summing to 1.0.
    All weights are read from config/valuation_assumptions.yaml → leg_weights.
    """
    lw = _va()["leg_weights"]
    two_leg = tuple(lw["default_2leg"])

    if not has_third_leg:
        return two_leg  # type: ignore[return-value]

    if sector_key in ("Technology", "Communication_Services") and life_cycle in ("Growth", "Startup"):
        return tuple(lw["tech_growth_3leg"])  # type: ignore[return-value]

    row = lw.get(sector_key)
    return tuple(row) if row else two_leg  # type: ignore[return-value]


# ── Sector-appropriate cross-sectional comparison ────────────────────────────
# (Peer medians are loaded from config/valuation_assumptions.yaml → peer_ev_ebitda_medians
#  and third_leg.gordon_pb.peer_pb_median_financials)


def sector_cross_sectional(
    raw_fund: dict[str, Any],
    sector: str,
) -> tuple[float, float, float]:
    """
    Return (stock_ratio, peer_median, discount_pct).
    discount_pct < 0 → cheaper than peers (positive signal).
    Uses P/B for Financials; EV/EBITDA for all other sectors.
    """
    sk = sector.replace(" ", "_")

    if sk == "Financials":
        pb = raw_fund.get("price_to_book") or 0
        median = _va()["third_leg"]["gordon_pb"]["peer_pb_median_financials"]
        discount = (pb - median) / median * 100 if (median and pb) else 0
        return round(pb, 2), median, round(discount, 1)

    # EV/EBITDA for all other sectors
    ev_ebitda = raw_fund.get("ev_ebitda") or 0
    if not ev_ebitda:
        ev = raw_fund.get("enterprise_value") or 0
        ebit = raw_fund.get("ebit_ttm") or 0
        ebitda_est = ebit * 1.25 if ebit else 0
        ev_ebitda = ev / ebitda_est if ebitda_est else 0

    median = _va()["peer_ev_ebitda_medians"].get(sk, 14.0)
    discount = (ev_ebitda - median) / median * 100 if (median and ev_ebitda) else 0
    return round(ev_ebitda, 1), median, round(discount, 1)

"""
Data fetchers with demo-cache fallbacks.
- In demo mode (or when API keys are absent), all functions return cached data.
- FRED key is read from env FRED_API_KEY; yfinance needs no key.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DEMO_CACHE_DIR = Path(__file__).parent / "demo_cache"
FRED_KEY = os.getenv("FRED_API_KEY", "")


# ── Demo cache helpers ────────────────────────────────────────────────────────


@lru_cache(maxsize=8)
def _load_demo_cache(filename: str) -> dict[str, Any]:
    path = DEMO_CACHE_DIR / filename
    return json.loads(path.read_text())


# ── FRED macro data ───────────────────────────────────────────────────────────


def fetch_fred_series(series_id: str, periods: int = 24) -> pd.Series:
    """Fetch a FRED time series; falls back to demo cache if no key."""
    if not FRED_KEY:
        cache = _load_demo_cache("macro.json")
        fred_data = cache.get("fred_series", {})
        if series_id in fred_data:
            raw = fred_data[series_id]
            return pd.Series(raw["values"], index=pd.to_datetime(raw["dates"]), name=series_id)
        return pd.Series([], name=series_id)
    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_KEY)
        return fred.get_series(series_id, observation_start=None).tail(periods)
    except Exception:
        cache = _load_demo_cache("macro.json")
        fred_data = cache.get("fred_series", {})
        if series_id in fred_data:
            raw = fred_data[series_id]
            return pd.Series(raw["values"], index=pd.to_datetime(raw["dates"]), name=series_id)
        return pd.Series([], name=series_id)


def get_macro_snapshot() -> dict[str, Any]:
    """Return latest macro readings; demo cache if no FRED key."""
    cache = _load_demo_cache("macro.json")
    return cache.get("snapshot", {})


# ── yfinance price & fundamental data ─────────────────────────────────────────


def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV price history; demo cache fallback."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period)
        if df.empty:
            raise ValueError("Empty")
        return df
    except Exception:
        cache = _load_demo_cache("prices.json")
        raw = cache.get(ticker, {})
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        df.index = pd.to_datetime(df.index if "date" not in df.columns else df["date"])
        return df


def fetch_fundamentals(ticker: str) -> dict[str, Any]:
    """Fetch key fundamental metrics; demo cache fallback."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return _normalize_fundamentals(info)
    except Exception:
        cache = _load_demo_cache("fundamentals.json")
        return cache.get(ticker, _empty_fundamentals(ticker))


# yfinance uses different sector names than GICS — normalize to GICS for consistency
_YFINANCE_SECTOR_MAP: dict[str, str] = {
    "Financial Services": "Financials",
    "Healthcare":         "Health Care",
    "Consumer Cyclical":  "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials":    "Materials",
    "Real Estate":        "Real Estate",
    "Communication Services": "Communication Services",
    "Technology":         "Technology",
    "Energy":             "Energy",
    "Industrials":        "Industrials",
    "Utilities":          "Utilities",
}


def _norm_pct_yield(value: float) -> float:
    """yfinance sometimes returns dividendYield as 2.91 (percent) vs 0.0291 (decimal)."""
    return value / 100 if value > 0.30 else value


def _normalize_fundamentals(info: dict) -> dict[str, Any]:
    raw_sector = info.get("sector", "")
    sector = _YFINANCE_SECTOR_MAP.get(raw_sector, raw_sector)
    # yfinance sometimes omits marketCap / sharesOutstanding for large caps;
    # floatShares is a reliable fallback
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    shares = (
        info.get("sharesOutstanding")
        or info.get("impliedSharesOutstanding")
        or info.get("floatShares")
        or 0
    )
    market_cap = info.get("marketCap") or (shares * price if shares and price else 0)
    return {
        "ticker": info.get("symbol", ""),
        "name": info.get("longName", ""),
        "sector": sector,
        "industry": info.get("industry", ""),
        "market_cap": market_cap,
        "enterprise_value": info.get("enterpriseValue", 0),
        "revenue_ttm": info.get("totalRevenue", 0),
        "ebit_ttm": info.get("ebit", 0),
        "net_income_ttm": info.get("netIncomeToCommon", 0),
        "free_cash_flow": info.get("freeCashflow", 0),
        "total_debt": info.get("totalDebt", 0),
        "cash": info.get("totalCash", 0),
        "shares_outstanding": shares,
        "beta": info.get("beta", 1.0),
        "pe_ttm": info.get("trailingPE"),
        "pe_fwd": info.get("forwardPE"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "price_to_book": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "roic": None,  # computed downstream
        "debt_to_equity": info.get("debtToEquity"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
        "dividend_yield": _norm_pct_yield(info.get("dividendYield", 0) or 0),
        "payout_ratio": info.get("payoutRatio", 0),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "net_margin": info.get("profitMargins"),
        "revenue_growth_yoy": info.get("revenueGrowth"),
        "earnings_growth_yoy": info.get("earningsGrowth"),
        "forward_eps": info.get("forwardEps"),
        "trailing_eps": info.get("trailingEps"),
        "analyst_target_price": info.get("targetMeanPrice"),
        "analyst_recommendation": info.get("recommendationKey", ""),
    }


def _empty_fundamentals(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker, "name": ticker, "sector": "", "industry": "",
        "market_cap": 0, "enterprise_value": 0, "revenue_ttm": 0, "ebit_ttm": 0,
        "net_income_ttm": 0, "free_cash_flow": 0, "total_debt": 0, "cash": 0,
        "shares_outstanding": 0, "beta": 1.0, "pe_ttm": None, "pe_fwd": None,
        "ev_ebitda": None, "price_to_book": None, "roe": None, "roa": None,
        "roic": None, "debt_to_equity": None, "current_price": 0,
        "dividend_yield": 0, "payout_ratio": 0, "gross_margin": None,
        "operating_margin": None, "net_margin": None, "revenue_growth_yoy": None,
        "earnings_growth_yoy": None, "forward_eps": None, "trailing_eps": None,
        "analyst_target_price": None,
        "analyst_recommendation": "",
    }


def compute_moving_averages(price_df: pd.DataFrame) -> dict[str, Optional[float]]:
    """Return latest 20-day and 200-day simple moving averages."""
    if price_df.empty or "Close" not in price_df.columns:
        return {"ma20": None, "ma200": None, "current": None}
    close = price_df["Close"]
    return {
        "ma20": close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None,
        "ma200": close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None,
        "current": close.iloc[-1],
    }


def compute_ebit_ev(fundamentals: dict[str, Any]) -> Optional[float]:
    ev = fundamentals.get("enterprise_value", 0)
    ebit = fundamentals.get("ebit_ttm", 0)
    if ev and ebit and ev > 0:
        return ebit / ev
    return None


def compute_ebit_tangible_assets(fundamentals: dict[str, Any]) -> Optional[float]:
    """EBIT / invested capital proxy — Greenblatt return on capital.
    Uses EV (market_cap + debt - cash) as invested capital approximation;
    closer to Greenblatt's net working capital + net fixed assets than
    market_cap alone, and moves in the correct direction for high-/low-P/B stocks.
    """
    ebit = fundamentals.get("ebit_ttm", 0)
    market_cap = fundamentals.get("market_cap", 0) or 0
    total_debt = fundamentals.get("total_debt", 0) or 0
    cash = fundamentals.get("cash", 0) or 0
    # EV proxy for invested capital: equity value + debt - excess cash
    invested_capital = max(market_cap + total_debt - cash, 1)
    return ebit / invested_capital if ebit else None

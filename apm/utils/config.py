"""YAML config loader with Pydantic validation."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path("config")


@lru_cache(maxsize=32)
def load_yaml(filename: str, config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    path = config_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh)


def get_economic_view() -> dict[str, Any]:
    return load_yaml("economic_view.yaml")


def get_scenarios() -> dict[str, Any]:
    return load_yaml("scenarios.yaml")


def get_sector_cyclicality() -> dict[str, Any]:
    return load_yaml("sector_cyclicality.yaml")


def get_sector_macro_corr() -> dict[str, Any]:
    return load_yaml("sector_macro_corr.yaml")


def get_phase_factor_leaders() -> dict[str, Any]:
    return load_yaml("phase_factor_leaders.yaml")


def get_factor_macro_corr() -> dict[str, Any]:
    return load_yaml("factor_macro_corr.yaml")


def get_size_style_cyclicality() -> dict[str, Any]:
    return load_yaml("size_style_cyclicality.yaml")


def get_hope_sequence() -> dict[str, Any]:
    return load_yaml("hope_sequence.yaml")


def get_holdings() -> dict[str, Any]:
    return load_yaml("holdings.yaml")


def get_universe() -> dict[str, Any]:
    return load_yaml("universe.yaml")


def get_weights() -> dict[str, Any]:
    return load_yaml("weights.yaml")


def get_valuation_defaults() -> dict[str, Any]:
    """Return valuation defaults from JSON sidecar; falls back to hardcoded values."""
    import json
    p = CONFIG_DIR / "valuation_defaults.json"
    base = {
        "terminal_g_startup": 3.0, "terminal_g_growth": 2.5,
        "terminal_g_mature": 2.0, "terminal_g_decline": 1.0,
        "equity_risk_premium": 5.5, "tax_rate_pct": 21.0,
        "dcf_weight": 0.45, "multiples_weight": 0.55,
        "bear_multiple_adj": 0.80, "bull_multiple_adj": 1.15,
        "buy_confidence_min": 60, "buy_return_min_pct": 3.0, "buy_rr_min": 1.5,
        "sell_confidence_max": 48, "sell_return_max_pct": 3.0, "hold_rr_min": 1.0,
    }
    if p.exists():
        try:
            saved = json.loads(p.read_text())
            base.update(saved)
        except Exception:
            pass
    return base


def get_industry_macro_beneficiaries() -> dict[str, Any]:
    return load_yaml("industry_macro_beneficiaries.yaml")


def all_tickers(universe: dict[str, Any] | None = None) -> list[str]:
    """Flatten the universe config into a list of tickers."""
    u = universe or get_universe()
    tickers = []
    for sector_data in u.get("sectors", {}).values():
        for t in sector_data.get("tickers", []):
            tickers.append(t["ticker"])
    return tickers


def ticker_to_sector(universe: dict[str, Any] | None = None) -> dict[str, str]:
    u = universe or get_universe()
    mapping: dict[str, str] = {}
    for sector_name, sector_data in u.get("sectors", {}).items():
        for t in sector_data.get("tickers", []):
            mapping[t["ticker"]] = sector_name
    return mapping

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

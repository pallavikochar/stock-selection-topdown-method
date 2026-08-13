"""
Shared Investment Clock phase → sector → ETF mapping.

Single source of truth used by:
  - BacktestAgent (a15): selects ETFs each month based on regime
  - SectorAgent (a04): reference for consistency checks

Sector preferences follow the Merrill Lynch / Piper Sandler Investment Clock:
  REFLATION   (growth recovering, inflation low):  early cyclicals
  INFLATION   (growth strong,    inflation rising): late cyclicals + real assets
  STAGFLATION (growth slowing,   inflation high):  defensives + energy
  DEFLATION   (growth falling,   inflation low):   pure defensives + quality growth
"""

from __future__ import annotations

from apm.core.types import ClockPhase

# Canonical sector name → SPDR Sector Select ETF ticker
SECTOR_TO_ETF: dict[str, str] = {
    "Energy":                  "XLE",
    "Materials":               "XLB",
    "Industrials":             "XLI",
    "Financials":              "XLF",
    "Consumer_Discretionary":  "XLY",
    "Consumer_Staples":        "XLP",
    "Health_Care":             "XLV",
    "Technology":              "XLK",
    "Communication_Services":  "XLC",
    "Utilities":               "XLU",
    "Real_Estate":             "XLRE",
}

# Phase → 4 favored sectors (equal-weight in backtest)
# Order within each list is informational only; all receive equal weight.
PHASE_FAVORED_SECTORS: dict[ClockPhase, list[str]] = {
    ClockPhase.REFLATION:   ["Financials", "Consumer_Discretionary", "Technology", "Industrials"],
    ClockPhase.INFLATION:   ["Energy", "Materials", "Industrials", "Financials"],
    ClockPhase.STAGFLATION: ["Energy", "Consumer_Staples", "Health_Care", "Utilities"],
    ClockPhase.DEFLATION:   ["Consumer_Staples", "Health_Care", "Utilities", "Technology"],
}


def phase_to_etfs(phase: ClockPhase) -> list[str]:
    """Return the 4 SPDR ETFs favored in the given clock phase."""
    return [SECTOR_TO_ETF[s] for s in PHASE_FAVORED_SECTORS[phase]]


def phase_to_sectors(phase: ClockPhase) -> list[str]:
    """Return the 4 favored sector names for the given clock phase."""
    return PHASE_FAVORED_SECTORS[phase]

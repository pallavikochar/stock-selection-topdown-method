"""Shared enumerations and simple value types used across all agents."""

from enum import Enum


class ClockPhase(str, Enum):
    REFLATION = "REFLATION"       # growth below trend & rising; inflation falling
    INFLATION = "INFLATION"       # growth above trend & rising; inflation rising
    STAGFLATION = "STAGFLATION"   # growth above trend & falling; inflation rising
    DEFLATION = "DEFLATION"       # growth below trend & falling; inflation falling
    UNKNOWN = "UNKNOWN"


class MarketCyclePhase(str, Enum):
    TROUGH = "Trough"
    RECOVERY = "Recovery"
    EXPANSION = "Expansion"
    QUALITY = "Quality"
    GROWTH_SLOWDOWN = "Growth_Slowdown"


class HopeStage(str, Enum):
    HOUSING = "Housing"
    ORDERS = "Orders"
    PROFITS = "Profits"
    EMPLOYMENT = "Employment"
    UNKNOWN = "Unknown"


class Direction(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"


class GrowthLevel(str, Enum):
    ABOVE_TREND = "above_trend"
    BELOW_TREND = "below_trend"


class InflationLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"


class Action(str, Enum):
    BUY = "Buy"
    HOLD = "Hold"
    REPLACE = "Replace"
    AVOID = "Avoid"


class ConfidenceLabel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class CorrelationRegime(str, Enum):
    HIGH = "High"     # stocks moving together → diversify, pick less
    LOW = "Low"       # differentiated → can concentrate


class LifeCycleStage(str, Enum):
    STARTUP = "Startup"
    GROWTH = "Growth"
    MATURE = "Mature"
    DECLINE = "Decline"


class MarketCap(str, Enum):
    LARGE = "large"
    MID = "mid"
    SMALL = "small"


class Favorability(str, Enum):
    STRONGLY_FAVORED = "strongly_favored"
    FAVORED = "favored"
    NEUTRAL = "neutral"
    UNFAVORED = "unfavored"
    STRONGLY_UNFAVORED = "strongly_unfavored"

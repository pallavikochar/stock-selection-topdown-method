"""
FastAPI application — serves agent outputs from output/agents/*.json.
The backend reads persisted artifacts; no logic is duplicated in the API layer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

OUTPUT_DIR = Path("output/agents")
FRONTEND_DIST = Path("frontend/dist")
CONFIG_DIR = Path("config")

# Load .env if present (safe no-op if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    import os
    _env = Path(".env")
    if _env.exists():
        for line in _env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

app = FastAPI(
    title="Project APM",
    description="Multi-agent top-down quantamental stock recommendation engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_NAMES = [
    "economy", "cycle", "scenario", "sector", "style",
    "screen", "fundamental", "valuation", "risk_correlation",
    "recommendations", "report", "llm_analysis",
    "analyst", "sec_filings", "backtest",
]

MACRO_CACHE = Path("apm/data/demo_cache/macro.json")
ECON_CONFIG = Path("config/economic_view.yaml")


def _read_agent_output(agent_name: str) -> dict[str, Any]:
    path = OUTPUT_DIR / f"{agent_name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' has not been run yet")
    return json.loads(path.read_text())


@app.get("/api/agents/{agent_name}")
async def get_agent_output(agent_name: str) -> dict[str, Any]:
    """Return the persisted output for a specific agent."""
    if agent_name not in AGENT_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")
    return _read_agent_output(agent_name)


@app.get("/api/agents")
async def list_agents() -> dict[str, Any]:
    """Return status of all agents (run / not-run)."""
    status = {}
    for name in AGENT_NAMES:
        path = OUTPUT_DIR / f"{name}.json"
        status[name] = {
            "run": path.exists(),
            "modified": path.stat().st_mtime if path.exists() else None,
        }
    return {"agents": status}


@app.get("/api/recommendations")
async def get_recommendations() -> dict[str, Any]:
    """Return the final recommendations output directly."""
    return _read_agent_output("recommendations")


@app.get("/api/funnel")
async def get_funnel_summary() -> dict[str, Any]:
    """Return a condensed summary of each funnel layer for the landing view."""
    summary: dict[str, Any] = {}
    for name in AGENT_NAMES:
        path = OUTPUT_DIR / f"{name}.json"
        if path.exists():
            raw = json.loads(path.read_text())
            summary[name] = {
                "confidence": raw.get("confidence"),
                "confidence_label": raw.get("confidence_label"),
                "rationale": raw.get("rationale", "")[:200],
                "warnings": raw.get("warnings", [])[:3],
            }
    return {"funnel": summary, "as_of_date": _get_run_date()}


@app.get("/api/config/economy")
async def get_economy_config() -> dict[str, Any]:
    """Return current macro snapshot for the economy panel."""
    if not MACRO_CACHE.exists():
        raise HTTPException(404, "Macro cache not found")
    raw = json.loads(MACRO_CACHE.read_text())
    snap = raw.get("snapshot", {})
    import yaml
    cfg = yaml.safe_load(ECON_CONFIG.read_text()) if ECON_CONFIG.exists() else {}
    regime_override = cfg.get("overrides", {}).get("force_clock_phase")
    return {"snapshot": snap, "regime_override": regime_override}


@app.post("/api/config/economy")
async def update_economy_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Update macro snapshot variables and/or regime override, then return updated state."""
    if not MACRO_CACHE.exists():
        raise HTTPException(404, "Macro cache not found")

    raw = json.loads(MACRO_CACHE.read_text())
    snap = raw.get("snapshot", {})

    FIELD_MAP = {
        "pmi": "ism_manufacturing", "cpi": "cpi_pct",
        "fed_funds": "fed_funds_pct", "ten_year_yield": "ten_year_yield_pct",
        "yield_curve": "yield_curve_2s10s_bps", "baa_spread": "baa_credit_spread_pct",
        "vix": "vix", "nahb": "nahb_index", "wti_crude": "wti_crude_usd",
        "dxy": "dxy", "initial_claims": "initial_claims_k",
        "ism_new_orders": "ism_new_orders", "unemployment": "unemployment_rate_pct",
        "nfp": "nonfarm_payrolls_mom_k",
    }
    updated: list[str] = []
    for frontend_key, cache_key in FIELD_MAP.items():
        if frontend_key in payload:
            snap[cache_key] = float(payload[frontend_key])
            updated.append(frontend_key)

    raw["snapshot"] = snap
    MACRO_CACHE.write_text(json.dumps(raw, indent=2))

    # Regime override — write to economic_view.yaml overrides
    if "regime_override" in payload:
        import yaml
        cfg: dict = {}
        if ECON_CONFIG.exists():
            cfg = yaml.safe_load(ECON_CONFIG.read_text()) or {}
        cfg.setdefault("overrides", {})
        regime = payload["regime_override"]
        if regime and regime != "AUTO":
            cfg["overrides"]["force_clock_phase"] = regime
        else:
            cfg["overrides"].pop("force_clock_phase", None)
        ECON_CONFIG.write_text(yaml.dump(cfg, default_flow_style=False))
        updated.append("regime_override")

    return {"status": "ok", "updated": updated}


_run_state: dict = {"running": False, "started_at": None, "finished_at": None, "error": None}
_backtest_state: dict = {"running": False, "started_at": None, "finished_at": None, "error": None}


@app.get("/api/run/status")
async def run_status() -> dict:
    """Return whether a pipeline run is in progress."""
    return _run_state


@app.post("/api/run")
async def trigger_run(
    background_tasks: BackgroundTasks,
    demo: bool = True,
) -> dict[str, str]:
    """Trigger a full pipeline run in the background."""
    if _run_state["running"]:
        return {"status": "already_running", "demo": str(demo)}
    background_tasks.add_task(_run_pipeline, demo)
    return {"status": "started", "demo": str(demo)}


@app.get("/api/run/backtest/status")
async def backtest_run_status() -> dict:
    """Return whether a backtest-only run is in progress."""
    return _backtest_state


@app.post("/api/run/backtest")
async def trigger_backtest(
    background_tasks: BackgroundTasks,
    demo: bool = True,
) -> dict[str, str]:
    """Trigger backtest agent only in the background."""
    if _backtest_state["running"] or _run_state["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(_run_backtest, demo)
    return {"status": "started"}


async def _run_pipeline(demo: bool) -> None:
    import sys, datetime
    _run_state["running"] = True
    _run_state["started_at"] = datetime.datetime.utcnow().isoformat()
    _run_state["error"] = None
    args = [sys.executable, "-m", "apm", "run"]
    if demo:
        args.append("--demo")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(Path(__file__).parent),
        )
        await proc.wait()
        _run_state["error"] = None if proc.returncode == 0 else f"Exit code {proc.returncode}"
    except Exception as exc:
        _run_state["error"] = str(exc)
    finally:
        _run_state["running"] = False
        _run_state["finished_at"] = datetime.datetime.utcnow().isoformat()


async def _run_backtest(demo: bool) -> None:
    import sys, datetime
    _backtest_state["running"] = True
    _backtest_state["started_at"] = datetime.datetime.utcnow().isoformat()
    _backtest_state["error"] = None
    args = [sys.executable, "-m", "apm", "run", "--agent", "backtest"]
    if demo:
        args.append("--demo")
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(Path(__file__).parent),
        )
        await proc.wait()
        _backtest_state["error"] = None if proc.returncode == 0 else f"Exit code {proc.returncode}"
    except Exception as exc:
        _backtest_state["error"] = str(exc)
    finally:
        _backtest_state["running"] = False
        _backtest_state["finished_at"] = datetime.datetime.utcnow().isoformat()


def _get_run_date() -> str | None:
    path = OUTPUT_DIR / "economy.json"
    if path.exists():
        raw = json.loads(path.read_text())
        return raw.get("as_of_date")
    return None


# ── Live macro fetch (FRED + yfinance) ────────────────────────────────────────

FRED_SERIES: dict[str, tuple[str, str, float]] = {
    # (series_id, snapshot_key, unit_factor)
    "fed_funds":      ("DFF",        "fed_funds_pct",           1.0),
    "ten_year_yield": ("DGS10",      "ten_year_yield_pct",      1.0),
    "yield_curve":    ("T10Y2Y",     "yield_curve_2s10s_bps",  100.0),  # % → bps
    "baa_spread":     ("BAMLC0A0CM", "baa_credit_spread_pct",   1.0),
    "vix":            ("VIXCLS",     "vix",                     1.0),
    "wti_crude":      ("DCOILWTICO", "wti_crude_usd",           1.0),
    "dxy":            ("DTWEXBGS",   "dxy",                     1.0),
    "initial_claims": ("ICSA",       "initial_claims_k",        0.001),  # units → thousands
    "nahb":           ("HOUST",      "nahb_index",              0.001),  # housing starts (k units proxy)
}


@app.get("/api/live/macro")
async def get_live_macro() -> dict[str, Any]:
    """
    Pull latest macro readings from FRED + compute CPI YoY from CPIAUCSL.
    Returns partial data if FRED_API_KEY not set — yfinance-based fields still work.
    """
    import os
    import datetime
    fred_key = os.getenv("FRED_API_KEY", "")
    result: dict[str, Any] = {"source": {}, "values": {}, "has_fred_key": bool(fred_key)}

    if fred_key:
        import httpx

        async def _fred_series(series_id: str) -> list[float]:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": fred_key,
                "file_type": "json",
                "limit": 24,
                "sort_order": "desc",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                obs = r.json().get("observations", [])
                return [float(o["value"]) for o in obs if o["value"] != "."]

        for field, (series_id, snap_key, factor) in FRED_SERIES.items():
            try:
                vals = await _fred_series(series_id)
                if vals:
                    result["values"][field] = round(vals[0] * factor, 3)
                    result["source"][field] = f"FRED:{series_id}"
                else:
                    result["source"][field] = f"FRED:{series_id} (no data)"
            except Exception as exc:
                result["source"][field] = f"error:{exc}"
            await asyncio.sleep(0.15)  # FRED rate limit: 120 req/min

        # CPI YoY — compute from monthly level series
        try:
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {"series_id": "CPIAUCSL", "api_key": fred_key, "file_type": "json", "limit": 15, "sort_order": "desc"}
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, params=params)
                r.raise_for_status()
                obs = [float(o["value"]) for o in r.json().get("observations", []) if o["value"] != "."]
                if len(obs) >= 13:
                    yoy = (obs[0] / obs[12] - 1) * 100
                    result["values"]["cpi"] = round(yoy, 2)
                    result["source"]["cpi"] = "FRED:CPIAUCSL (YoY computed)"
        except Exception as exc:
            result["source"]["cpi"] = f"error:{exc}"

        result["source"]["pmi"] = "manual — ISM PMI not on FRED (proprietary)"
        result["source"]["ism_new_orders"] = "manual — ISM New Orders not on FRED"
    else:
        result["note"] = "Set FRED_API_KEY env var for live macro. Get a free key at fred.stlouisfed.org"

    return result


# ── Assumptions config endpoints ──────────────────────────────────────────────

@app.get("/api/config/assumptions")
async def get_assumptions() -> dict[str, Any]:
    """Return all tunable assumption config files."""
    import yaml
    out: dict[str, Any] = {}
    for name in ["scenarios", "weights"]:
        p = CONFIG_DIR / f"{name}.yaml"
        if p.exists():
            out[name] = yaml.safe_load(p.read_text()) or {}
    # Also return valuation defaults from the module
    out["valuation"] = _valuation_defaults()
    return out


@app.post("/api/config/assumptions")
async def update_assumptions(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Partially update assumption configs. Accepts keys: 'scenarios', 'weights', 'valuation'.
    For scenarios: update probabilities and per-scenario macro numbers.
    For weights: update score_component weights.
    """
    import yaml
    updated: list[str] = []

    if "scenarios" in payload:
        p = CONFIG_DIR / "scenarios.yaml"
        cfg: dict = yaml.safe_load(p.read_text()) or {} if p.exists() else {}
        _deep_merge(cfg, payload["scenarios"])
        p.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
        updated.append("scenarios")

    if "weights" in payload:
        p = CONFIG_DIR / "weights.yaml"
        cfg = yaml.safe_load(p.read_text()) or {} if p.exists() else {}
        # Only update numeric weights under score_components
        for comp, val in payload["weights"].items():
            if "score_components" in cfg and comp in cfg["score_components"]:
                cfg["score_components"][comp]["weight"] = int(val)
        p.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
        updated.append("weights")

    if "valuation" in payload:
        _write_valuation_defaults(payload["valuation"])
        updated.append("valuation")

    return {"status": "ok", "updated": updated}


def _valuation_defaults() -> dict[str, Any]:
    """Read valuation defaults from a small JSON sidecar (created on first write)."""
    p = CONFIG_DIR / "valuation_defaults.json"
    if p.exists():
        return json.loads(p.read_text())
    return {
        "terminal_g_startup": 3.0,
        "terminal_g_growth": 2.5,
        "terminal_g_mature": 2.0,
        "terminal_g_decline": 1.0,
        "equity_risk_premium": 5.5,
        "tax_rate_pct": 21.0,
        "dcf_weight": 0.6,
        "multiples_weight": 0.4,
        "bear_multiple_adj": 0.80,
        "bull_multiple_adj": 1.15,
        "buy_confidence_min": 63,
        "buy_return_min_pct": 8.0,
        "buy_rr_min": 1.5,
        "sell_confidence_max": 48,
        "sell_return_max_pct": 3.0,
        "hold_rr_min": 1.0,
    }


def _write_valuation_defaults(data: dict) -> None:
    p = CONFIG_DIR / "valuation_defaults.json"
    current = json.loads(p.read_text()) if p.exists() else _valuation_defaults()
    current.update({k: v for k, v in data.items() if k in _valuation_defaults()})
    p.write_text(json.dumps(current, indent=2))


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# Serve built frontend if it exists
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

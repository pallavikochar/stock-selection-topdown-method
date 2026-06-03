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


@app.post("/api/run")
async def trigger_run(
    background_tasks: BackgroundTasks,
    demo: bool = True,
) -> dict[str, str]:
    """Trigger a full pipeline run in the background."""
    background_tasks.add_task(_run_pipeline, demo)
    return {"status": "started", "demo": str(demo)}


async def _run_pipeline(demo: bool) -> None:
    import subprocess, sys
    args = [sys.executable, "-m", "apm", "run"]
    if demo:
        args.append("--demo")
    await asyncio.create_subprocess_exec(*args)


def _get_run_date() -> str | None:
    path = OUTPUT_DIR / "economy.json"
    if path.exists():
        raw = json.loads(path.read_text())
        return raw.get("as_of_date")
    return None


# Serve built frontend if it exists
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

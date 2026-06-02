"""
CLI entry point.

Usage:
  python -m apm run --demo                   full demo run
  python -m apm run --demo --report          + write output/report.md
  python -m apm run --demo --agent economy   single agent
  python -m apm run --demo --from sector     resume from sector
  python -m apm run --log-level DEBUG        verbose
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from apm.utils.logging import setup_logging

app = typer.Typer(
    help="Project APM — Multi-agent top-down quantamental engine",
    no_args_is_help=True,
)
console = Console()


def _build_orchestrator(demo: bool):
    from apm.agents.a01_economy import EconomyAgent
    from apm.agents.a02_cycle import CycleAgent
    from apm.agents.a03_scenario import ScenarioAgent
    from apm.agents.a04_sector import SectorAgent
    from apm.agents.a05_style import StyleAgent
    from apm.agents.a06_screen import ScreenAgent
    from apm.agents.a07_fundamental import FundamentalAgent
    from apm.agents.a08_valuation import ValuationAgent
    from apm.agents.a09_risk_correlation import RiskCorrelationAgent
    from apm.agents.a10_recommendation import RecommendationAgent
    from apm.agents.a11_report import ReportAgent
    from apm.agents.a12_llm_analysis import LLMAnalysisAgent
    from apm.core.orchestrator import Orchestrator

    return (
        Orchestrator(demo_mode=demo)
        .register(
            EconomyAgent(),
            CycleAgent(),
            ScenarioAgent(),
            SectorAgent(),
            StyleAgent(),
            ScreenAgent(),
            FundamentalAgent(),
            ValuationAgent(),
            RiskCorrelationAgent(),
            RecommendationAgent(),
            ReportAgent(),
            LLMAnalysisAgent(),
        )
    )


@app.command("run")
def cmd_run(
    demo: bool = typer.Option(False, "--demo", help="Run on cached demo data — no API keys needed"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Run a single agent by name"),
    from_agent: Optional[str] = typer.Option(None, "--from", help="Resume pipeline from this agent"),
    report: bool = typer.Option(False, "--report", help="Write Markdown report to output/"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
) -> None:
    """Run the full pipeline (or partial chain) and optionally generate a report."""
    setup_logging(log_level)
    orch = _build_orchestrator(demo)
    orch.run(from_agent=from_agent, single_agent=agent)
    if report:
        console.print("\n[green]Report written to output/report.md[/green]")


@app.command("agents")
def cmd_agents() -> None:
    """List all agents and whether their outputs exist."""
    from pathlib import Path
    output_dir = Path("output/agents")
    names = [
        "economy", "cycle", "scenario", "sector", "style", "screen",
        "fundamental", "valuation", "risk_correlation", "recommendations", "report", "llm_analysis",
    ]
    for name in names:
        path = output_dir / f"{name}.json"
        status = "[green]✓[/green]" if path.exists() else "[dim]✗[/dim]"
        console.print(f"  {status} {name}")


if __name__ == "__main__":
    app()

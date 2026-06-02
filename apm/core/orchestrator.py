"""
Orchestrator: runs agents 1→11 in sequence, persists each AgentOutput,
and supports --agent / --from for single-agent and partial-chain execution.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from apm.core.agent import Agent, AgentOutput, Context, OUTPUT_DIR

log = logging.getLogger(__name__)
console = Console()


class Orchestrator:
    def __init__(self, demo_mode: bool = False, output_dir: Path = OUTPUT_DIR) -> None:
        self.demo_mode = demo_mode
        self.output_dir = output_dir
        self._agents: list[Agent] = []

    def register(self, *agents: Agent) -> "Orchestrator":
        self._agents.extend(agents)
        return self

    def run(
        self,
        tickers: Optional[list[str]] = None,
        from_agent: Optional[str] = None,
        single_agent: Optional[str] = None,
    ) -> list[AgentOutput]:
        """Run the full pipeline (or a partial chain) and return all outputs."""
        run_id = str(uuid.uuid4())[:8]
        context = Context(
            run_id=run_id,
            demo_mode=self.demo_mode,
            tickers=tickers or [],
            as_of_date=date.today().isoformat(),
        )

        agents_to_run = self._resolve_agents(from_agent, single_agent)
        outputs: list[AgentOutput] = []

        console.print(f"\n[bold cyan]Project APM[/bold cyan] · run [dim]{run_id}[/dim]")
        console.print(f"Mode: {'[yellow]DEMO[/yellow]' if self.demo_mode else '[green]LIVE[/green]'}")
        console.print()

        # Pre-load cached outputs for agents we're skipping
        if from_agent or single_agent:
            self._preload_cached_context(context, agents_to_run)

        for agent in agents_to_run:
            t0 = time.perf_counter()
            console.print(f"  [dim]→[/dim] [bold]{agent.name}[/bold]", end="")
            try:
                output = agent.run(context)
                elapsed = time.perf_counter() - t0
                path = output.persist(self.output_dir)
                self._apply_output_to_context(agent.name, output, context)
                outputs.append(output)
                label_color = {
                    "High": "green", "Medium": "yellow", "Low": "red"
                }.get(output.confidence_label.value, "white")
                console.print(
                    f"  [{label_color}]{output.confidence_label.value} {output.confidence:.0f}[/{label_color}]"
                    f"  [dim]{elapsed:.1f}s → {path.name}[/dim]"
                )
                if output.warnings:
                    for w in output.warnings:
                        console.print(f"    [yellow]⚠ {w}[/yellow]")
            except Exception as exc:
                console.print(f"  [red]FAILED: {exc}[/red]")
                log.exception("Agent %s failed", agent.name)
                raise

        self._print_summary(outputs)
        return outputs

    def _resolve_agents(
        self, from_agent: Optional[str], single_agent: Optional[str]
    ) -> list[Agent]:
        if single_agent:
            matches = [a for a in self._agents if a.name == single_agent]
            if not matches:
                raise ValueError(f"Unknown agent: {single_agent}")
            return matches
        if from_agent:
            names = [a.name for a in self._agents]
            if from_agent not in names:
                raise ValueError(f"Unknown agent: {from_agent}")
            idx = names.index(from_agent)
            return self._agents[idx:]
        return self._agents

    def _preload_cached_context(self, context: Context, agents_to_run: list[Agent]) -> None:
        """Load persisted outputs for all agents that won't be re-run."""
        run_names = {a.name for a in agents_to_run}
        for agent in self._agents:
            if agent.name in run_names:
                continue
            try:
                output = AgentOutput.load(agent.name, self.output_dir)
                self._apply_output_to_context(agent.name, output, context)
                log.debug("Pre-loaded cached output for %s", agent.name)
            except FileNotFoundError:
                log.warning("No cached output found for %s — downstream agents may fail", agent.name)

    @staticmethod
    def _apply_output_to_context(agent_name: str, output: AgentOutput, context: Context) -> None:
        """Write an agent's typed data into the shared Context."""
        from apm.core.agent import (
            CycleData, EconomyData, FundamentalData, LLMAnalysisData, RiskData,
            RecommendationsData, ScenariosData, SectorData, ScreenData,
            StyleData, ValuationData,
        )

        mapping = {
            "economy": ("economy", EconomyData),
            "cycle": ("cycle", CycleData),
            "scenario": ("scenarios", ScenariosData),
            "sector": ("sectors", SectorData),
            "style": ("styles", StyleData),
            "screen": ("screen", ScreenData),
            "risk_correlation": ("risk", RiskData),
            "recommendations": ("recommendations", RecommendationsData),
            "llm_analysis": ("llm_analysis", LLMAnalysisData),
        }

        if agent_name in mapping:
            field, model_cls = mapping[agent_name]
            try:
                parsed = model_cls.model_validate(output.data)
                setattr(context, field, parsed)
            except Exception as exc:
                log.warning("Could not parse %s output into context: %s", agent_name, exc)

        # Per-ticker agents
        elif agent_name == "fundamental":
            if isinstance(output.data, dict):
                from apm.core.agent import FundamentalData
                context.fundamentals = {
                    k: FundamentalData.model_validate(v) for k, v in output.data.items()
                }
        elif agent_name == "valuation":
            if isinstance(output.data, dict):
                from apm.core.agent import ValuationData
                context.valuations = {
                    k: ValuationData.model_validate(v) for k, v in output.data.items()
                }

    def _print_summary(self, outputs: list[AgentOutput]) -> None:
        table = Table(title="Run Summary", show_header=True, header_style="bold cyan")
        table.add_column("Agent")
        table.add_column("Confidence", justify="right")
        table.add_column("Label")
        table.add_column("Warnings", justify="right")
        for o in outputs:
            color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(
                o.confidence_label.value, "white"
            )
            table.add_row(
                o.agent_name,
                f"{o.confidence:.1f}",
                f"[{color}]{o.confidence_label.value}[/{color}]",
                str(len(o.warnings)),
            )
        console.print()
        console.print(table)

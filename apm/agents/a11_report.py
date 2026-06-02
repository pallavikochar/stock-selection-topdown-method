"""
Agent 11 — ReportAgent
Assembles the deliverable in the course presentation arc.
Always outputs Markdown to output/report.md.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from apm.core.agent import Agent, AgentOutput, Context
from apm.core.types import ConfidenceLabel

log = logging.getLogger(__name__)
OUTPUT_DIR = Path("output")


class ReportAgent(Agent):
    name = "report"

    def run(self, context: Context) -> AgentOutput:
        md = self._build_markdown(context)
        OUTPUT_DIR.mkdir(exist_ok=True)
        report_path = OUTPUT_DIR / "report.md"
        report_path.write_text(md)

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date,
            confidence=85.0,
            confidence_label=ConfidenceLabel.HIGH,
            rationale=f"Report written to {report_path}",
            data={"report_path": str(report_path), "word_count": len(md.split())},
            warnings=[],
            provenance={"format": "Markdown"},
        )

    def _build_markdown(self, context: Context) -> str:
        ec = context.economy
        cy = context.cycle
        sc = context.scenarios
        se = context.sectors
        st = context.styles
        ri = context.risk
        rec = context.recommendations

        lines: list[str] = []
        lines += [
            f"# Project APM — Investment Report",
            f"**As of:** {context.as_of_date} · **Run ID:** {context.run_id}",
            f"> *Top-Down Process: Economy → Cycle → Sector → Style → Stock. "
            f"Macro explains ~70% of a stock's move.*",
            "",
            "---",
            "",
        ]

        # 1. Economic View
        lines += [
            "## 1. Economic View",
            f"**Growth:** {ec.growth_level.value} & {ec.growth_direction.value}  ",
            f"**Inflation:** {ec.inflation_level.value} & {ec.inflation_direction.value}  ",
            f"**PMI:** {ec.pmi_read:.1f} ({ec.pmi_direction.value})  ",
            f"**CMI:** {ec.cmi_score:.1f} ({ec.cmi_direction.value})  ",
            f"**LEI Trajectory:** {ec.lei_trajectory}  ",
            f"**Cost of Money:** {ec.cost_of_money_read}  ",
            f"**Cost of Goods:** {ec.cost_of_goods_read}  ",
            "",
        ] if ec else ["## 1. Economic View\n*No data*\n"]

        # 2. Cycle & H.O.P.E.
        if cy:
            lines += [
                "## 2. Business Cycle & H.O.P.E.",
                f"**Investment Clock Phase:** {cy.clock_phase.value}  ",
                f"**Market Cycle Phase:** {cy.market_cycle_phase.value}  ",
                f"**H.O.P.E. Stage:** {cy.hope_stage.value} → next: {cy.hope_next_stage.value}  ",
                f"**Inflecting indicators:** {', '.join(cy.hope_inflecting_indicators)}  ",
                f"**Rotation direction:** {cy.rotation_direction}  ",
                "",
            ]

        # 3. Scenarios
        if sc:
            lines += ["## 3. Scenarios & Probabilities", ""]
            for s in sc.scenarios:
                m = s.macro
                lines.append(
                    f"### {s.label} ({s.probability:.0%})\n"
                    f"- GDP: {m.gdp_growth_pct:+.1f}% | Revenue: {m.revenue_growth_pct:+.1f}% | "
                    f"CPI: {m.cpi_pct:.1f}% | 10yr: {m.ten_year_yield_pct:.2f}%\n"
                    f"- Margins: {m.margin_trajectory} | Multiple: {m.market_multiple_path} | "
                    f"EPS growth: {m.earnings_growth_pct:+.1f}%\n"
                )
            lines.append("")

        # 4. Sector Ranking
        if se:
            lines += ["## 4. Sector Ranking (Favored → Unfavored)", ""]
            lines.append("| Sector | Score | Favorability | Primary Driver |")
            lines.append("|--------|-------|-------------|----------------|")
            for s in se.ranked_sectors:
                lines.append(f"| {s.sector} | {s.score:.0f} | {s.favorability.value} | {s.primary_macro_driver} |")
            lines.append("")

        # 5. Style & Factor
        if st:
            lines += [
                "## 5. Style & Factor Selection",
                f"**Phase:** {st.phase.value}  ",
                f"**Favored size/style box:** {st.favored_size_style_box}  ",
                f"**Value vs. Growth:** {st.value_vs_growth_read[:120]}…  ",
                "",
                "**Favored Factors:**",
            ]
            for f in st.favored_factors:
                lines.append(f"- {f.factor_name} ({f.classification}) — {f.rationale[:80]}")
            lines += ["", f"> ⚠ {st.dividend_yield_warning}", ""]

        # 6. Risk & Correlation
        if ri:
            lines += [
                "## 6. Risk & Correlation Context",
                f"**Avg Pairwise Correlation:** {ri.avg_pairwise_correlation:.2f} → **{ri.correlation_regime.value} regime**  ",
                f"**Stock-picking reward:** {ri.stock_picking_reward_signal}  ",
                f"**Position count guidance:** {ri.recommended_position_count_guidance[:200]}  ",
            ]
            if ri.crowded_names:
                lines.append(f"**Crowded names:** {', '.join(ri.crowded_names)}  ")
            lines.append("")

        # 7. Recommendations
        if rec:
            lines += ["## 7. Final Recommendations", ""]
            lines.append(
                "| Ticker | Action | Current | Target | Return | R:R | Confidence | Replaces |"
            )
            lines.append(
                "|--------|--------|---------|--------|--------|-----|-----------|---------|"
            )
            for r in rec.ranked:
                lines.append(
                    f"| **{r.ticker}** | {r.action.value} | ${r.current_price:.0f} | "
                    f"${r.prob_weighted_target:.0f} | {r.expected_return_pct:+.1f}% | "
                    f"{r.reward_to_risk:.1f}x | {r.confidence_label.value} {r.confidence_numeric:.0f} | "
                    f"{r.replaces_ticker or '—'} |"
                )
            lines.append("")

            lines += ["### Investment Theses", ""]
            for r in rec.ranked:
                lines.append(f"#### {r.ticker} — {r.action.value}")
                lines.append(r.thesis)
                if r.warnings:
                    for w in r.warnings:
                        lines.append(f"> ⚠ {w}")
                lines.append("")

                # Scenario table
                lines.append("**Scenario Analysis:**")
                lines.append("| Scenario | Prob | EPS Growth | WACC | Target | Upside |")
                lines.append("|----------|------|-----------|------|--------|--------|")
                for sv in r.scenario_table:
                    lines.append(
                        f"| {sv.scenario_name} | {sv.probability:.0%} | "
                        f"{sv.revenue_growth_pct:+.1f}% | {sv.wacc_pct:.1f}% | "
                        f"${sv.blended_value:.0f} | {sv.upside_pct:+.1f}% |"
                    )
                lines.append("")

        lines += [
            "---",
            f"*Generated by Project APM · {date.today().isoformat()} · Top-Down Quantamental Process*",
            "*All scenario values are estimates. Not investment advice.*",
        ]

        return "\n".join(lines)

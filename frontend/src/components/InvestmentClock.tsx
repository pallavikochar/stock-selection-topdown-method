import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { motion } from "motion/react";
import type { ClockPhase } from "../lib/types";

const PHASES = {
  REFLATION:   { angle: -135, label: "Reflation",   color: "#4ade80", desc: "Growth↑ Inflation↓" },
  INFLATION:   { angle: -45,  label: "Inflation",    color: "#f5a623", desc: "Growth↑ Inflation↑" },
  STAGFLATION: { angle: 45,   label: "Stagflation",  color: "#ef4444", desc: "Growth↓ Inflation↑" },
  DEFLATION:   { angle: 135,  label: "Deflation",    color: "#818cf8", desc: "Growth↓ Inflation↓" },
  UNKNOWN:     { angle: 0,    label: "Unknown",      color: "#64748b", desc: "Ambiguous" },
};

interface Props {
  phase: ClockPhase;
}

export function InvestmentClock({ phase }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const currentPhase = PHASES[phase] ?? PHASES.UNKNOWN;

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const size = 280;
    const cx = size / 2;
    const cy = size / 2;
    const r = 110;
    const innerR = 32;

    svg.attr("viewBox", `0 0 ${size} ${size}`).attr("role", "img")
      .attr("aria-label", `Investment Clock showing ${phase} phase`);

    // Background circle
    svg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", r + 12)
      .attr("fill", "oklch(13% 0.030 252)").attr("stroke", "oklch(24% 0.040 252)").attr("stroke-width", 1);

    // Four quadrant arcs
    const quadrants = [
      { start: -Math.PI, end: -Math.PI / 2, color: "#4ade8020", phase: "REFLATION" },
      { start: -Math.PI / 2, end: 0,         color: "#f5a62320", phase: "INFLATION" },
      { start: 0, end: Math.PI / 2,           color: "#ef444420", phase: "STAGFLATION" },
      { start: Math.PI / 2, end: Math.PI,     color: "#818cf820", phase: "DEFLATION" },
    ];

    const arc = d3.arc<{ start: number; end: number; color: string }>()
      .innerRadius(innerR)
      .outerRadius(r)
      .startAngle((d) => d.start)
      .endAngle((d) => d.end);

    quadrants.forEach((q) => {
      const isActive = q.phase === phase;
      svg.append("path")
        .datum(q)
        .attr("d", arc)
        .attr("fill", isActive ? q.color.replace("20", "40") : q.color)
        .attr("stroke", isActive ? q.color.replace("20", "80") : "oklch(24% 0.040 252)")
        .attr("stroke-width", isActive ? 1.5 : 0.5)
        .attr("transform", `translate(${cx},${cy})`);
    });

    // Axes
    svg.append("line").attr("x1", cx - r).attr("y1", cy).attr("x2", cx + r).attr("y2", cy)
      .attr("stroke", "oklch(24% 0.040 252)").attr("stroke-width", 0.5);
    svg.append("line").attr("x1", cx).attr("y1", cy - r).attr("x2", cx).attr("y2", cy + r)
      .attr("stroke", "oklch(24% 0.040 252)").attr("stroke-width", 0.5);

    // Axis labels
    svg.append("text").text("Growth↑").attr("x", cx + r + 2).attr("y", cy - 4).attr("text-anchor", "start").style("font-size", "9px").style("fill", "oklch(40% 0.04 252)").style("font-family", "JetBrains Mono");
    svg.append("text").text("Growth↓").attr("x", cx - r - 2).attr("y", cy - 4).attr("text-anchor", "end").style("font-size", "9px").style("fill", "oklch(40% 0.04 252)").style("font-family", "JetBrains Mono");
    svg.append("text").text("Infl↑").attr("x", cx + 4).attr("y", cy - r + 10).style("font-size", "9px").style("fill", "oklch(40% 0.04 252)").style("font-family", "JetBrains Mono");
    svg.append("text").text("Infl↓").attr("x", cx + 4).attr("y", cy + r - 4).style("font-size", "9px").style("fill", "oklch(40% 0.04 252)").style("font-family", "JetBrains Mono");

    // Phase labels
    const phaseLabels = [
      { angle: -135, label: "Reflation",   color: "#4ade80" },
      { angle: -45,  label: "Inflation",   color: "#f5a623" },
      { angle: 45,   label: "Stagflation", color: "#ef4444" },
      { angle: 135,  label: "Deflation",   color: "#818cf8" },
    ];
    const labelR = r * 0.65;
    phaseLabels.forEach(({ angle, label, color }) => {
      const rad = (angle * Math.PI) / 180;
      const lx = cx + labelR * Math.cos(rad);
      const ly = cy + labelR * Math.sin(rad);
      svg.append("text").text(label)
        .attr("x", lx).attr("y", ly)
        .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
        .style("font-size", "10px").style("fill", color)
        .style("font-weight", label === currentPhase.label ? "700" : "400")
        .style("font-family", "Space Grotesk");
    });

    // Center circle
    svg.append("circle").attr("cx", cx).attr("cy", cy).attr("r", innerR)
      .attr("fill", "oklch(9% 0.025 252)").attr("stroke", "oklch(30% 0.04 252)").attr("stroke-width", 1);
    svg.append("text").text("APM").attr("x", cx).attr("y", cy + 1)
      .attr("text-anchor", "middle").attr("dominant-baseline", "middle")
      .style("font-size", "9px").style("fill", "oklch(40% 0.04 252)").style("font-family", "JetBrains Mono");

  }, [phase]);

  // Needle — drawn in React with Motion for animation
  const targetAngle = currentPhase.angle;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <svg ref={svgRef} width="280" height="280" />
        {/* Animated needle overlay */}
        <motion.div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          aria-hidden="true"
        >
          <motion.div
            animate={{ rotate: targetAngle }}
            transition={{ type: "spring", stiffness: 60, damping: 15 }}
            className="w-0.5 h-[90px] mb-[140px] rounded-full"
            style={{
              originX: "50%", originY: "100%",
              background: `linear-gradient(to top, ${currentPhase.color}, transparent)`,
              transformOrigin: "bottom center",
            }}
          />
        </motion.div>
      </div>

      <div className="text-center">
        <div className="font-display font-700 text-lg" style={{ color: currentPhase.color }}>
          {currentPhase.label}
        </div>
        <div className="text-xs text-navy-500 font-mono mt-0.5">{currentPhase.desc}</div>
      </div>
    </div>
  );
}

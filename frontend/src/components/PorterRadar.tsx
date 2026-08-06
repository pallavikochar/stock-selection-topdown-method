import type { PorterForces } from "../lib/types";

// Spec: Porter's Five Forces radar with pentagon shape
// Each raw score is 1–5 where HIGHER = STRONGER THREAT (worse for company).
// We invert for display: display_value = 5 - raw, so larger area = better position.
const AXES = [
  { key: "threat_of_entry",       label: "Entry\nBarrier"      },
  { key: "buyer_power",           label: "Customer\nPosition"  },
  { key: "competitive_rivalry",   label: "Competitive\nEdge"   },
  { key: "supplier_power",        label: "Supplier\nPosition"  },
  { key: "threat_of_substitutes", label: "Substitutes\nMoat"   },
] as const;

type AxisKey = (typeof AXES)[number]["key"];

interface Props {
  porter: PorterForces;
  size?: number;
}

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function pentagPoints(
  cx: number,
  cy: number,
  r: number,
  startDeg = -90,
  n = 5
): { x: number; y: number }[] {
  return Array.from({ length: n }, (_, i) =>
    polar(cx, cy, r, startDeg + i * (360 / n))
  );
}

function polyline(pts: { x: number; y: number }[]) {
  return pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ") + " Z";
}

export function PorterRadar({ porter, size = 220 }: Props) {
  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.32;   // data area radius
  const labelR = size * 0.47; // label distance

  // Invert raw scores: display = 5 - raw → larger = better
  const values = AXES.map((a) => 5 - (porter[a.key as AxisKey] as number));

  // Background rings — warm charcoal palette
  const ringColors = ["oklch(15% 0.009 58)", "oklch(19% 0.010 58)", "oklch(23% 0.010 58)"];

  const ringPaths = [2, 3.5, 5].map((level) => {
    const r = (level / 5) * maxR;
    return polyline(pentagPoints(cx, cy, r));
  });

  const axisEndPts = pentagPoints(cx, cy, maxR);
  const dataPts = values.map((v, i) => {
    const r = (Math.max(0, Math.min(5, v)) / 5) * maxR;
    return polar(cx, cy, r, -90 + i * 72);
  });

  const dataPath = polyline(dataPts);
  const labelPts = pentagPoints(cx, cy, labelR);

  // Text anchor logic per angle — typed for SVG
  function textAnchor(deg: number): "middle" | "start" | "end" {
    const a = ((deg % 360) + 360) % 360;
    if (a < 30 || a > 330) return "middle";
    if (a < 150) return "start";
    if (a < 210) return "middle";
    return "end";
  }
  function domBaseline(deg: number): "middle" | "auto" | "hanging" {
    const a = ((deg % 360) + 360) % 360;
    if (a > 30 && a < 150) return "auto";
    if (a > 210 && a < 330) return "hanging";
    return "middle";
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-label="Porter's Five Forces radar">
        {/* Background rings */}
        {ringPaths.map((d, i) => (
          <path key={i} d={d} fill={ringColors[i]} stroke="oklch(27% 0.010 58)" strokeWidth={0.5} />
        ))}

        {/* Axis lines */}
        {axisEndPts.map((pt, i) => (
          <line key={i} x1={cx} y1={cy} x2={pt.x} y2={pt.y}
            stroke="oklch(27% 0.010 58)" strokeWidth={0.5} />
        ))}

        {/* Data fill — gold */}
        <path d={dataPath} fill="oklch(80% 0.163 55 / 0.15)" stroke="oklch(80% 0.163 55)" strokeWidth={1.5} />

        {/* Data vertex dots */}
        {dataPts.map((pt, i) => (
          <circle key={i} cx={pt.x} cy={pt.y} r={2.5} fill="oklch(80% 0.163 55)" />
        ))}

        {/* Labels */}
        {AXES.map((axis, i) => {
          const deg = -90 + i * 72;
          const lp = labelPts[i];
          const lines = axis.label.split("\n");
          return (
            <text
              key={axis.key}
              x={lp.x}
              y={lp.y}
              textAnchor={textAnchor(deg)}
              dominantBaseline={domBaseline(deg)}
              fontSize="7.5"
              fill="oklch(48% 0.008 58)"
              fontFamily="JetBrains Mono, monospace"
            >
              {lines.map((line, li) => (
                <tspan key={li} x={lp.x} dy={li === 0 ? 0 : 10}>
                  {line}
                </tspan>
              ))}
            </text>
          );
        })}

        {/* Score label at center */}
        <text x={cx} y={cy + 2} textAnchor="middle" dominantBaseline="middle"
          fontSize="11" fill="oklch(80% 0.163 55)" fontFamily="JetBrains Mono, monospace"
          fontWeight="700"
        >
          {porter.overall_score.toFixed(1)}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" dominantBaseline="middle"
          fontSize="7" fill="oklch(38% 0.008 58)" fontFamily="JetBrains Mono, monospace"
        >
          /10
        </text>
      </svg>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[10px] font-mono text-navy-500">
        {AXES.map((axis, i) => (
          <div key={axis.key} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-cyan-accent/60 shrink-0" />
            <span className="truncate">{axis.label.replace("\n", " ")}</span>
            <span className="text-white ml-auto">{values[i].toFixed(1)}</span>
          </div>
        ))}
      </div>

      {/* Market share + margin outlook */}
      <div className="flex gap-3 text-xs">
        <span className="text-navy-500">Market share: <span className="text-white">{porter.market_share_outlook}</span></span>
        <span className="text-navy-600">·</span>
        <span className="text-navy-500">Margins: <span className="text-white">{porter.margin_outlook}</span></span>
      </div>
    </div>
  );
}

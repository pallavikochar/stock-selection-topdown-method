import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { api } from "../lib/api";

type Regime = "AUTO" | "REFLATION" | "INFLATION" | "STAGFLATION" | "DEFLATION";

const REGIME_META: Record<Regime, { label: string; color: string; hint: string }> = {
  AUTO:        { label: "Auto (computed)", color: "text-navy-400 border-navy-600 bg-navy-800/40",  hint: "Derived from macro variables via Investment Clock" },
  REFLATION:   { label: "Reflation",       color: "text-cyan-accent border-cyan-accent/40 bg-cyan-accent/10",   hint: "Growth ↑, Inflation ↓ — bonds, growth stocks" },
  INFLATION:   { label: "Inflation",       color: "text-amber-accent border-amber-accent/40 bg-amber-accent/10", hint: "Growth ↑, Inflation ↑ — commodities, financials" },
  STAGFLATION: { label: "Stagflation",     color: "text-red-signal border-red-signal/40 bg-red-signal/10",    hint: "Growth ↓, Inflation ↑ — energy, staples" },
  DEFLATION:   { label: "Deflation",       color: "text-navy-400 border-navy-500 bg-navy-800/60",              hint: "Growth ↓, Inflation ↓ — defensives, bonds" },
};

const FIELDS: { key: string; label: string; unit: string; min: number; max: number; step: number }[] = [
  { key: "pmi",           label: "PMI (ISM Mfg)",        unit: "",    min: 25,   max: 70,   step: 0.1 },
  { key: "cpi",           label: "CPI YoY",              unit: "%",   min: -1,   max: 12,   step: 0.1 },
  { key: "fed_funds",     label: "Fed Funds",            unit: "%",   min: 0,    max: 8,    step: 0.25 },
  { key: "ten_year_yield",label: "10-Yr Yield",          unit: "%",   min: 0.5,  max: 8,    step: 0.05 },
  { key: "yield_curve",   label: "Yield Curve (2s10s)",  unit: "bps", min: -200, max: 300,  step: 5 },
  { key: "baa_spread",    label: "BAA Credit Spread",    unit: "%",   min: 0.5,  max: 6,    step: 0.05 },
  { key: "vix",           label: "VIX",                  unit: "",    min: 9,    max: 80,   step: 0.5 },
  { key: "nahb",          label: "NAHB Housing",         unit: "",    min: 10,   max: 80,   step: 1 },
  { key: "wti_crude",     label: "WTI Crude",            unit: "$/bbl", min: 30, max: 150,  step: 0.5 },
  { key: "dxy",           label: "DXY Index",            unit: "",    min: 80,   max: 120,  step: 0.1 },
  { key: "initial_claims",label: "Initial Claims",       unit: "k",   min: 150,  max: 700,  step: 1 },
  { key: "ism_new_orders",label: "ISM New Orders",       unit: "",    min: 25,   max: 70,   step: 0.1 },
];

const SNAP_KEY_MAP: Record<string, string> = {
  pmi:            "ism_manufacturing",
  cpi:            "cpi_pct",
  fed_funds:      "fed_funds_pct",
  ten_year_yield: "ten_year_yield_pct",
  yield_curve:    "yield_curve_2s10s_bps",
  baa_spread:     "baa_credit_spread_pct",
  vix:            "vix",
  nahb:           "nahb_index",
  wti_crude:      "wti_crude_usd",
  dxy:            "dxy",
  initial_claims: "initial_claims_k",
  ism_new_orders: "ism_new_orders",
};

export function EconomyPanel() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [draftRegime, setDraftRegime] = useState<Regime>("AUTO");

  const { data: econConfig } = useQuery({
    queryKey: ["econConfig"],
    queryFn: api.econConfig,
  });

  const mutation = useMutation({
    mutationFn: (payload: Record<string, number | string>) => api.setEconConfig(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["econConfig"] });
      setEditing(false);
    },
  });

  const snap = econConfig?.snapshot ?? {};
  const currentRegime = (econConfig?.regime_override ?? "AUTO") as Regime;

  function startEdit() {
    const initial: Record<string, number> = {};
    for (const f of FIELDS) {
      const raw = snap[SNAP_KEY_MAP[f.key]];
      initial[f.key] = typeof raw === "number" ? raw : 0;
    }
    setDraft(initial);
    setDraftRegime((econConfig?.regime_override ?? "AUTO") as Regime);
    setEditing(true);
  }

  function applyAndRun() {
    const payload: Record<string, number | string> = { ...draft, regime_override: draftRegime };
    mutation.mutate(payload, {
      onSuccess: () => { api.run(true); setTimeout(() => window.location.reload(), 4000); },
    });
  }

  return (
    <div className="bg-navy-900 rounded-xl border border-navy-800 p-6">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-600 text-navy-500 uppercase tracking-widest">Economy — Macro Dashboard</h3>
          <p className="text-xs text-navy-600 mt-0.5">Current macro snapshot driving the Investment Clock</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-600 px-2 py-1 rounded border ${REGIME_META[currentRegime].color}`}>
            {REGIME_META[currentRegime].label}
          </span>
          {!editing && (
            <button
              onClick={startEdit}
              className="text-xs px-3 py-1.5 rounded border border-cyan-accent/30 text-cyan-accent hover:bg-cyan-accent/10 transition-colors"
            >
              Edit Macro
            </button>
          )}
        </div>
      </div>

      {/* Read-only macro grid */}
      {!editing && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {FIELDS.map(f => {
            const val = snap[SNAP_KEY_MAP[f.key]];
            return (
              <div key={f.key} className="bg-navy-800/50 rounded-lg px-3 py-2.5 border border-navy-700/40">
                <div className="text-[10px] text-navy-500 uppercase tracking-wider mb-1">{f.label}</div>
                <div className="font-mono text-sm text-white tabular-nums">
                  {typeof val === "number" ? val.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "—"}
                  {val !== undefined && f.unit && <span className="text-navy-500 ml-0.5 text-[10px]">{f.unit}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit mode */}
      <AnimatePresence>
        {editing && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {/* Regime selector */}
            <div className="mb-5">
              <div className="text-xs text-navy-500 uppercase tracking-widest mb-2">Regime Override</div>
              <div className="flex flex-wrap gap-2">
                {(Object.keys(REGIME_META) as Regime[]).map(r => (
                  <button
                    key={r}
                    onClick={() => setDraftRegime(r)}
                    className={`text-xs px-3 py-1.5 rounded border font-600 transition-colors ${
                      draftRegime === r ? REGIME_META[r].color : "text-navy-500 border-navy-700 bg-navy-800/40"
                    }`}
                    title={REGIME_META[r].hint}
                  >
                    {REGIME_META[r].label}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-navy-600 mt-1">{REGIME_META[draftRegime].hint}</p>
            </div>

            {/* Macro variable inputs */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
              {FIELDS.map(f => (
                <div key={f.key} className="bg-navy-800/50 rounded-lg px-3 py-2.5 border border-navy-700/60">
                  <label className="block text-[10px] text-navy-500 uppercase tracking-wider mb-1">
                    {f.label}
                    {f.unit && <span className="ml-1 normal-case">({f.unit})</span>}
                  </label>
                  <input
                    type="number"
                    step={f.step}
                    min={f.min}
                    max={f.max}
                    value={draft[f.key] ?? ""}
                    onChange={e => setDraft(d => ({ ...d, [f.key]: parseFloat(e.target.value) }))}
                    className="w-full bg-transparent font-mono text-sm text-white tabular-nums focus:outline-none focus:ring-1 focus:ring-cyan-accent/50 rounded px-1 py-0.5"
                  />
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={applyAndRun}
                disabled={mutation.isPending}
                className="px-4 py-2 text-sm font-600 rounded-lg bg-cyan-accent text-navy-950 hover:opacity-90 disabled:opacity-50 transition"
              >
                {mutation.isPending ? "Applying…" : "Apply & Re-run Pipeline"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-4 py-2 text-sm text-navy-400 hover:text-white transition"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

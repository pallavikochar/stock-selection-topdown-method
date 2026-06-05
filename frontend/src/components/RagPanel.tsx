import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { RagQueryResult, RagSource, ScoreLabel } from "../lib/types";

// ── Score badge ───────────────────────────────────────────────────────────────

const SCORE_STYLE: Record<ScoreLabel, string> = {
  high:   "bg-green-signal/20 text-green-signal border border-green-signal/30",
  medium: "bg-amber-accent/20 text-amber-accent border border-amber-accent/30",
  low:    "bg-red-signal/20 text-red-signal border border-red-signal/30",
};

function ScoreBadge({ score, label }: { score: number; label: ScoreLabel }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono ${SCORE_STYLE[label]}`}>
      {score.toFixed(2)}
    </span>
  );
}

// ── Source card ───────────────────────────────────────────────────────────────

function SourceCard({ source, index }: { source: RagSource; index: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-surface-border rounded-lg p-3 space-y-1.5 bg-surface-card/40">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-text-dim font-mono">#{index + 1}</span>
          <span className="text-xs font-semibold text-text-primary truncate">{source.citation}</span>
          {source.period && (
            <span className="text-xs text-text-dim">{source.period}</span>
          )}
        </div>
        <ScoreBadge score={source.score} label={source.score_label} />
      </div>

      <p className="text-xs text-text-secondary leading-relaxed">
        {expanded ? source.text : `${source.text.slice(0, 200)}${source.text.length > 200 ? "…" : ""}`}
      </p>

      {source.text.length > 200 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-accent-blue hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

// ── Ingestion badge ───────────────────────────────────────────────────────────

export function RagIngestionBadge() {
  const { data } = useQuery({
    queryKey: ["ragCollections"],
    queryFn: api.ragCollections,
    refetchInterval: 30_000,
    retry: false,
  });

  const count = data?.collections?.[0]?.doc_count ?? 0;

  return (
    <span
      title={`RAG: ${count} chunks ingested`}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono border ${
        count > 0
          ? "border-green-signal/30 text-green-signal bg-green-signal/10"
          : "border-surface-border text-text-dim bg-surface-card/40"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${count > 0 ? "bg-green-signal" : "bg-text-dim"}`} />
      {count > 0 ? `${count} docs` : "No docs"}
    </span>
  );
}

// ── Ingest form ───────────────────────────────────────────────────────────────

function IngestForm() {
  const [ticker, setTicker] = useState("");
  const [docType, setDocType] = useState("10-K");
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleIngest() {
    if (!ticker.trim()) return;
    setBusy(true);
    setStatus(null);
    try {
      const result = await api.ragIngest(ticker.trim().toUpperCase(), docType, year);
      setStatus(result.status === "started" ? "Ingestion started in background…" : result.status);
    } catch {
      setStatus("Failed to start ingestion.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-text-dim">Auto-download + ingest an SEC filing from EDGAR:</p>
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="Ticker (e.g. AAPL)"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          className="flex-1 min-w-[120px] px-2 py-1.5 text-xs rounded border border-surface-border bg-surface-input text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-1 focus:ring-accent-blue/50"
        />
        <select
          value={docType}
          onChange={e => setDocType(e.target.value)}
          className="px-2 py-1.5 text-xs rounded border border-surface-border bg-surface-input text-text-primary focus:outline-none"
        >
          {["10-K", "10-Q", "earnings_transcript", "fed_minutes", "analyst_report"].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          type="number"
          value={year}
          onChange={e => setYear(Number(e.target.value))}
          min={2018}
          max={new Date().getFullYear()}
          className="w-20 px-2 py-1.5 text-xs rounded border border-surface-border bg-surface-input text-text-primary focus:outline-none"
        />
        <button
          onClick={handleIngest}
          disabled={busy || !ticker.trim()}
          className="px-3 py-1.5 text-xs rounded bg-accent-blue/90 hover:bg-accent-blue text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {busy ? "Starting…" : "Ingest"}
        </button>
      </div>
      {status && <p className="text-xs text-amber-accent">{status}</p>}
      <p className="text-xs text-text-dim">
        Or drop PDFs/TXTs in <code className="font-mono">data/raw/</code> and run{" "}
        <code className="font-mono">python -m rag.ingest --all</code>
      </p>
    </div>
  );
}

// ── Main RAG query panel ──────────────────────────────────────────────────────

export function RagPanel() {
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RagQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showIngest, setShowIngest] = useState(false);

  async function handleAsk() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.ragQuery(query.trim(), ticker.trim() || null);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">RAG Research</span>
          <RagIngestionBadge />
        </div>
        <button
          onClick={() => setShowIngest(!showIngest)}
          className="text-xs text-accent-blue hover:underline"
        >
          {showIngest ? "Hide ingest" : "+ Ingest filing"}
        </button>
      </div>

      {/* Ingest form */}
      {showIngest && (
        <div className="p-3 rounded-lg border border-surface-border bg-surface-card/60">
          <IngestForm />
        </div>
      )}

      {/* Query inputs */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Ticker (optional)"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            className="w-28 px-2 py-2 text-sm rounded border border-surface-border bg-surface-input text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-1 focus:ring-accent-blue/50"
          />
          <input
            type="text"
            placeholder="Ask a research question…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleAsk()}
            className="flex-1 px-2 py-2 text-sm rounded border border-surface-border bg-surface-input text-text-primary placeholder:text-text-dim focus:outline-none focus:ring-1 focus:ring-accent-blue/50"
          />
          <button
            onClick={handleAsk}
            disabled={loading || !query.trim()}
            className="px-4 py-2 text-sm rounded bg-accent-blue/90 hover:bg-accent-blue text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "…" : "Ask"}
          </button>
        </div>

        {/* Example queries */}
        <div className="flex flex-wrap gap-1.5">
          {[
            "What is the Fed's forward guidance on rates?",
            "What revenue guidance did management give?",
            "What are the key risks mentioned in 10-K filings?",
          ].map(q => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="text-xs px-2 py-0.5 rounded-full border border-surface-border text-text-dim hover:text-text-secondary hover:border-accent-blue/40 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-red-signal bg-red-signal/10 border border-red-signal/20 rounded p-2">
          {error}
        </p>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-3">
          {/* Answer */}
          <div className="p-3 rounded-lg bg-surface-card/60 border border-surface-border">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-text-dim uppercase tracking-wide">Answer</span>
              {result.avg_score > 0 && (
                <span className="text-xs text-text-dim font-mono">
                  avg similarity {result.avg_score.toFixed(2)}
                </span>
              )}
            </div>
            <p className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">
              {result.answer}
            </p>
          </div>

          {/* Sources */}
          {result.sources.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-text-dim uppercase tracking-wide">
                Sources ({result.sources.length})
              </p>
              {result.sources.map((src, i) => (
                <SourceCard key={i} source={src} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

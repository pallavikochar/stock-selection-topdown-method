"""
Agent 16 — ResearchAgent
Given a ticker (or None for macro) and a research question, retrieves grounded
context from ingested SEC filings / Fed minutes via RAG and returns a cited answer.

Plugs into the existing multi-agent orchestration as agent #16.
Other agents call _rag_context() for optional enrichment before reasoning.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from apm.core.agent import Agent, AgentOutput, Context
from apm.core.types import ConfidenceLabel

log = logging.getLogger(__name__)


def _rag_context(
    query: str,
    ticker: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> str:
    """
    Optional helper for other agents: returns a brief RAG-grounded context string,
    or an empty string if Qdrant is unavailable or no documents are ingested.
    This never raises — it degrades gracefully so the calling agent is unaffected.
    """
    try:
        from rag.retriever import FinancialRetriever
        retriever = FinancialRetriever()
        result = retriever.retrieve_and_summarize(query, ticker=ticker, doc_type=doc_type)
        answer = result.get("answer", "")
        if "No documents ingested" in answer or "Synthesis unavailable" in answer:
            return ""
        sources = result.get("sources", [])
        citations = " | ".join(c.citation() for c in sources[:3])
        return f"{answer[:400]} [{citations}]" if citations else answer[:400]
    except Exception as exc:
        log.debug("RAG context unavailable: %s", exc)
        return ""


class ResearchAgent(Agent):
    """
    Retrieves grounded financial data from SEC filings and transcripts via RAG.
    Designed as a standalone agent (#16) and as a helper for other agents.
    """

    name = "research"
    description = "Retrieves grounded financial data from SEC filings and transcripts via RAG"

    def run(self, context: Context) -> AgentOutput:
        """Run the research agent for all tickers in the current context."""
        from rag.retriever import FinancialRetriever

        retriever = FinancialRetriever()
        tickers = context.tickers or []
        results: dict[str, dict] = {}
        total_score = 0.0
        n = 0

        for ticker in tickers:
            res = self._research_ticker(retriever, ticker)
            results[ticker] = res
            if res.get("avg_score", 0) > 0:
                total_score += res["avg_score"]
                n += 1

        # Also run a macro question
        macro_res = self._research_macro(retriever)
        results["_macro"] = macro_res
        if macro_res.get("avg_score", 0) > 0:
            total_score += macro_res["avg_score"]
            n += 1

        avg_score = total_score / n if n else 0.0
        confidence = round(min(100.0, avg_score * 100), 1)

        rationale = (
            f"RAG: {n} successful retrievals across {len(tickers)} tickers + macro. "
            f"Avg similarity score {avg_score:.2f}"
        )

        return AgentOutput(
            agent_name=self.name,
            run_id=context.run_id,
            as_of_date=context.as_of_date or date.today().isoformat(),
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=rationale,
            data=results,
            warnings=[] if n > 0 else ["No documents ingested — run `python -m rag.ingest` first"],
            provenance={
                "source": "Qdrant vector DB (financial_docs collection)",
                "embedding": "BAAI/bge-base-en-v1.5 (local) or text-embedding-3-small (OpenAI)",
                "synthesis": "Anthropic Claude",
            },
        )

    def run_for_ticker(
        self,
        ticker: str,
        question: str,
    ) -> AgentOutput:
        """
        Convenience method: research a specific question for a specific ticker.
        Returns AgentOutput with answer, sources, and confidence.
        """
        from rag.retriever import FinancialRetriever

        retriever = FinancialRetriever()
        result = retriever.retrieve_and_summarize(question, ticker=ticker)

        avg_score = result.get("avg_score", 0.0)
        confidence = round(min(100.0, avg_score * 100), 1)

        return AgentOutput(
            agent_name=self.name,
            run_id="adhoc",
            as_of_date=date.today().isoformat(),
            confidence=confidence,
            confidence_label=self._confidence_label(confidence),
            rationale=result.get("answer", ""),
            data=result,
            warnings=[],
            provenance={"ticker": ticker, "query": question},
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _research_ticker(self, retriever, ticker: str) -> dict:
        question = f"What revenue guidance did management give for {ticker}?"
        try:
            return retriever.retrieve_and_summarize(question, ticker=ticker)
        except Exception as exc:
            return {"answer": str(exc), "sources": [], "query": question, "avg_score": 0.0}

    def _research_macro(self, retriever) -> dict:
        question = "What is the Fed's current stance on interest rates and forward guidance?"
        try:
            return retriever.retrieve_and_summarize(question, doc_type="fed_minutes")
        except Exception as exc:
            return {"answer": str(exc), "sources": [], "query": question, "avg_score": 0.0}

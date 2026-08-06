"""
FinancialRetriever: embed query → Qdrant metadata-filtered search → LLM synthesis.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from rag.config import (
    COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_LOCAL_PATH,
    SYNTHESIS_MODEL, TOP_K, embedding_model, embedding_provider,
)
from rag.sources import DocumentMetadata, RetrievedChunk

log = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """\
You are a financial research assistant. Answer the question using ONLY the provided context excerpts.
For each claim, note which document it comes from.
If the context doesn't contain the answer, say "Not found in ingested documents."

Question: {query}

Context:
{formatted_chunks}

Answer with citations (e.g. [AAPL 10-K FY2023]):"""


class FinancialRetriever:
    """
    Retrieves grounded financial context from Qdrant and synthesizes answers
    using the Anthropic Claude API (already a project dependency).
    """

    def __init__(
        self,
        collection_name: str = COLLECTION_NAME,
        top_k: int = TOP_K,
    ) -> None:
        self.collection_name = collection_name
        self.top_k = top_k
        self._client = None
        self._embedder = None

    # ── Lazy initialisation ───────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            if QDRANT_LOCAL_PATH:
                # Local file-based mode — no Docker required
                self._client = QdrantClient(path=QDRANT_LOCAL_PATH)
            else:
                self._client = QdrantClient(
                    host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY,
                )
        return self._client

    def _get_embedder(self):
        if self._embedder is None:
            provider = embedding_provider()
            model = embedding_model()
            if provider == "openai":
                from langchain_openai import OpenAIEmbeddings
                self._embedder = OpenAIEmbeddings(model=model)
            else:
                from langchain_community.embeddings import HuggingFaceEmbeddings
                self._embedder = HuggingFaceEmbeddings(model_name=model)
        return self._embedder

    def _check_collection(self) -> bool:
        """Return True if the collection exists and has at least one document."""
        try:
            client = self._get_client()
            existing = [c.name for c in client.get_collections().collections]
            if self.collection_name not in existing:
                return False
            info = client.get_collection(self.collection_name)
            return (info.points_count or 0) > 0
        except Exception:
            return False

    # ── Core retrieval ────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        ticker: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[RetrievedChunk]:
        """
        Embed query, run Qdrant similarity search with optional metadata filters,
        return list of RetrievedChunk sorted by score descending.

        Raises RuntimeError if no documents are ingested yet.
        """
        if not self._check_collection():
            raise RuntimeError(
                "No documents ingested yet. Run `python -m rag.ingest` first."
            )

        k = top_k or self.top_k
        query_vec = self._get_embedder().embed_query(query)

        # Build metadata filter
        must_conditions = []
        if ticker or doc_type:
            from qdrant_client.models import FieldCondition, Filter, MatchValue
            if ticker:
                must_conditions.append(
                    FieldCondition(key="ticker", match=MatchValue(value=ticker))
                )
            if doc_type:
                must_conditions.append(
                    FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
                )

        search_filter = None
        if must_conditions:
            from qdrant_client.models import Filter
            search_filter = Filter(must=must_conditions)

        # Fetch 4× candidates so the cross-encoder has room to rerank
        response = self._get_client().query_points(
            collection_name=self.collection_name,
            query=query_vec,
            query_filter=search_filter,
            limit=k * 4,
            with_payload=True,
        )

        chunks = []
        for hit in response.points:
            payload = hit.payload or {}
            meta = DocumentMetadata(
                ticker=payload.get("ticker"),
                doc_type=payload.get("doc_type", "unknown"),
                period=payload.get("period"),
                filing_date=payload.get("filing_date"),
                source_url=payload.get("source_url"),
                file_name=payload.get("file_name", ""),
            )
            chunks.append(RetrievedChunk(
                text=payload.get("text", ""),
                metadata=meta,
                score=float(hit.score),
            ))

        return self._rerank(query, chunks, k)

    def retrieve_and_summarize(
        self,
        query: str,
        ticker: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> dict:
        """
        Retrieve top_k chunks, synthesize a grounded answer via LLM.

        Returns:
            {
                "answer": str,
                "sources": list[RetrievedChunk],
                "query": str,
                "avg_score": float,
            }
        """
        try:
            chunks = self.retrieve(query, ticker=ticker, doc_type=doc_type)
        except RuntimeError as exc:
            return {"answer": str(exc), "sources": [], "query": query, "avg_score": 0.0}

        if not chunks:
            return {
                "answer": "Not found in ingested documents.",
                "sources": [],
                "query": query,
                "avg_score": 0.0,
            }

        formatted = "\n\n".join(
            f"{c.citation()} (score {c.score:.2f}):\n{c.text[:800]}"
            for c in chunks
        )
        prompt = SYNTHESIS_PROMPT.format(query=query, formatted_chunks=formatted)

        avg_score = sum(c.score for c in chunks) / len(chunks)
        t0 = time.time()
        answer = self._synthesize(prompt, avg_score=avg_score)
        result = {
            "answer": answer,
            "sources": chunks,
            "query": query,
            "avg_score": round(avg_score, 3),
        }
        self._trace(query, chunks, answer, time.time() - t0)
        return result

    def collection_stats(self) -> dict:
        """Return collection name, doc count, and unique tickers."""
        try:
            client = self._get_client()
            existing = [c.name for c in client.get_collections().collections]
            if self.collection_name not in existing:
                return {"name": self.collection_name, "doc_count": 0, "tickers": []}

            info = client.get_collection(self.collection_name)
            count = info.points_count or 0

            # Scroll to collect unique tickers (up to 1000 points)
            tickers: set[str] = set()
            try:
                scroll_result, _ = client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    with_payload=["ticker"],
                )
                for point in scroll_result:
                    t = (point.payload or {}).get("ticker")
                    if t:
                        tickers.add(t)
            except Exception:
                pass

            return {
                "name": self.collection_name,
                "doc_count": count,
                "tickers": sorted(tickers),
            }
        except Exception as exc:
            log.debug("collection_stats failed: %s", exc)
            return {"name": self.collection_name, "doc_count": 0, "tickers": []}

    # ── Cross-encoder re-ranking ──────────────────────────────────────────────

    def _rerank(self, query: str, chunks: list, top_k: int) -> list:
        if not chunks:
            return chunks
        try:
            from sentence_transformers import CrossEncoder
            if not hasattr(self, "_cross_encoder"):
                # ponytail: lazy singleton; swap model name for a larger one if precision matters
                self._cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            pairs = [[query, c.text[:512]] for c in chunks]
            scores = self._cross_encoder.predict(pairs)
            ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
            # Write cross-encoder score back so avg_score in retrieve_and_summarize
            # reflects post-rerank quality, not stale dense similarity (P1-5 fix)
            top = ranked[:top_k]
            for ce_score, chunk in top:
                chunk.score = float(ce_score)
            return [c for _, c in top]
        except Exception as exc:
            log.debug("Re-ranking unavailable, falling back to dense scores: %s", exc)
            return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]

    # ── Call tracing ──────────────────────────────────────────────────────────

    def _trace(self, query: str, chunks: list, answer: str, latency_s: float) -> None:
        try:
            trace_path = Path("output/rag_traces.jsonl")
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "query": query,
                "n_chunks": len(chunks),
                "avg_score": round(sum(c.score for c in chunks) / len(chunks), 3) if chunks else 0,
                "top_score": round(chunks[0].score, 3) if chunks else 0,
                "latency_s": round(latency_s, 2),
                "answer_preview": answer[:200],
                "tickers": list({c.metadata.ticker for c in chunks if c.metadata.ticker}),
            }
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass  # tracing must never break the hot path

    # ── LLM synthesis (Anthropic) ─────────────────────────────────────────────

    def _synthesize(self, prompt: str, avg_score: float = 1.0) -> str:
        """
        Synthesize answer via Anthropic with prompt caching + model routing.
        Routes to escalation model when retrieval confidence is low.
        """
        from rag.config import ESCALATION_MODEL, ESCALATION_THRESHOLD
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            # Route: low retrieval confidence → escalate to stronger model
            model = ESCALATION_MODEL if avg_score < ESCALATION_THRESHOLD else SYNTHESIS_MODEL
            msg = client.messages.create(
                model=model,
                max_tokens=1024,
                system=[{
                    "type": "text",
                    "text": (
                        "You are a financial research assistant. Answer questions using ONLY "
                        "the provided context excerpts. Cite documents as [TICKER DOC_TYPE PERIOD]. "
                        "If context doesn't contain the answer, say 'Not found in ingested documents.'"
                    ),
                    # ponytail: cache_control caches this system prompt across calls; saves ~200 tokens/call
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": prompt}],
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
            )
            return msg.content[0].text if msg.content else "No response from LLM."
        except Exception as exc:
            log.warning("LLM synthesis failed: %s", exc)
            return f"Synthesis unavailable: {exc}"

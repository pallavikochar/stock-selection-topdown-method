"""
FinancialRetriever: embed query → Qdrant metadata-filtered search → LLM synthesis.
"""

from __future__ import annotations

import logging
import os
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

        results = self._get_client().search(
            collection_name=self.collection_name,
            query_vector=query_vec,
            query_filter=search_filter,
            limit=k,
            with_payload=True,
        )

        chunks = []
        for hit in results:
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

        return sorted(chunks, key=lambda c: c.score, reverse=True)

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

        answer = self._synthesize(prompt)
        avg_score = sum(c.score for c in chunks) / len(chunks)

        return {
            "answer": answer,
            "sources": chunks,
            "query": query,
            "avg_score": round(avg_score, 3),
        }

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

    # ── LLM synthesis (Anthropic) ─────────────────────────────────────────────

    def _synthesize(self, prompt: str) -> str:
        """Send prompt to Anthropic Claude and return the answer text."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            msg = client.messages.create(
                model=SYNTHESIS_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text if msg.content else "No response from LLM."
        except Exception as exc:
            log.warning("LLM synthesis failed: %s", exc)
            return f"Synthesis unavailable: {exc}"

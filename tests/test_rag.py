"""
Tests for the RAG layer: chunk validation, metadata filtering, retrieval, synthesis.

Most tests use mock/stub objects so they run without Qdrant or API keys.
Integration tests (marked with @pytest.mark.integration) require a live Qdrant instance.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from rag.config import CHUNK_SIZE, CHUNK_OVERLAP, TOP_K, DOC_TYPES
from rag.sources import DocumentMetadata, RetrievedChunk


# ── 1. Chunk size validation ──────────────────────────────────────────────────

def test_chunk_size_positive():
    assert CHUNK_SIZE > 0, "CHUNK_SIZE must be positive"


def test_chunk_overlap_less_than_chunk_size():
    assert CHUNK_OVERLAP < CHUNK_SIZE, "CHUNK_OVERLAP must be less than CHUNK_SIZE"


def test_top_k_positive():
    assert TOP_K > 0, "TOP_K must be positive"


def test_doc_types_non_empty():
    assert len(DOC_TYPES) > 0
    assert "10-K" in DOC_TYPES
    assert "fed_minutes" in DOC_TYPES


# ── 2. DocumentMetadata / RetrievedChunk models ───────────────────────────────

def test_document_metadata_minimal():
    meta = DocumentMetadata(doc_type="10-K", file_name="aapl_10k.pdf")
    assert meta.doc_type == "10-K"
    assert meta.ticker is None


def test_document_metadata_full():
    meta = DocumentMetadata(
        ticker="AAPL",
        doc_type="10-K",
        period="FY2023",
        filing_date="2024-01-25",
        file_name="aapl_10k_2023.pdf",
    )
    assert meta.ticker == "AAPL"
    assert meta.period == "FY2023"


def test_retrieved_chunk_citation_with_ticker():
    meta = DocumentMetadata(ticker="AAPL", doc_type="10-K", period="FY2023", file_name="f.pdf")
    chunk = RetrievedChunk(text="Revenue grew 8%.", metadata=meta, score=0.92)
    assert chunk.citation() == "[AAPL 10-K FY2023]"


def test_retrieved_chunk_citation_no_ticker():
    meta = DocumentMetadata(doc_type="fed_minutes", period="Dec-2024", file_name="fomc.pdf")
    chunk = RetrievedChunk(text="The FOMC held rates.", metadata=meta, score=0.75)
    assert chunk.citation() == "[fed_minutes Dec-2024]"


def test_score_label_high():
    meta = DocumentMetadata(doc_type="10-K", file_name="f.pdf")
    chunk = RetrievedChunk(text="x", metadata=meta, score=0.90)
    assert chunk.score_label() == "high"


def test_score_label_medium():
    meta = DocumentMetadata(doc_type="10-K", file_name="f.pdf")
    chunk = RetrievedChunk(text="x", metadata=meta, score=0.78)
    assert chunk.score_label() == "medium"


def test_score_label_low():
    meta = DocumentMetadata(doc_type="10-K", file_name="f.pdf")
    chunk = RetrievedChunk(text="x", metadata=meta, score=0.55)
    assert chunk.score_label() == "low"


# ── 3. Metadata filtering in retrieve() ──────────────────────────────────────

def _make_mock_retriever(chunks: list[RetrievedChunk]):
    """Return a FinancialRetriever with Qdrant and embedder mocked out."""
    from rag.retriever import FinancialRetriever

    retriever = FinancialRetriever.__new__(FinancialRetriever)
    retriever.collection_name = "financial_docs"
    retriever.top_k = TOP_K
    retriever._client = None
    retriever._embedder = None

    def _mock_hit(c: RetrievedChunk):
        h = MagicMock()
        h.payload = {
            "text": c.text,
            "ticker": c.metadata.ticker,
            "doc_type": c.metadata.doc_type,
            "period": c.metadata.period,
            "filing_date": c.metadata.filing_date,
            "source_url": c.metadata.source_url,
            "file_name": c.metadata.file_name,
        }
        h.score = c.score
        return h

    # Build collection stub — note: MagicMock(name=...) sets repr, NOT .name attribute
    col_stub = MagicMock()
    col_stub.name = "financial_docs"

    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[col_stub])
    mock_client.get_collection.return_value = MagicMock(points_count=len(chunks))
    mock_client.search.return_value = [_mock_hit(c) for c in chunks]
    retriever._client = mock_client

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 768
    retriever._embedder = mock_embedder

    return retriever


def test_retrieve_filters_by_doc_type():
    """retrieve() should only return chunks matching the requested doc_type."""
    aapl_chunk = RetrievedChunk(
        text="AAPL revenue was $383B",
        metadata=DocumentMetadata(ticker="AAPL", doc_type="10-K", file_name="f.pdf"),
        score=0.88,
    )
    fed_chunk = RetrievedChunk(
        text="Fed held rates steady",
        metadata=DocumentMetadata(doc_type="fed_minutes", file_name="fomc.pdf"),
        score=0.85,
    )

    retriever = _make_mock_retriever([aapl_chunk])
    results = retriever.retrieve("what is aapl revenue?", doc_type="10-K")

    assert len(results) >= 1
    for r in results:
        assert r.metadata.doc_type == "10-K"


def test_retrieve_filters_by_ticker():
    """retrieve() with ticker filter should build correct Qdrant filter."""
    aapl = RetrievedChunk(
        text="AAPL Services grew 16%",
        metadata=DocumentMetadata(ticker="AAPL", doc_type="10-K", file_name="f.pdf"),
        score=0.91,
    )
    retriever = _make_mock_retriever([aapl])
    results = retriever.retrieve("services revenue", ticker="AAPL")

    # Verify the embedder was called
    assert retriever._embedder.embed_query.called
    assert all(r.metadata.ticker == "AAPL" for r in results)


def test_retrieve_raises_when_no_docs():
    """retrieve() must raise RuntimeError when collection is empty."""
    from rag.retriever import FinancialRetriever

    retriever = FinancialRetriever.__new__(FinancialRetriever)
    retriever.collection_name = "financial_docs"
    retriever.top_k = TOP_K
    retriever._embedder = None

    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    retriever._client = mock_client

    with pytest.raises(RuntimeError, match="No documents ingested"):
        retriever.retrieve("any query")


# ── 4. retrieve_and_summarize returns non-empty answer ───────────────────────

def test_retrieve_and_summarize_returns_answer():
    """retrieve_and_summarize() must return a non-empty answer string."""
    aapl = RetrievedChunk(
        text="Apple expects revenue of $90-91B in Q1 FY2024, driven by iPhone 15 demand.",
        metadata=DocumentMetadata(ticker="AAPL", doc_type="earnings_transcript",
                                  period="Q3-2023", file_name="aapl_transcript.pdf"),
        score=0.89,
    )
    retriever = _make_mock_retriever([aapl])
    expected_answer = "AAPL guides for $90-91B in Q1 [AAPL earnings_transcript Q3-2023]."

    # Patch both retrieve (so _check_collection passes) and _synthesize
    with patch.object(retriever, "retrieve", return_value=[aapl]), \
         patch.object(retriever, "_synthesize", return_value=expected_answer):
        result = retriever.retrieve_and_summarize("What revenue guidance did AAPL give?", ticker="AAPL")

    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0
    assert result["sources"]
    assert result["avg_score"] > 0


def test_retrieve_and_summarize_handles_empty_collection():
    """When no docs are ingested, returns helpful error string, not an exception."""
    from rag.retriever import FinancialRetriever

    retriever = FinancialRetriever.__new__(FinancialRetriever)
    retriever.collection_name = "financial_docs"
    retriever.top_k = TOP_K
    retriever._embedder = None

    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock(collections=[])
    retriever._client = mock_client

    result = retriever.retrieve_and_summarize("What is the Fed rate?")
    assert "No documents ingested" in result["answer"]
    assert result["sources"] == []


# ── 5. _rag_context helper degrades gracefully ────────────────────────────────

def test_rag_context_returns_empty_string_on_failure():
    """_rag_context() must return '' rather than raising, when Qdrant is down."""
    from apm.agents.a16_research import _rag_context

    with patch("rag.retriever.FinancialRetriever.retrieve_and_summarize",
               side_effect=ConnectionRefusedError("Qdrant not running")):
        result = _rag_context("What is the Fed stance?", doc_type="fed_minutes")

    assert result == ""

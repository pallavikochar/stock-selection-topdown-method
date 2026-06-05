"""Metadata schema and result types for RAG documents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    ticker: Optional[str] = None       # e.g. "AAPL" — None for macro docs
    doc_type: str                       # one of config.DOC_TYPES
    period: Optional[str] = None       # e.g. "Q3-2024", "FY2023"
    filing_date: Optional[str] = None  # ISO date string
    source_url: Optional[str] = None
    file_name: str


class RetrievedChunk(BaseModel):
    text: str
    metadata: DocumentMetadata
    score: float  # cosine similarity score from Qdrant

    def citation(self) -> str:
        """Return a human-readable citation label, e.g. '[AAPL 10-K FY2023]'."""
        parts = []
        if self.metadata.ticker:
            parts.append(self.metadata.ticker)
        parts.append(self.metadata.doc_type)
        if self.metadata.period:
            parts.append(self.metadata.period)
        return "[" + " ".join(parts) + "]"

    def score_label(self) -> str:
        """Return 'high', 'medium', or 'low' based on cosine similarity score."""
        if self.score >= 0.85:
            return "high"
        if self.score >= 0.70:
            return "medium"
        return "low"

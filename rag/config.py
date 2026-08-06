"""All RAG configuration in one place — override via environment variables."""

from __future__ import annotations

import os

# Vector DB
COLLECTION_NAME: str = os.getenv("RAG_COLLECTION", "financial_docs")
QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY") or None
# Local file-based mode (no Docker needed) — set QDRANT_LOCAL_PATH to enable
QDRANT_LOCAL_PATH: str | None = os.getenv("QDRANT_LOCAL_PATH", "./qdrant_storage")

# Chunking
CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "512"))
CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "64"))

# Retrieval
TOP_K: int = int(os.getenv("RAG_TOP_K", "6"))

# Embedding — "openai" if OPENAI_API_KEY is set, otherwise "local" (sentence-transformers)
EMBEDDING_MODEL_OPENAI: str = "text-embedding-3-small"
EMBEDDING_MODEL_LOCAL: str = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM_OPENAI: int = 1536
EMBEDDING_DIM_LOCAL: int = 768

# Synthesis LLM — uses Anthropic (already a project dependency) by default
SYNTHESIS_MODEL: str = os.getenv("RAG_SYNTHESIS_MODEL", "claude-haiku-4-5-20251001")
# Escalation model for low-confidence retrievals (avg_score < ESCALATION_THRESHOLD)
ESCALATION_MODEL: str = os.getenv("RAG_ESCALATION_MODEL", "claude-sonnet-5")
ESCALATION_THRESHOLD: float = float(os.getenv("RAG_ESCALATION_THRESHOLD", "0.55"))

# Document types supported
DOC_TYPES: list[str] = [
    "10-K", "10-Q", "earnings_transcript", "fed_minutes", "analyst_report"
]


def embedding_provider() -> str:
    """Return 'openai' if a valid OPENAI_API_KEY is set, else 'local'."""
    key = os.getenv("OPENAI_API_KEY", "")
    return "openai" if key.startswith("sk-") else "local"


def embedding_dim() -> int:
    return EMBEDDING_DIM_OPENAI if embedding_provider() == "openai" else EMBEDDING_DIM_LOCAL


def embedding_model() -> str:
    return EMBEDDING_MODEL_OPENAI if embedding_provider() == "openai" else EMBEDDING_MODEL_LOCAL

"""
Document ingestion pipeline: load → chunk → embed → upsert to Qdrant.

Usage:
    python -m rag.ingest --ticker AAPL --doc_type 10-K --year 2023
    python -m rag.ingest --file data/raw/fed_minutes_dec2024.pdf --doc_type fed_minutes
    python -m rag.ingest --all   # ingest everything in data/raw/
"""

from __future__ import annotations

import argparse
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

DATA_RAW = Path("data/raw")


# ── Document loading ──────────────────────────────────────────────────────────

def load_document(path: str) -> list:
    """Load a file into LangChain Documents. Supports PDF, TXT, CSV."""
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader

    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        loader = PyPDFLoader(str(p))
    elif suffix == ".csv":
        loader = CSVLoader(str(p))
    else:
        loader = TextLoader(str(p), encoding="utf-8")
    return loader.load()


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_documents(
    docs: list,
    metadata: dict,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list:
    """Split documents into overlapping chunks and attach metadata to each."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from rag.config import CHUNK_SIZE, CHUNK_OVERLAP

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or CHUNK_SIZE,
        chunk_overlap=chunk_overlap or CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    for chunk in chunks:
        chunk.metadata.update(metadata)
    return chunks


# ── Embedding ─────────────────────────────────────────────────────────────────

def _get_embedder():
    """Return an embedder based on available API keys."""
    from rag.config import embedding_provider, embedding_model

    provider = embedding_provider()
    model = embedding_model()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)
    else:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=model)


# ── Qdrant upsert ─────────────────────────────────────────────────────────────

def _ensure_collection(client, collection_name: str) -> None:
    """Create the Qdrant collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams
    from rag.config import embedding_dim

    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=embedding_dim(), distance=Distance.COSINE),
        )
        log.info("Created Qdrant collection '%s' (dim=%d)", collection_name, embedding_dim())


def embed_and_upsert(
    chunks: list,
    collection_name: str | None = None,
) -> int:
    """Embed chunks and upsert into Qdrant. Returns number of chunks ingested."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
    from rag.config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, QDRANT_LOCAL_PATH, COLLECTION_NAME

    col = collection_name or COLLECTION_NAME
    if QDRANT_LOCAL_PATH:
        client = QdrantClient(path=QDRANT_LOCAL_PATH)
    else:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)
    _ensure_collection(client, col)

    embedder = _get_embedder()
    texts = [c.page_content for c in chunks]
    vectors = embedder.embed_documents(texts)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={**chunk.metadata, "text": chunk.page_content},
        )
        for chunk, vec in zip(chunks, vectors)
    ]

    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=col, points=points[i : i + batch_size])

    return len(points)


# ── SEC EDGAR auto-download ───────────────────────────────────────────────────

def download_sec_filing(ticker: str, doc_type: str, year: int) -> Optional[Path]:
    """Download a 10-K or 10-Q from SEC EDGAR. Returns path to downloaded file."""
    try:
        from sec_edgar_downloader import Downloader
    except ImportError:
        log.error("sec-edgar-downloader not installed. Run: uv add sec-edgar-downloader")
        return None

    dl = Downloader("ProjectAPM", "admin@projectapm.local", str(DATA_RAW))
    form = "10-K" if "K" in doc_type.upper() else "10-Q"

    try:
        dl.get(form, ticker, after=f"{year}-01-01", before=f"{year}-12-31", limit=1)
        # SEC downloads to sec-edgar-filings/{ticker}/{form}/
        filing_dir = DATA_RAW / "sec-edgar-filings" / ticker / form
        if filing_dir.exists():
            txts = list(filing_dir.rglob("*.txt")) + list(filing_dir.rglob("*.htm"))
            if txts:
                return txts[0]
    except Exception as exc:
        log.warning("SEC EDGAR download failed for %s %s %d: %s", ticker, doc_type, year, exc)
    return None


# ── Top-level ingest ──────────────────────────────────────────────────────────

def ingest_file(
    file_path: str,
    doc_type: str,
    ticker: Optional[str] = None,
    period: Optional[str] = None,
    collection_name: str | None = None,
) -> int:
    """Load, chunk, embed, and upsert a single file. Returns chunks ingested."""
    from rag.config import COLLECTION_NAME

    col = collection_name or COLLECTION_NAME
    meta = {
        "ticker": ticker,
        "doc_type": doc_type,
        "period": period,
        "file_name": Path(file_path).name,
    }
    docs = load_document(file_path)
    chunks = chunk_documents(docs, meta)
    n = embed_and_upsert(chunks, col)
    print(f"Ingested {n} chunks from {Path(file_path).name} into collection '{col}'")
    return n


def ingest_all(directory: str = str(DATA_RAW), collection_name: str | None = None) -> int:
    """Ingest all supported files in a directory."""
    total = 0
    for path in Path(directory).rglob("*"):
        if path.suffix.lower() in (".pdf", ".txt", ".csv") and path.is_file():
            # Infer doc_type from filename heuristics
            name = path.stem.lower()
            if "10-k" in name or "10k" in name:
                doc_type = "10-K"
            elif "10-q" in name or "10q" in name:
                doc_type = "10-Q"
            elif "transcript" in name or "earnings" in name:
                doc_type = "earnings_transcript"
            elif "fed" in name or "minutes" in name or "fomc" in name:
                doc_type = "fed_minutes"
            else:
                doc_type = "analyst_report"
            try:
                total += ingest_file(str(path), doc_type, collection_name=collection_name)
            except Exception as exc:
                log.warning("Skipped %s: %s", path.name, exc)
    return total


# ── CLI entry-point ───────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Ingest financial documents into Qdrant")
    parser.add_argument("--ticker", help="Ticker symbol (e.g. AAPL)")
    parser.add_argument("--doc_type", help="Document type (10-K, 10-Q, fed_minutes, …)")
    parser.add_argument("--year", type=int, help="Fiscal year for SEC auto-download")
    parser.add_argument("--file", help="Path to a specific file to ingest")
    parser.add_argument("--all", action="store_true", help="Ingest all files in data/raw/")
    parser.add_argument("--period", help="Period label, e.g. FY2023 or Q3-2024")
    args = parser.parse_args()

    if args.all:
        n = ingest_all()
        print(f"Total: {n} chunks ingested")
    elif args.file:
        ingest_file(args.file, args.doc_type or "analyst_report", args.ticker, args.period)
    elif args.ticker and args.doc_type and args.year:
        path = download_sec_filing(args.ticker, args.doc_type, args.year)
        if path:
            ingest_file(str(path), args.doc_type, args.ticker, f"FY{args.year}")
        else:
            print("Download failed — check logs.")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()

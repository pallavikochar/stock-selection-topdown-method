"""
Bootstrap RAG: download SEC 10-K filings for a sample universe + last 3 Fed minutes.
Run from the project root:
    python scripts/bootstrap_rag.py

Requires:
    - Qdrant running: docker run -p 6333:6333 qdrant/qdrant
    - pip install sec-edgar-downloader (or: uv add sec-edgar-downloader)
    - ANTHROPIC_API_KEY in .env (for synthesis); OPENAI_API_KEY optional (better embeddings)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE_TICKERS = ["AAPL", "SPG", "O", "PLD"]  # Tech + REITs (Green Street relevance)

FED_MINUTES_URLS = [
    # Last 3 FOMC minutes (plain-text versions from federalreserve.gov)
    "https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20250129.pdf",
    "https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20241113.pdf",
    "https://www.federalreserve.gov/monetarypolicy/files/fomcminutes20240918.pdf",
]

DATA_RAW = Path("data/raw")


def _download_url(url: str, dest: Path) -> bool:
    """Download a URL to a local file. Returns True on success."""
    try:
        import httpx
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return True
    except Exception as exc:
        print(f"  ✗ Download failed: {url} — {exc}")
        return False


def bootstrap_sec_filings() -> list[tuple[Path, str, str]]:
    """Download 10-K filings for sample tickers. Returns list of (path, doc_type, ticker)."""
    from rag.ingest import download_sec_filing
    results = []
    for ticker in SAMPLE_TICKERS:
        print(f"  Downloading {ticker} 10-K 2023…", end=" ", flush=True)
        path = download_sec_filing(ticker, "10-K", 2023)
        if path:
            print(f"✓ {path.name}")
            results.append((path, "10-K", ticker))
        else:
            print("✗ not found (EDGAR may require a delay; try again later)")
    return results


def bootstrap_fed_minutes() -> list[tuple[Path, str, None]]:
    """Download last 3 Fed minutes PDFs. Returns list of (path, doc_type, None)."""
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    results = []
    for url in FED_MINUTES_URLS:
        filename = url.split("/")[-1]
        dest = DATA_RAW / filename
        print(f"  Downloading Fed minutes {filename}…", end=" ", flush=True)
        if _download_url(url, dest):
            print("✓")
            results.append((dest, "fed_minutes", None))
        else:
            print("✗")
    return results


def main() -> None:
    print("\n═══ Project APM — RAG Bootstrap ═══\n")

    print("① Starting Qdrant check…")
    try:
        from qdrant_client import QdrantClient
        from rag.config import QDRANT_LOCAL_PATH, QDRANT_HOST, QDRANT_PORT
        if QDRANT_LOCAL_PATH:
            _check = QdrantClient(path=QDRANT_LOCAL_PATH)
            _check.get_collections()
            del _check  # release lock before ingestion opens its own client
            print(f"  ✓ Qdrant local mode (path={QDRANT_LOCAL_PATH})\n")
        else:
            _check = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            _check.get_collections()
            del _check
            print("  ✓ Qdrant server is running\n")
    except Exception as exc:
        print(f"  ✗ Cannot connect to Qdrant: {exc}")
        print("  Either set QDRANT_LOCAL_PATH in .env or start Docker: docker run -p 6333:6333 qdrant/qdrant\n")
        sys.exit(1)

    print("② Downloading SEC 10-K filings…")
    sec_files = bootstrap_sec_filings()
    print()

    print("③ Downloading Fed minutes PDFs…")
    fed_files = bootstrap_fed_minutes()
    print()

    all_files = sec_files + fed_files
    if not all_files:
        print("No files downloaded. Exiting.")
        sys.exit(1)

    print(f"④ Ingesting {len(all_files)} files into Qdrant…")
    from rag.ingest import ingest_file
    total_chunks = 0
    rows = []
    for path, doc_type, ticker in all_files:
        period = "FY2023" if doc_type == "10-K" else None
        try:
            n = ingest_file(str(path), doc_type, ticker, period)
            total_chunks += n
            rows.append((path.name, doc_type, ticker or "—", n, "✓"))
        except Exception as exc:
            rows.append((path.name, doc_type, ticker or "—", 0, f"✗ {exc}"))

    print()
    print("═══ Ingestion Summary ═══")
    print(f"{'File':<40} {'Type':<20} {'Ticker':<8} {'Chunks':>6}  Status")
    print("─" * 85)
    for file_name, doc_type, ticker, n, status in rows:
        print(f"{file_name:<40} {doc_type:<20} {ticker:<8} {n:>6}  {status}")
    print("─" * 85)
    print(f"{'Total':<40} {'':20} {'':8} {total_chunks:>6}")
    print()
    print(f"✓ Bootstrap complete. {total_chunks} chunks ingested into 'financial_docs' collection.")
    print("  Try a query: python -m rag.ingest --help")
    print()


if __name__ == "__main__":
    main()

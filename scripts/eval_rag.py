"""
RAG evaluation: precision@5 + groundedness on a labeled question set.
Run from project root: python scripts/eval_rag.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv; load_dotenv()

# Labeled queries: (question, [keywords that must appear in retrieved chunks], ticker_filter)
EVAL_SET = [
    ("What revenue guidance did Apple management give?",
     ["revenue", "billion", "growth", "fiscal"], "AAPL"),
    ("What are Apple's key risk factors?",
     ["risk", "competition", "supply chain", "regulatory"], "AAPL"),
    ("What is Apple's capital expenditure outlook?",
     ["capital", "expenditure", "investment", "property"], "AAPL"),
    ("What does Apple say about services revenue?",
     ["services", "revenue", "subscription"], "AAPL"),
    ("What is Simon Property Group's occupancy rate?",
     ["occupancy", "percent", "retail", "lease"], "SPG"),
    ("What does SPG say about tenant sales?",
     ["tenant", "sales", "per square foot", "retailer"], "SPG"),
    ("What are Realty Income's acquisition plans?",
     ["acquisition", "property", "net lease", "invest"], "O"),
    ("What is the Fed's stance on interest rates?",
     ["rate", "federal funds", "inflation", "committee"], None),
    ("What did FOMC say about inflation outlook?",
     ["inflation", "price", "percent", "target"], None),
    ("What macro risks did management discuss?",
     ["risk", "economic", "interest rate", "market"], None),
]


def precision_at_k(chunks: list, keywords: list[str], k: int = 5) -> float:
    """Fraction of top-k chunks containing at least one expected keyword."""
    hits = sum(
        any(kw.lower() in c.text.lower() for kw in keywords)
        for c in chunks[:k]
    )
    return hits / min(k, len(chunks)) if chunks else 0.0


def word_overlap_proxy(answer: str, chunks: list) -> float:
    """
    Word-overlap proxy for answer grounding.
    NOTE: This is NOT RAGAS faithfulness. RAGAS uses an NLI/LLM judge to check
    whether each answer claim is supported by context. This metric measures
    lexical overlap and rewards verbatim copying over paraphrasing.
    Cite as 'word-overlap proxy (not RAGAS)' — never compare directly to
    published RAGAS benchmarks.
    """
    if not answer or not chunks:
        return 0.0
    answer_words = set(answer.lower().split())
    scores = []
    for c in chunks:
        chunk_words = set(c.text.lower().split())
        overlap = len(answer_words & chunk_words) / max(len(answer_words), 1)
        scores.append(min(overlap * 10, 1.0))  # scale up sparse overlap
    return round(sum(scores) / len(scores), 3)


def main() -> None:
    import warnings, logging
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)

    from rag.retriever import FinancialRetriever
    r = FinancialRetriever()

    print("RAG Evaluation — precision@5 + word-overlap proxy (not RAGAS)\n")
    print(f"{'Query':<55} {'P@5':>5}  {'Ovlp':>5}  {'Chunks':>6}")
    print("─" * 80)

    p_scores, g_scores = [], []
    for query, keywords, ticker in EVAL_SET:
        try:
            result = r.retrieve_and_summarize(query, ticker=ticker)
            chunks = result["sources"]
            p = precision_at_k(chunks, keywords)
            g = word_overlap_proxy(result["answer"], chunks)
            p_scores.append(p)
            g_scores.append(g)
            label = query[:53]
            print(f"{label:<55} {p:>5.0%}  {g:>5.2f}  {len(chunks):>6}")
        except Exception as exc:
            print(f"{query[:53]:<55}  ERR: {exc}")

    print("─" * 80)
    avg_p = sum(p_scores) / len(p_scores) if p_scores else 0
    avg_g = sum(g_scores) / len(g_scores) if g_scores else 0
    n = len(p_scores)
    # Wilson score 95% CI for precision@5
    import math
    z = 1.96
    if n > 0:
        centre = (avg_p + z**2 / (2 * n)) / (1 + z**2 / n)
        half = z * math.sqrt(avg_p * (1 - avg_p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
        ci_lo, ci_hi = max(0.0, centre - half), min(1.0, centre + half)
        ci_str = f"95% CI [{ci_lo:.0%}, {ci_hi:.0%}]"
    else:
        ci_str = "n/a"
    print(f"{'AVERAGE':<55} {avg_p:>5.0%}  {avg_g:>5.2f}")
    print(f"  precision@5: {avg_p:.0%}  {ci_str}  (n={n})")
    print(f"  word-overlap proxy: {avg_g:.2f}  [NOT comparable to RAGAS faithfulness]")
    print()

    # Persist results
    out = Path("output/rag_eval.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "precision_at_5": round(avg_p, 3),
        "precision_at_5_ci_95_lo": round(ci_lo if n > 0 else 0, 3),
        "precision_at_5_ci_95_hi": round(ci_hi if n > 0 else 0, 3),
        "avg_word_overlap_proxy": round(avg_g, 3),
        "note_word_overlap": "word-overlap proxy only; not comparable to RAGAS faithfulness",
        "n_queries": n,
    }, indent=2))
    print(f"Results saved → {out}")


if __name__ == "__main__":
    main()

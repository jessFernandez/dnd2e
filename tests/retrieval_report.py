"""Baseline retrieval report — run:  python tests/retrieval_report.py

Prints, for every golden question, the rank at which the correct page is first
retrieved, plus aggregate recall@1/3/5 and MRR. Use it to see exactly where
retrieval is silently failing and to track improvements as we tune the retriever.
Deterministic and model-free (no Ollama needed).
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))          # tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root

import rules_agent
from rules_agent import AskWorker
from golden_retrieval import GOLDEN, retrieved_urls, first_hit_rank, recall_at_k, reciprocal_rank

DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")


def main():
    if not os.path.exists(DB):
        print("rulebook DB not found:", DB)
        return
    worker = AskWorker(DB, "x", "x")
    r1 = r3 = r5 = mrr = 0.0
    misses = []
    print(f"{'rank':>4}  {'r@5':>3}  question")
    print("-" * 60)
    for q, gold in GOLDEN:
        urls = retrieved_urls(worker, q, k=12)
        rank = first_hit_rank(urls, gold)
        r1 += recall_at_k(urls, gold, 1)
        r3 += recall_at_k(urls, gold, 3)
        hit5 = recall_at_k(urls, gold, 5)
        r5 += hit5
        mrr += reciprocal_rank(urls, gold)
        tag = "ok " if hit5 else "MISS"
        print(f"{(rank if rank else '--'):>4}  {tag:>3}  {q}")
        if not hit5:
            misses.append((q, gold, urls[:5]))
    n = len(GOLDEN)
    print("-" * 60)
    print(f"recall@1 = {r1/n:.0%}   recall@3 = {r3/n:.0%}   recall@5 = {r5/n:.0%}   MRR = {mrr/n:.3f}   (n={n})")
    if misses:
        print("\nMISSES (correct page not in top 5):")
        for q, gold, top in misses:
            print(f"  • {q}")
            print(f"      want any of: {list(gold)}")
            print(f"      got top-5:   {top}")


if __name__ == "__main__":
    main()

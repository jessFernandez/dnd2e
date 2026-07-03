"""Retrieval evaluation — the quality gate for Jarvis answers.

RAG answer quality is bottlenecked by retrieval, so we assert the deterministic
(model-free) search lands the *actual answer page* — pinned in golden_retrieval.py
by page_url — in the top results. This is stronger than matching a keyword in a
retrieved title, which silently passed questions whose real answer page was never
retrieved.

Questions whose correct page currently ranks outside the top 5 are marked xfail
with the reason; as the retriever improves, those xfails should start passing
(pytest reports them as XPASS) and the marker can be removed. The aggregate test
guards recall@5 / MRR against regressions.
"""
import os
import pytest
import rules_agent
from rules_agent import AskWorker
from golden_retrieval import (
    GOLDEN, retrieved_urls, first_hit_rank, recall_at_k, reciprocal_rank,
)

DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")

# Every golden question now surfaces its correct page in the top 5.
KNOWN_MISSES = set()

# Recorded baseline (current retriever) — the suite fails if we regress below it.
# History: 84% / 0.55 (raw BM25)  →  97% / 0.74 after title-weighting, table &
# appendix penalties, PHB/DMG core-book preference, prefix matching, and a
# title-is-the-query re-rank bonus  →  100% recall@5 / 0.78 MRR after passage
# chunking (chunks_fts) let single rules out-rank the long pages that bury them.
BASELINE_RECALL5 = 0.97
BASELINE_MRR = 0.76


@pytest.mark.skipif(not os.path.exists(DB), reason="rulebook database not present")
@pytest.mark.parametrize("question,gold", GOLDEN, ids=[q for q, _ in GOLDEN])
def test_correct_page_in_top5(question, gold):
    if question in KNOWN_MISSES:
        pytest.xfail("correct page ranks outside top-5 pending retrieval-ranking fix")
    worker = AskWorker(DB, "x", question)
    urls = retrieved_urls(worker, question, k=12)
    rank = first_hit_rank(urls, gold)
    assert recall_at_k(urls, gold, 5), (
        f"{question!r}: no gold page in top-5 (rank={rank}); "
        f"want any of {list(gold)}; got {urls[:5]}"
    )


@pytest.mark.skipif(not os.path.exists(DB), reason="rulebook database not present")
def test_aggregate_recall_and_mrr_no_regression():
    worker = AskWorker(DB, "x", "x")
    r5 = mrr = 0.0
    for q, gold in GOLDEN:
        urls = retrieved_urls(worker, q, k=12)
        r5 += recall_at_k(urls, gold, 5)
        mrr += reciprocal_rank(urls, gold)
    n = len(GOLDEN)
    recall5, mean_rr = r5 / n, mrr / n
    assert recall5 >= BASELINE_RECALL5, f"recall@5 regressed: {recall5:.2%} < {BASELINE_RECALL5:.0%}"
    assert mean_rr >= BASELINE_MRR, f"MRR regressed: {mean_rr:.3f} < {BASELINE_MRR}"

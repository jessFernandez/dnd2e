"""Live answer-quality gate for Jarvis (opt-in).

Runs the full pipeline against a local Ollama model and asserts aggregate answer
quality — citation accuracy, must-have-fact coverage, and groundedness. It is
slow and model-dependent, so it only runs when explicitly enabled:

    JARVIS_LIVE=1 python -m pytest tests/test_answer_quality.py -q

The fast unit suite (retrieval, query, render, calculator) never triggers it.
Thresholds sit just under the observed llama3.1 baseline (citation 92% / facts
94% / grounded 100%) so a genuine quality regression fails the build.
"""
import os
import pytest

import rules_agent
from rules_agent import AskWorker, ollama_status, pick_default_model
from golden_retrieval import GOLDEN
from answer_eval import ANSWER_CASES, cited_pages, fact_score, looks_refused

DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
GOLD = dict(GOLDEN)

_ENABLED = os.environ.get("JARVIS_LIVE") == "1"
_OLLAMA_OK, _MODELS = ollama_status(timeout=2.0) if _ENABLED else (False, [])

pytestmark = [
    pytest.mark.skipif(not _ENABLED, reason="set JARVIS_LIVE=1 to run the live answer-quality gate"),
    pytest.mark.skipif(not os.path.exists(DB), reason="rulebook database not present"),
    pytest.mark.skipif(_ENABLED and not (_OLLAMA_OK and _MODELS),
                       reason="Ollama not running / no models installed"),
]


def _run_all():
    model = pick_default_model(_MODELS)
    cite = grounded = 0
    fn = fd = 0
    for q, groups in ANSWER_CASES:
        answer = AskWorker(DB, model, q).answer_sync()
        cite += bool(cited_pages(answer) & set(GOLD.get(q, ())))
        grounded += (not looks_refused(answer))
        hit, tot = fact_score(answer, groups)
        fn += hit; fd += tot
    n = len(ANSWER_CASES)
    return cite / n, fn / fd, grounded / n


def test_answer_quality_meets_baseline():
    citation, facts, grounded = _run_all()
    assert citation >= 0.80, f"citation accuracy regressed: {citation:.0%}"
    assert facts >= 0.85, f"fact coverage regressed: {facts:.0%}"
    assert grounded >= 0.90, f"groundedness regressed: {grounded:.0%}"

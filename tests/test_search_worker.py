"""Tests for SearchWorker — a real search failure must surface via `failed`,
distinct from a genuine zero-match (which emits results_ready([])).

SearchWorker is a QThread; calling .run() directly executes it synchronously on
the test thread, so the signals fire (DirectConnection) without an event loop.
"""
import os

import pytest
from PyQt5.QtWidgets import QApplication

import rules_agent
from app import SearchWorker

RULES_DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _capture(worker):
    got = {"failed": None, "results": "<unset>"}
    worker.failed.connect(lambda msg: got.__setitem__("failed", msg))
    worker.results_ready.connect(lambda rows: got.__setitem__("results", rows))
    worker.run()
    return got


def test_failure_emits_failed_not_empty_results(qapp, tmp_path):
    # Pointing at a directory makes db.connect() itself raise (unable to open) —
    # an error outside search_pages's own sqlite guard. The old code masked any
    # such failure as results_ready([]); now it must surface via `failed`.
    got = _capture(SearchWorker(str(tmp_path), "anything"))
    assert got["failed"] is not None          # the real error surfaced
    assert got["results"] == "<unset>"        # results_ready was NOT emitted


@needs_db
def test_success_emits_results(qapp):
    got = _capture(SearchWorker(RULES_DB, "THAC0"))
    assert got["failed"] is None              # no error on a valid query
    assert isinstance(got["results"], list)   # results_ready fired with a list

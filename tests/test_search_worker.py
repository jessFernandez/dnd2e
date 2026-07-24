"""Tests for SearchWorker — a real search failure must surface via `failed`,
distinct from a genuine zero-match (which emits results_ready([])).

SearchWorker is a QThread; calling .run() directly executes it synchronously on
the test thread, so the signals fire (DirectConnection) without an event loop.
"""
import os
import threading
import time

import pytest
from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication

import rules_agent
from app import SearchWorker

RULES_DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _capture(worker):
    got = {"failed": None, "results": "<unset>", "token": None}
    worker.failed.connect(lambda tok, msg: got.update(failed=msg, token=tok))
    worker.results_ready.connect(lambda tok, rows: got.update(results=rows, token=tok))
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


@needs_db
def test_both_signals_carry_the_token_of_the_search_they_answer(qapp, tmp_path):
    """A search cannot be cancelled — quit() only asks an event loop to exit and
    run() has none — so a superseded query still finishes and still emits. The token
    is how MainWindow tells that late reply from the one it is waiting for."""
    assert _capture(SearchWorker(RULES_DB, "THAC0", token=11))["token"] == 11
    assert _capture(SearchWorker(str(tmp_path), "anything", token=12))["token"] == 12


def test_quit_does_not_stop_a_run_with_no_event_loop(qapp):
    """Pins the Qt assumption the whole token design rests on.

    `quit()` posts to a thread's *event loop*. `SearchWorker.run()` — like this
    stand-in — overrides run() with blocking work and never calls exec_(), so there
    is no loop to post to and the call does nothing. That is why a superseded search
    is discarded on arrival rather than cancelled: it cannot be cancelled.

    Uses a controlled thread rather than a real query, so the assertion doesn't race
    the DB: a fast enough search would finish before isRunning() was read and the
    test would fail for the wrong reason.
    """
    class _Blocking(QThread):
        def __init__(self):
            super().__init__()
            self.release = threading.Event()

        def run(self):
            self.release.wait(timeout=10)

    worker = _Blocking()
    worker.start()
    while not worker.isRunning():           # wait for the thread to actually enter run()
        time.sleep(0.005)

    worker.quit()                            # a no-op here, by design
    still_running = worker.isRunning()

    worker.release.set()
    worker.wait()
    assert still_running, "quit() unexpectedly stopped a run() with no event loop"

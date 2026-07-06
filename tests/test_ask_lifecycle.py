"""Regression tests for the Jarvis (AskWorker) stop/cleanup lifecycle.

Bug: after a question finished, `worker.finished -> worker.deleteLater` destroyed
the worker's underlying C++ QThread, but MainWindow._ask_worker kept pointing at
the now-dangling Python wrapper. The next visit to Jarvis called _ask_stop, which
did `worker.isRunning()` on the dead wrapper and raised:

    RuntimeError: wrapped C/C++ object of type AskWorker has been deleted

_ask_stop only touches `self._ask_worker`, so we exercise it against a tiny
stand-in (no full MainWindow / DB needed) and simulate deleteLater with
sip.delete(), which is exactly what leaves the wrapper dangling.
"""
from types import SimpleNamespace

import pytest
from PyQt5 import sip
from PyQt5.QtWidgets import QApplication

import app
from rules_agent import AskWorker


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_ask_stop_survives_deleted_worker(qapp):
    """The reported crash: worker's C++ object was deleted; _ask_stop must not raise."""
    worker = AskWorker("db.sqlite", "llama3.1", "how does thac0 work")
    sip.delete(worker)                        # what finished -> deleteLater does
    assert sip.isdeleted(worker)

    win = SimpleNamespace(_ask_worker=worker)
    app.MainWindow._ask_stop(win)             # must not raise RuntimeError

    assert win._ask_worker is None            # stale reference dropped


def test_ask_stop_with_no_worker_is_noop(qapp):
    win = SimpleNamespace(_ask_worker=None)
    app.MainWindow._ask_stop(win)             # must not raise


def test_ask_stop_cancels_a_running_worker(qapp):
    cancelled = []
    running = SimpleNamespace(
        isRunning=lambda: True,
        cancel=lambda: cancelled.append(True),
    )
    win = SimpleNamespace(_ask_worker=running)
    app.MainWindow._ask_stop(win)
    assert cancelled == [True]                 # in-flight generation was stopped
    assert win._ask_worker is running          # a live worker is left in place


def test_ask_stop_leaves_idle_worker_alone(qapp):
    cancelled = []
    idle = SimpleNamespace(
        isRunning=lambda: False,
        cancel=lambda: cancelled.append(True),
    )
    win = SimpleNamespace(_ask_worker=idle)
    app.MainWindow._ask_stop(win)
    assert cancelled == []                     # nothing running -> nothing to cancel


def test_ask_worker_done_clears_only_the_current_worker(qapp):
    """The done-slot must not null out a newer worker if a stale signal arrives."""
    current = object()
    win = SimpleNamespace(_ask_worker=current, sender=lambda: object())
    app.MainWindow._ask_worker_done(win)
    assert win._ask_worker is current          # unrelated sender -> untouched

    win.sender = lambda: current
    app.MainWindow._ask_worker_done(win)
    assert win._ask_worker is None             # matching sender -> cleared

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
from ask_controller import Conversation
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
    app.MainWindow._ask_stop(win)             # must not raise with nothing running
    assert win._ask_worker is None            # and leaves the (absent) worker alone


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


# ── a superseded question's answer must not land ─────────────────────────────
#
# The loading page keeps the ask box enabled, so asking again mid-stream is a
# supported gesture. _ask_stop cancels the old worker, but cancel() is cooperative:
# AskWorker.run() still emits `finished` with the partial answer plus "_(stopped)_".
# Every handler therefore checks the generation its reply was issued under.

def _ask_win(conversation):
    """A stand-in carrying just what the reply handlers touch, with the real
    `_ask_view` gate bound onto it."""
    win = SimpleNamespace(
        _ask=conversation,
        status=SimpleNamespace(showMessage=lambda *a: None),
    )
    win._ask_view = app.MainWindow._ask_view.__get__(win)
    return win


def _view(into):
    """A view that records everything painted onto it, by setHtml or by JS."""
    return SimpleNamespace(
        setHtml=lambda html: into.append(html),
        page=lambda: SimpleNamespace(runJavaScript=lambda js: into.append(js)),
    )


def _asked(convo, question, painted):
    """Ask `question` on `convo`; return the generation its worker would carry."""
    return convo.begin(question, "llama3.1", ["llama3.1"], _view(painted))


def test_a_superseded_answer_is_not_recorded_or_rendered(qapp):
    convo = Conversation()
    painted = []
    first = _asked(convo, "how does thac0 work", painted)
    second = _asked(convo, "what is a saving throw", painted)
    assert first != second

    app.MainWindow._ask_finished(_ask_win(convo), first, "the old, abandoned answer")

    assert convo.pairs == [], "a superseded answer must not join the thread"
    assert painted == [], "and must not be painted over the new question's page"


def test_a_superseded_answer_is_not_paired_with_the_new_question(qapp):
    """The subtler half: record_answer reads whatever `question` currently holds, so
    a late answer would be filed under the question the reader asked *second*."""
    convo = Conversation()
    painted = []
    stale = _asked(convo, "question one", painted)
    _asked(convo, "question two", painted)

    app.MainWindow._ask_finished(_ask_win(convo), stale, "answer to question one")

    assert not any(q == "question two" for q, _a in convo.pairs)


def test_the_current_answer_still_lands(qapp):
    convo = Conversation()
    painted = []
    gen = _asked(convo, "how does thac0 work", painted)

    app.MainWindow._ask_finished(_ask_win(convo), gen,
                                 "attack matrices, mercifully abolished")

    assert convo.pairs == [("how does thac0 work", "attack matrices, mercifully abolished")]
    assert painted, "the answer page should have been rendered"


def test_superseded_deltas_status_and_errors_do_not_touch_the_page(qapp):
    convo = Conversation()
    painted = []
    stale = _asked(convo, "one", painted)
    _asked(convo, "two", painted)
    win = _ask_win(convo)

    app.MainWindow._ask_delta(win, stale, "half a sentence")
    app.MainWindow._ask_status(win, stale, "Thinking…")
    app.MainWindow._ask_failed(win, stale, "ollama fell over")

    assert painted == []


def test_leaving_the_page_abandons_an_in_flight_answer(qapp):
    """_render_ask calls Conversation.reset(); a worker still streaming into the old
    page must not paint onto the fresh one."""
    convo = Conversation()
    painted = []
    gen = _asked(convo, "one", painted)

    convo.reset()                       # the reader navigated away and back

    app.MainWindow._ask_finished(_ask_win(convo), gen, "an answer nobody is waiting for")

    assert convo.pairs == []
    assert painted == []

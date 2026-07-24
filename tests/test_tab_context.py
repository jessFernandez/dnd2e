"""Per-tab state must follow the tab, not its position.

The content tabs are movable (`setMovable(True)`). MainWindow used to keep a
parallel `self._tabs` list and index it with `currentIndex()`, which Qt reorders
on a drag without touching any list we hold. After one drag every per-tab property
resolved against the wrong tab: back/forward rewrote a different tab than the one
on screen, `current_page_url` bookmarked the wrong page, and `_close_tab` popped
another tab's context — all silently, since nothing raises.

The context now hangs on the tab's own widget (`TabContext.__init__` sets
`view._tab_context`) and is reached through `MainWindow._ctx` / `_contexts`. These
tests drive a *real* QTabWidget, because the bug lives in Qt's reordering rather
than in our code's arithmetic — a mocked tab widget would reorder exactly as the
old code assumed and prove nothing.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLabel, QTabWidget   # noqa: E402

import app                                                     # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class _View(QLabel):
    """Stands in for ContentView: TabContext only needs somewhere to attach."""


def _window(qapp, count=3):
    """A stand-in exposing the real `_ctx` / `_contexts` over a real QTabWidget."""
    tabs = QTabWidget()
    tabs.setMovable(True)
    contexts = []
    for i in range(count):
        view = _View(f"tab{i}")
        ctx = app.TabContext(view)
        ctx.current_page_url = f"PHB/page{i}.htm"
        contexts.append(ctx)
        tabs.addTab(view, f"tab{i}")
    win = SimpleWindow(tabs)
    return win, tabs, contexts


class SimpleWindow:
    """Binds the real unbound methods to a minimal object holding the tab widget."""

    def __init__(self, tabs):
        self._content_tabs = tabs

    _ctx = app.MainWindow._ctx
    _contexts = app.MainWindow._contexts
    content = app.MainWindow.content
    _nav = app.MainWindow._nav
    current_page_url = app.MainWindow.current_page_url


def test_context_follows_the_tab_after_a_drag(qapp):
    """The regression, named. Dragging the third tab to the front used to leave
    `_tabs[currentIndex()]` pointing at the first tab's context."""
    win, tabs, contexts = _window(qapp)
    tabs.setCurrentIndex(2)
    assert win._ctx() is contexts[2]
    assert win.content is contexts[2].view

    tabs.tabBar().moveTab(2, 0)                      # the reader drags it to the front

    assert tabs.currentWidget() is contexts[2].view  # Qt still shows the same tab
    assert win._ctx() is contexts[2]                 # ...and so do we
    assert win.content is contexts[2].view
    assert win._nav is contexts[2].nav
    assert win.current_page_url == "PHB/page2.htm"


def test_every_index_resolves_to_its_own_context_after_a_drag(qapp):
    win, tabs, contexts = _window(qapp)
    tabs.tabBar().moveTab(0, 2)                      # first tab dragged to the end

    for i in range(tabs.count()):
        widget = tabs.widget(i)
        assert win._ctx(i).view is widget, f"index {i} resolved to another tab"


def test_contexts_are_returned_in_visual_order(qapp):
    """Session save writes this order and restore replays it, so a dragged layout
    has to survive a restart."""
    win, tabs, contexts = _window(qapp)
    assert [c.current_page_url for c in win._contexts()] == [
        "PHB/page0.htm", "PHB/page1.htm", "PHB/page2.htm"]

    tabs.tabBar().moveTab(2, 0)

    assert [c.current_page_url for c in win._contexts()] == [
        "PHB/page2.htm", "PHB/page0.htm", "PHB/page1.htm"]


def test_setting_current_page_url_writes_to_the_visible_tab(qapp):
    win, tabs, contexts = _window(qapp)
    tabs.tabBar().moveTab(2, 0)
    tabs.setCurrentIndex(0)                          # the dragged tab is now first

    win.current_page_url = "PHB/edited.htm"

    assert contexts[2].current_page_url == "PHB/edited.htm"
    assert contexts[0].current_page_url == "PHB/page0.htm"   # untouched
    assert contexts[1].current_page_url == "PHB/page1.htm"


def test_ctx_is_none_when_there_is_no_tab(qapp):
    """`_ctx` is reachable before the first tab exists (during _build_ui) and while
    a tab is being removed, so it must answer None rather than raise."""
    win = SimpleWindow(QTabWidget())
    assert win._ctx() is None
    assert win._ctx(0) is None
    assert win._contexts() == []
    assert win.current_page_url is None


def test_removing_a_tab_takes_its_context_with_it(qapp):
    """There is no second structure to keep in step — that is the whole point."""
    win, tabs, contexts = _window(qapp)
    tabs.removeTab(1)

    remaining = win._contexts()
    assert len(remaining) == 2
    assert contexts[1] not in remaining
    assert [c.current_page_url for c in remaining] == ["PHB/page0.htm", "PHB/page2.htm"]

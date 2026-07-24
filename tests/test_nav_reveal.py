"""Opening a book page via a content link brings the browse pane along.

MainWindow._on_content_navigate is where every dnd:// link click lands. When the
destination is a book page (a rules page or a book's TOC), it now reveals the
browse pane — full-width reference screens still hide it. These exercise that
wiring against a SimpleNamespace stand-in (no real window / DB / display needed),
the same way test_ask_lifecycle drives _ask_stop.
"""
from types import SimpleNamespace

import pytest

import app

# The full-width-vs-book classification these methods rely on now lives as the
# pure navigation.takes_full_width / link_to_destination (tested directly in
# test_navigation.py); here we only check MainWindow wires the side effects to it.


# ── _reveal_nav_for in isolation ──────────────────────────────────────────────

def _reveal_win():
    shown = []
    win = SimpleNamespace(_show_sidebar=lambda: shown.append(True))
    return win, shown


def test_reveal_opens_pane_for_a_rules_page():
    win, shown = _reveal_win()
    app.MainWindow._reveal_nav_for(win, "PHB/DD01671.htm")
    assert shown == [True]


def test_reveal_opens_pane_for_a_book_toc():
    win, shown = _reveal_win()
    app.MainWindow._reveal_nav_for(win, "toc:PHB")
    assert shown == [True]


def test_reveal_leaves_full_width_screens_and_proficiencies_alone():
    win, shown = _reveal_win()
    for dest in ("dmscreen", "spells", "charactermancer", "ask", "splash",
                 "proficiencies", "proficiencies#thieving"):
        app.MainWindow._reveal_nav_for(win, dest)
    assert shown == []          # none of these should pop the pane open


# ── end-to-end through _on_content_navigate ───────────────────────────────────

def _nav_win():
    calls = {"shown": 0, "navigate": [], "newtab": 0}
    win = SimpleNamespace(
        _show_sidebar=lambda: calls.__setitem__("shown", calls["shown"] + 1),
        _navigate=lambda d: calls["navigate"].append(d),
        _new_tab=lambda show_splash=True: calls.__setitem__("newtab", calls["newtab"] + 1),
        _on_jarvis_page=lambda: False,
    )
    # Bind the real _reveal_nav_for so the reveal decision is genuinely exercised.
    win._reveal_nav_for = lambda d: app.MainWindow._reveal_nav_for(win, d)
    return win, calls


def test_book_link_opens_pane_then_navigates():
    win, calls = _nav_win()
    app.MainWindow._on_content_navigate(win, "PHB/DD01671.htm")
    assert calls["shown"] == 1
    assert calls["navigate"] == ["PHB/DD01671.htm"]
    assert calls["newtab"] == 0


def test_book_chip_link_opens_pane_for_the_toc():
    win, calls = _nav_win()
    app.MainWindow._on_content_navigate(win, "toc/PHB")     # a splash book chip
    assert calls["shown"] == 1
    assert calls["navigate"] == ["toc:PHB"]


def test_reference_screen_link_does_not_open_pane():
    win, calls = _nav_win()
    app.MainWindow._on_content_navigate(win, "screen/dmscreen")
    assert calls["shown"] == 0
    assert calls["navigate"] == ["dmscreen"]


def test_newtab_book_link_opens_pane_in_the_new_tab():
    win, calls = _nav_win()
    app.MainWindow._on_content_navigate(win, "newtab/CT/DD00123.htm")
    assert calls["newtab"] == 1
    assert calls["shown"] == 1
    assert calls["navigate"] == ["CT/DD00123.htm"]


def test_jarvis_citation_opens_pane_and_a_new_tab():
    win, calls = _nav_win()
    win._on_jarvis_page = lambda: True
    app.MainWindow._on_content_navigate(win, "MM/DD09912.htm")
    assert calls["newtab"] == 1          # citation opens beside the Q&A
    assert calls["shown"] == 1
    assert calls["navigate"] == ["MM/DD09912.htm"]


# ── the mirror image: leaving a book page closes the pane ─────────────────────
#
# _navigate hides the browse pane whenever the destination is a full-width
# reference screen (or the Proficiencies codex) — on any navigation, not just
# link clicks — so paging off a book page into one of those closes the pane,
# while book -> book keeps it open.

def _navigate_win():
    calls = {"hidden": 0, "pushed": []}
    win = SimpleNamespace(
        _render_destination=lambda d: True,
        _hide_sidebar=lambda: calls.__setitem__("hidden", calls["hidden"] + 1),
        _nav=SimpleNamespace(push=lambda d: calls["pushed"].append(d)),
        _update_nav_buttons=lambda: None,
    )
    return win, calls


def test_leaving_for_a_full_width_screen_closes_the_pane():
    for dest in ("dmscreen", "spells", "actions", "charactermancer", "ask",
                 "splash", "proficiencies", "proficiencies#thieving"):
        win, calls = _navigate_win()
        app.MainWindow._navigate(win, dest)
        assert calls["hidden"] == 1, dest


def test_staying_on_a_book_page_keeps_the_pane():
    for dest in ("PHB/DD01671.htm", "toc:PHB", "CT/DD00123.htm"):
        win, calls = _navigate_win()
        app.MainWindow._navigate(win, dest)
        assert calls["hidden"] == 0, dest


# ── closing / switching tabs reconciles the pane with the new active tab ──────
#
# Closing the book tab hands focus to another tab (currentChanged -> _on_tab_changed).
# The pane must follow that tab's content: a full-width screen closes it, a book
# page leaves it as the reader left it (switching isn't a link click).

def _tab_ctx(dest, page_url=None):
    return SimpleNamespace(
        nav=SimpleNamespace(current=lambda: dest),
        current_page_url=page_url,
    )


def _tab_win(ctx):
    calls = {"hidden": 0, "synced": []}
    win = SimpleNamespace(
        # _on_tab_changed resolves the context through the tab's widget (_ctx),
        # not by indexing a parallel list — see TabContext.
        _ctx=lambda index=None: ctx,
        _update_nav_buttons=lambda: None,
        _update_bookmark_btn=lambda: None,
        _hide_sidebar=lambda: calls.__setitem__("hidden", calls["hidden"] + 1),
        _sync_tree_selection=lambda u: calls["synced"].append(u),
    )
    return win, calls


def test_landing_on_a_full_width_tab_closes_the_pane():
    win, calls = _tab_win(_tab_ctx("dmscreen"))
    app.MainWindow._on_tab_changed(win, 0)
    assert calls["hidden"] == 1
    assert calls["synced"] == []          # no book page to select


def test_landing_on_a_book_tab_keeps_the_pane_and_syncs_the_tree():
    win, calls = _tab_win(_tab_ctx("PHB/DD01671.htm", page_url="PHB/DD01671.htm"))
    app.MainWindow._on_tab_changed(win, 0)
    assert calls["hidden"] == 0                        # pane left as-is
    assert calls["synced"] == ["PHB/DD01671.htm"]      # tree follows the page


def test_landing_on_a_toc_tab_keeps_the_pane():
    win, calls = _tab_win(_tab_ctx("toc:PHB"))
    app.MainWindow._on_tab_changed(win, 0)
    assert calls["hidden"] == 0


def test_landing_on_an_empty_tab_is_harmless():
    win, calls = _tab_win(_tab_ctx(None))              # fresh tab, nothing rendered yet
    app.MainWindow._on_tab_changed(win, 0)
    assert calls["hidden"] == 0 and calls["synced"] == []


def test_tab_change_on_an_index_with_no_context_does_nothing():
    """currentChanged fires during teardown and while a tab is being removed, when
    the index can name a widget that is already gone. _ctx returns None there."""
    calls = {"hidden": 0, "synced": []}
    win = SimpleNamespace(
        _ctx=lambda index=None: None,
        _update_nav_buttons=lambda: pytest.fail("should not run without a context"),
        _update_bookmark_btn=lambda: pytest.fail("should not run without a context"),
        _hide_sidebar=lambda: calls.__setitem__("hidden", 1),
        _sync_tree_selection=lambda u: calls["synced"].append(u),
    )
    app.MainWindow._on_tab_changed(win, -1)
    assert calls == {"hidden": 0, "synced": []}


# ── the in-place routes (ask / builder) dispatch to the right handler ─────────
#
# route_link's classification is unit-tested in test_navigation.py; here we check
# _on_content_navigate's match wires each route to the matching side effect.

def _dispatch_win():
    calls = {"ask": [], "model": [], "synced": 0, "render_ask": 0, "stop": 0, "cm": []}
    win = SimpleNamespace(
        _on_jarvis_page=lambda: False,
        _ask_question=lambda q: calls["ask"].append(q),
        _settings=SimpleNamespace(
            setValue=lambda k, v: calls["model"].append((k, v)),
            sync=lambda: calls.__setitem__("synced", calls["synced"] + 1),
        ),
        _render_ask=lambda: calls.__setitem__("render_ask", calls["render_ask"] + 1),
        _ask_stop=lambda: calls.__setitem__("stop", calls["stop"] + 1),
        _cm_action=lambda p: calls["cm"].append(p),
    )
    return win, calls


def test_ask_link_dispatches_a_decoded_question():
    win, calls = _dispatch_win()
    app.MainWindow._on_content_navigate(win, "ask/how%20does%20thac0%20work")
    assert calls["ask"] == ["how does thac0 work"]


def test_ask_setmodel_link_saves_and_rerenders():
    win, calls = _dispatch_win()
    app.MainWindow._on_content_navigate(win, "ask-setmodel/llama3.1")
    assert calls["model"] == [("askModel", "llama3.1")]
    assert calls["synced"] == 1
    assert calls["render_ask"] == 1


def test_ask_refresh_and_new_both_rerender():
    for u in ("ask-refresh", "ask-new"):
        win, calls = _dispatch_win()
        app.MainWindow._on_content_navigate(win, u)
        assert calls["render_ask"] == 1, u


def test_ask_stop_link_cancels_generation():
    win, calls = _dispatch_win()
    app.MainWindow._on_content_navigate(win, "ask-stop")
    assert calls["stop"] == 1


def test_cm_link_dispatches_the_raw_payload():
    win, calls = _dispatch_win()
    app.MainWindow._on_content_navigate(win, "cm/set-race/Elf")
    assert calls["cm"] == ["set-race/Elf"]

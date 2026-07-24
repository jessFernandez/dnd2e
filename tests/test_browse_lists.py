"""Tests for browse_lists.py — how a page looks as a row in the side lists.

Extracted from MainWindow's _show_results / _load_bookmarks / _load_topics, which
had written the same title cleanup three times. See docs/audit-2-plan.md finding 2.
"""
from types import SimpleNamespace

import pytest
from PyQt5.QtCore import Qt

import app
import browse_lists as bl
import theme


# ── display_title ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("THAC0 (Player's Handbook)",           "THAC0"),
    ("Combat-- Chapter 9 (X)",              "Combat-- Chapter 9"),
    ("Armor Class",                         "Armor Class"),          # nothing to strip
    ("Gear & Equipment",                    "Gear & Equipment"),     # '&' left alone
    ("  Spaced  (Book)  ",                  "Spaced"),
    ("",                                    ""),
    (None,                                  ""),
])
def test_display_title_strips_the_trailing_book(raw, expected):
    assert bl.display_title(raw) == expected


def test_display_title_only_strips_the_trailing_parenthetical():
    """A title with parentheses in the middle keeps them — only the suffix goes."""
    assert bl.display_title("Spells (Reversed) of the Priest (PHB)") == \
        "Spells (Reversed) of the Priest"


# ── snippet ──────────────────────────────────────────────────────────────────

def test_snippet_flattens_and_strips_fts_markers():
    assert bl.snippet("a  **match**\nover\tlines") == "a match over lines"
    assert bl.snippet("") == ""
    assert bl.snippet(None) == ""


def test_snippet_truncates_with_an_ellipsis():
    long = "x" * 200
    out = bl.snippet(long)
    assert len(out) == bl.SNIPPET_MAX - 1        # 118 chars + the ellipsis
    assert out.endswith("…")


def test_snippet_at_the_boundary_is_untouched():
    exact = "y" * bl.SNIPPET_MAX
    assert bl.snippet(exact) == exact
    assert not bl.snippet(exact).endswith("…")


# ── colours ──────────────────────────────────────────────────────────────────

def test_book_color_known_and_unknown():
    assert bl.book_color("PHB") == theme.BOOKS["PHB"].item
    assert bl.book_color("NOPE") == bl.DEFAULT_ITEM_COLOR
    assert bl.book_color("") == bl.DEFAULT_ITEM_COLOR
    assert bl.book_color(None) == bl.DEFAULT_ITEM_COLOR


# ── rows ─────────────────────────────────────────────────────────────────────

def test_page_row_without_a_snippet_is_two_lines():
    row = bl.page_row("PHB/DD01.htm", "THAC0 (Player's Handbook)", "Player's Handbook", "PHB")
    assert row.text == "  THAC0\n  Player's Handbook"
    assert row.page_url == "PHB/DD01.htm"
    assert row.color == theme.BOOKS["PHB"].item


def test_page_row_with_a_snippet_is_three_lines():
    row = bl.page_row("PHB/DD01.htm", "THAC0 (PHB)", "Player's Handbook", "PHB",
                      "the **attack** roll")
    assert row.text.splitlines() == ["  THAC0", "  Player's Handbook", "  the attack roll"]


def test_page_row_falls_back_to_the_url_when_untitled():
    row = bl.page_row("PHB/DD01.htm", "", "", "")
    assert row.text.startswith("  PHB/DD01.htm")
    assert row.color == bl.DEFAULT_ITEM_COLOR


def test_search_rows_maps_db_search_pages_output():
    rows = [
        ("PHB/a.htm", "Armor (PHB)", "Player's Handbook", "PHB", "plate **mail**"),
        ("MM/b.htm",  "Ogre (MM)",   "Monstrous Manual",  "MM",  ""),
    ]
    out = bl.search_rows(rows)
    assert [r.page_url for r in out] == ["PHB/a.htm", "MM/b.htm"]
    assert out[0].text.endswith("plate mail")
    assert out[1].text == "  Ogre\n  Monstrous Manual"     # no snippet line
    assert out[1].color == theme.BOOKS["MM"].item


# ── tab labels ───────────────────────────────────────────────────────────────

def test_tab_labels():
    assert bl.results_tab_label(0) == "Results (0)"
    assert bl.results_tab_label(12) == "Results (12)"
    # bookmarks drops the count at zero — "(0)" reads like something went wrong
    assert bl.bookmarks_tab_label(0) == "Bookmarks"
    assert bl.bookmarks_tab_label(3) == "Bookmarks (3)"


# ── the Qt wiring (stand-ins, no window) ─────────────────────────────────────
#
# _show_results / _load_bookmarks were rewritten to delegate here, so check the
# delegation actually happened. Bound-method-on-a-stand-in, per CLAUDE.md.

class _FakeList:
    """Stands in for a QListWidget: records what got added."""
    def __init__(self):
        self.items = []

    def clear(self):
        self.items.clear()

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)


#: The token the stand-in window is currently waiting on. Search replies carry the
#: token of the search they answer; anything else is a superseded query's late
#: answer and must be dropped (see MainWindow._stale_search).
CURRENT = 7


def _window(results=None, bookmarks=None):
    return SimpleNamespace(
        results_list=results or _FakeList(),
        bookmarks_list=bookmarks or _FakeList(),
        tabs=SimpleNamespace(setTabText=lambda *a: None),
        status=SimpleNamespace(showMessage=lambda *a: None),
        _search_token=CURRENT,
        _add_row=None, _add_placeholder=None,
    )


def _bind(win):
    win._add_row = app.MainWindow._add_row.__get__(win)
    win._add_placeholder = app.MainWindow._add_placeholder.__get__(win)
    win._stale_search = app.MainWindow._stale_search.__get__(win)
    return win


def test_show_results_adds_a_row_per_result():
    win = _bind(_window())
    rows = [("PHB/a.htm", "Armor (PHB)", "Player's Handbook", "PHB", "plate **mail**"),
            ("MM/b.htm",  "Ogre (MM)",   "Monstrous Manual",  "MM",  "")]
    app.MainWindow._show_results(win, CURRENT, rows)

    assert win.results_list.count() == 2
    first = win.results_list.items[0]
    assert first.text() == "  Armor\n  Player's Handbook\n  plate mail"
    # the page_url rides along as UserRole data, so a click can navigate
    assert first.data(Qt.UserRole) == "PHB/a.htm"


def test_show_results_with_nothing_shows_one_placeholder():
    win = _bind(_window())
    app.MainWindow._show_results(win, CURRENT, [])
    assert win.results_list.count() == 1
    assert "No results found" in win.results_list.items[0].text()


def test_search_error_is_distinct_from_an_empty_result():
    """A failed search must not read as 'no matches' — different text, different colour."""
    win = _bind(_window())
    app.MainWindow._show_search_error(win, CURRENT, "malformed MATCH")
    assert win.results_list.count() == 1
    assert "Search failed" in win.results_list.items[0].text()


# ── a superseded search's late answer is discarded ───────────────────────────
#
# A search cannot be cancelled: quit() only asks an event loop to exit and
# SearchWorker.run() has none, so an abandoned query finishes and emits anyway.
# Type "dragon" then "fireball" before the first returns and both land — the broad
# one usually last, which without this guard left the list showing dragons under a
# fireball query.

def test_a_superseded_search_does_not_replace_the_current_results():
    win = _bind(_window())
    app.MainWindow._show_results(win, CURRENT, [
        ("MM/f.htm", "Fireball (PHB)", "Player's Handbook", "PHB", "")])
    assert win.results_list.count() == 1

    stale = [("MM/d.htm", "Dragon (MM)", "Monstrous Manual", "MM", "")] * 4
    app.MainWindow._show_results(win, CURRENT - 1, stale)

    assert win.results_list.count() == 1                       # untouched
    assert "Fireball" in win.results_list.items[0].text()


def test_a_superseded_empty_search_does_not_blank_the_current_results():
    """The nastiest shape of the race: the late reply has *no* rows, so the guard
    has to run before the 'No results found' placeholder, not after."""
    win = _bind(_window())
    app.MainWindow._show_results(win, CURRENT, [
        ("MM/f.htm", "Fireball (PHB)", "Player's Handbook", "PHB", "")])

    app.MainWindow._show_results(win, CURRENT - 1, [])

    assert win.results_list.count() == 1
    assert "Fireball" in win.results_list.items[0].text()


def test_a_superseded_search_failure_is_not_reported():
    """The reader has moved on; surfacing the old query's error would replace a good
    result list with 'Search failed'."""
    win = _bind(_window())
    app.MainWindow._show_results(win, CURRENT, [
        ("MM/f.htm", "Fireball (PHB)", "Player's Handbook", "PHB", "")])

    app.MainWindow._show_search_error(win, CURRENT - 1, "malformed MATCH")

    assert win.results_list.count() == 1
    assert "Search failed" not in win.results_list.items[0].text()


def test_stale_search_recognises_only_the_newest_token():
    win = _window()
    stale = app.MainWindow._stale_search.__get__(win)
    assert not stale(CURRENT)
    assert stale(CURRENT - 1)
    assert stale(CURRENT + 1)      # a token we never issued is not current either

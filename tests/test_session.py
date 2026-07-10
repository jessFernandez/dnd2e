"""Pure session-restore helpers extracted from MainWindow (session.py).

QSettings is loosely typed, so these guard the coercions that turn whatever it
hands back into something safe to feed the tab widget.
"""
import session


# ── normalize_open_tabs ──────────────────────────────────────────────────────

def test_missing_key_is_no_tabs():
    assert session.normalize_open_tabs(None) == []


def test_a_single_saved_tab_comes_back_as_a_bare_string():
    # QSettings collapses a one-element list to the element itself.
    assert session.normalize_open_tabs("dnd://PHB/DD01671.htm") == ["dnd://PHB/DD01671.htm"]


def test_multiple_tabs_pass_through_as_a_list():
    entries = ["dnd://a", "dnd://b", "dnd://c"]
    assert session.normalize_open_tabs(entries) == entries
    assert session.normalize_open_tabs(entries) is not entries   # a copy, not the original


def test_empty_list_is_no_tabs():
    assert session.normalize_open_tabs([]) == []


# ── active_tab_index ─────────────────────────────────────────────────────────

def test_a_valid_index_is_returned_as_is():
    assert session.active_tab_index(2, tab_count=3) == 2
    assert session.active_tab_index("1", tab_count=3) == 1     # QSettings often stringifies


def test_an_out_of_range_index_selects_nothing():
    assert session.active_tab_index(5, tab_count=3) is None
    assert session.active_tab_index(-1, tab_count=3) is None


def test_a_corrupt_value_falls_back_to_the_default_then_clamps():
    # Garbage -> default 0, which is valid when there are tabs...
    assert session.active_tab_index("garbage", tab_count=3) == 0
    assert session.active_tab_index(None, tab_count=3) == 0
    # ...but even the default is refused when there are no tabs at all.
    assert session.active_tab_index("garbage", tab_count=0) is None


def test_the_default_is_configurable():
    assert session.active_tab_index("x", tab_count=3, default=2) == 2
    assert session.active_tab_index("x", tab_count=1, default=2) is None

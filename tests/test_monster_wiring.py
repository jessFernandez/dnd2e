"""Tests for MainWindow's monster-sheet Qt wiring (_mon_* methods).

Driven against SimpleNamespace stand-ins, like test_charactermancer's _cm routing
and test_nav_reveal — no real window/DB/display.
"""
import os
from types import SimpleNamespace

import pytest

import app
import db
import monster
from monster import Monster
from monster_library import MonsterLibrary

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


# ── _mon_set: store edits, with the AC/THAC0 house-rule inverse ───────────────

def test_mon_set_stores_editable_fields():
    win = SimpleNamespace(_mon=Monster())
    app.MainWindow._mon_set(win, "climate_terrain/Any%20land")
    assert win._mon.climate_terrain == "Any land"        # URL-decoded, stored verbatim


def test_mon_set_ignores_unknown_and_non_editable_fields():
    win = SimpleNamespace(_mon=Monster(source_page="MM/x.htm"))
    app.MainWindow._mon_set(win, "source_page/hax")       # not editable
    app.MainWindow._mon_set(win, "bogus/whatever")        # unknown field
    assert win._mon.source_page == "MM/x.htm"


def test_mon_set_converts_house_rule_ac_and_thaco_back_to_raw():
    win = SimpleNamespace(_mon=Monster())
    app.MainWindow._mon_set(win, "armor_class/16")        # ascending 16 -> descending 4
    app.MainWindow._mon_set(win, "thac0/3")               # attack bonus 3 -> THAC0 17
    assert win._mon.armor_class == "4" and win._mon.thac0 == "17"
    # round-trips: the stored raw redisplays as the house-rule value the DM typed
    assert win._mon.ascending_ac() == "16" and win._mon.attack_bonus() == "3"


# ── _mon_action dispatch ──────────────────────────────────────────────────────

def _action_win():
    calls = {}
    win = SimpleNamespace(
        _mon=None, _mon_saved_id=None,
        _mon_set=lambda r: calls.__setitem__("set", r),
        _navigate=lambda d: calls.__setitem__("nav", d),
        _render_monster_sheet=lambda: calls.__setitem__("sheet", True),
        _render_monster_picker=lambda: calls.__setitem__("picker", True),
        _mon_save=lambda: calls.__setitem__("save", True),
        _mon_pick=lambda u: calls.__setitem__("pick", u),
        _mon_pick_variant=lambda r: calls.__setitem__("pickvar", r),
        _mon_load=lambda i: calls.__setitem__("load", i),
        _mon_delete=lambda i: calls.__setitem__("delete", i),
    )
    return win, calls


def test_mon_action_routes_each_verb():
    win, calls = _action_win()
    app.MainWindow._mon_action(win, "set/size/L")
    assert calls["set"] == "size/L"
    app.MainWindow._mon_action(win, "import")
    assert calls["nav"] == "monster"                # Back-able navigation to the picker
    app.MainWindow._mon_action(win, "save")
    assert calls["save"] is True and calls["sheet"] is True
    app.MainWindow._mon_action(win, "pick/MM/DD03797.htm")
    assert calls["pick"] == "MM/DD03797.htm"
    app.MainWindow._mon_action(win, "pickvar/MM/DD03805.htm/2")
    assert calls["pickvar"] == "MM/DD03805.htm/2"
    app.MainWindow._mon_action(win, "load/7")
    app.MainWindow._mon_action(win, "delete/7")
    assert calls["load"] == "7" and calls["delete"] == "7"


def test_mon_action_family_navigates_to_the_family_picker():
    calls = {}
    win = SimpleNamespace(_navigate=lambda d: calls.__setitem__("nav", d))
    app.MainWindow._mon_action(win, "family/Dragon")
    assert calls["nav"] == "monster-family/Dragon"      # Back-able sub-picker


def test_render_family_picker_renders_members():
    calls = {}
    families = [("Dragon", "MM/DD03842.htm", [("MM/DDr.htm", "Red")])]
    win = SimpleNamespace(
        _monster_index=lambda: (families, []),
        content=SimpleNamespace(_view=SimpleNamespace(setHtml=lambda h: calls.__setitem__("html", h))),
        _mon_status=lambda s: calls.__setitem__("status", s))
    assert app.MainWindow._render_family_picker(win, "Dragon") is True
    assert "Red" in calls["html"] and calls["status"] == "Dragon"


def test_render_family_picker_falls_back_when_unknown():
    seen = []
    win = SimpleNamespace(_monster_index=lambda: ([], []),
                          _render_monster_picker=lambda: seen.append(True) or True)
    assert app.MainWindow._render_family_picker(win, "Nope") is True and seen == [True]


def test_mon_action_new_navigates_to_a_fresh_sheet():
    calls = {}
    win = SimpleNamespace(_mon="stale", _mon_saved_id=9,
                          _navigate=lambda d: calls.__setitem__("nav", d))
    app.MainWindow._mon_action(win, "new")
    assert isinstance(win._mon, Monster) and win._mon_saved_id is None
    assert calls["nav"] == "monster-sheet"          # pushes history so Back works


# ── _render_monster_sheet: current monster, or a blank sheet ──────────────────

def test_render_monster_sheet_uses_current_monster():
    calls = {}
    view = SimpleNamespace(setHtml=lambda h: calls.__setitem__("html", h))
    win = SimpleNamespace(
        _mon=Monster(name="Orc", armor_class="6", thac0="19"), _mon_saved_id=None,
        content=SimpleNamespace(_view=view),
        _mon_status=lambda s: calls.__setitem__("status", s))
    assert app.MainWindow._render_monster_sheet(win) is True
    assert "Orc" in calls["html"] and calls["status"] == "Orc"


def test_render_monster_sheet_is_blank_when_none():
    calls = {}
    win = SimpleNamespace(
        _mon=None, _mon_saved_id=None,
        content=SimpleNamespace(_view=SimpleNamespace(setHtml=lambda h: calls.__setitem__("html", h))),
        _mon_status=lambda s: None)
    assert app.MainWindow._render_monster_sheet(win) is True
    assert "Stat Block" in calls["html"]            # a blank editable sheet


# ── end-to-end: real DB parse -> sheet -> save -> load (Qt view faked) ─────────

@needs_db
def test_import_pick_save_load_end_to_end(tmp_path):
    htmls = []
    win = SimpleNamespace(
        db=db.connect(RULES_DB),
        _mon=None, _mon_saved_id=None, _mon_index=None,
        _mon_library=MonsterLibrary(db.connect(tmp_path / "user.db")),
        content=SimpleNamespace(_view=SimpleNamespace(setHtml=htmls.append)),
        _mon_status=lambda s: None,
    )

    def _nav(dest):                                  # dispatch the monster destinations
        if dest == "monster-sheet":
            app.MainWindow._render_monster_sheet(win)
        elif dest.startswith("monster-variant/"):
            app.MainWindow._render_variant_picker(win, dest[len("monster-variant/"):])
        elif dest == "monster":
            app.MainWindow._render_monster_picker(win)
    win._navigate = _nav

    # single-creature page imports straight to the sheet
    app.MainWindow._mon_pick(win, "MM/DD03797.htm")             # Ankheg
    assert win._mon.name == "Ankheg" and "Ankheg" in htmls[-1]

    # multi-variant page shows the variant picker first, then imports the choice
    app.MainWindow._mon_pick(win, "MM/DD03805.htm")             # Bear
    assert "Black Bear" in htmls[-1] and win._mon.name == "Ankheg"   # unchanged until picked
    app.MainWindow._mon_pick_variant(win, "MM/DD03805.htm/0")
    assert "Bear" in win._mon.name and "Bear" in htmls[-1]

    # save to the user DB, then load it back
    app.MainWindow._mon_save(win)
    assert win._mon_saved_id is not None and len(win._mon_library.all()) == 1
    saved_name = win._mon.name
    win._mon, win._mon_saved_id = None, None
    app.MainWindow._mon_load(win, str(win._mon_library.all()[0]["id"]))
    assert win._mon.name == saved_name

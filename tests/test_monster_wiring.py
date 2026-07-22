"""Tests for MainWindow's monster-sheet Qt wiring (_mon_* methods).

Driven against SimpleNamespace stand-ins, like test_charactermancer's _cm routing
and test_nav_reveal — no real window/DB/display.
"""
import os
from types import SimpleNamespace

import pytest

import app
import db
from monster import Monster
from monster_library import MonsterLibrary

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


# ── _mon_set: store edits, with the AC/THAC0 house-rule inverse ───────────────
#
# The link *grammar* (decoding, coercion) is navigation.route_mon's job and is tested
# in test_navigation; these drive the side effects with already-parsed arguments.

def test_mon_set_stores_editable_fields():
    win = SimpleNamespace(_mon=Monster())
    app.MainWindow._mon_set(win, "climate_terrain", "Any land")
    assert win._mon.climate_terrain == "Any land"        # stored verbatim


def test_mon_set_ignores_unknown_and_non_editable_fields():
    win = SimpleNamespace(_mon=Monster(source_page="MM/x.htm"))
    app.MainWindow._mon_set(win, "source_page", "hax")    # not editable
    app.MainWindow._mon_set(win, "bogus", "whatever")     # unknown field
    assert win._mon.source_page == "MM/x.htm"


def test_mon_set_converts_house_rule_ac_and_thaco_back_to_raw():
    win = SimpleNamespace(_mon=Monster())
    app.MainWindow._mon_set(win, "armor_class", "16")     # ascending 16 -> descending 4
    app.MainWindow._mon_set(win, "thac0", "3")            # attack bonus 3 -> THAC0 17
    assert win._mon.armor_class == "4" and win._mon.thac0 == "17"
    # round-trips: the stored raw redisplays as the house-rule value the DM typed
    assert win._mon.ascending_ac() == "16" and win._mon.attack_bonus() == "3"


def test_mon_set_refuses_a_field_the_selected_tier_is_scaling():
    """While a tier is selected the sheet shows that tier's numbers, so writing one
    back would overwrite the base stat block with a scaled value. The view renders
    those rows read-only; this is the guard behind it."""
    m = Monster(thac0="5-6 HD: 15 7-8 HD: 13", morale="Steady")
    win = SimpleNamespace(_mon=m)
    m.selected_tier = 1                                   # the "7-8 HD" tier
    app.MainWindow._mon_set(win, "thac0", "9")            # scaled by the tier -> refused
    assert m.thac0 == "5-6 HD: 15 7-8 HD: 13"             # the source (and its tiers) intact
    app.MainWindow._mon_set(win, "morale", "Fanatic")     # untiered -> still editable
    assert m.morale == "Fanatic"
    m.selected_tier = None                                # back to Base: editable again
    app.MainWindow._mon_set(win, "thac0", "9")
    assert m.thac0 == "11"


# ── _mon_action dispatch ──────────────────────────────────────────────────────

def _action_win():
    calls = {}
    win = SimpleNamespace(
        _mon=None, _mon_saved_id=None,
        _mon_set=lambda f, v: calls.__setitem__("set", (f, v)),
        _mon_set_tier=lambda v: calls.__setitem__("tier", v),
        _mon_set_init=lambda v: calls.__setitem__("init", v),
        _navigate=lambda d: calls.__setitem__("nav", d),
        _render_monster_sheet=lambda: calls.__setitem__("sheet", True),
        _render_monster_picker=lambda: calls.__setitem__("picker", True),
        _mon_save=lambda: calls.__setitem__("save", True),
        _mon_export_roll20=lambda: calls.__setitem__("roll20", True),
        _mon_pick=lambda u: calls.__setitem__("pick", u),
        _mon_pick_variant=lambda u, i: calls.__setitem__("pickvar", (u, i)),
        _mon_load=lambda i: calls.__setitem__("load", i),
        _mon_delete=lambda i: calls.__setitem__("delete", i),
    )
    return win, calls


def test_mon_action_routes_each_verb():
    win, calls = _action_win()
    app.MainWindow._mon_action(win, "set/size/L")
    assert calls["set"] == ("size", "L")
    app.MainWindow._mon_action(win, "import")
    assert calls["nav"] == "monster"                # Back-able navigation to the picker
    app.MainWindow._mon_action(win, "save")
    assert calls["save"] is True and calls["sheet"] is True
    app.MainWindow._mon_action(win, "tier/2")
    assert calls["tier"] == 2 and calls["sheet"] is True     # re-renders scaled
    app.MainWindow._mon_action(win, "roll20")
    assert calls["roll20"] is True                           # exports to clipboard
    app.MainWindow._mon_action(win, "init/5")
    assert calls["init"] == 5 and calls["sheet"] is True     # re-renders the Initiative tile
    app.MainWindow._mon_action(win, "pick/MM/DD03797.htm")
    assert calls["pick"] == "MM/DD03797.htm"
    app.MainWindow._mon_action(win, "pickvar/MM/DD03805.htm/2")
    assert calls["pickvar"] == ("MM/DD03805.htm", 2)
    app.MainWindow._mon_action(win, "load/7")
    app.MainWindow._mon_action(win, "delete/7")
    assert calls["load"] == 7 and calls["delete"] == 7


def test_mon_action_ignores_an_unknown_verb():
    win, calls = _action_win()
    app.MainWindow._mon_action(win, "detonate/everything")
    assert calls == {}


def test_parse_mm_page_caches_the_last_page(monkeypatch):
    calls = []

    def fake_get_page(conn, url):
        calls.append(url)
        return {"content_html": "<html></html>", "title": "Foo (Monstrous Manual)"}

    monkeypatch.setattr(app.db, "get_page", fake_get_page)
    win = SimpleNamespace(db=None, _mon_page_cache=None)
    _, group = app.MainWindow._parse_mm_page(win, "MM/X.htm")
    app.MainWindow._parse_mm_page(win, "MM/X.htm")                 # same page -> cached
    assert calls == ["MM/X.htm"] and group == "Foo"
    app.MainWindow._parse_mm_page(win, "MM/Y.htm")                # a new page re-parses
    assert calls == ["MM/X.htm", "MM/Y.htm"]


def test_fresh_monster_is_a_detached_copy():
    orig = Monster(name="Orig", extra_tables=[{"kind": "age", "rows": [["1"]]}])
    clone = app.MainWindow._fresh_monster(orig)
    clone.name = "Edited"
    clone.extra_tables.append({"kind": "x"})
    assert orig.name == "Orig" and len(orig.extra_tables) == 1    # the cached original is untouched


def test_mon_set_tier_selects_index_or_clears_to_base():
    win = SimpleNamespace(_mon=Monster(thac0="5-6 HD: 15 7-8 HD: 13"))
    app.MainWindow._mon_set_tier(win, 1)
    assert win._mon.selected_tier == 1
    app.MainWindow._mon_set_tier(win, None)                 # "Base (as written)"
    assert win._mon.selected_tier is None


def test_mon_set_init_overrides_or_clears():
    win = SimpleNamespace(_mon=Monster(size="M"))
    app.MainWindow._mon_set_init(win, 1)
    assert win._mon.initiative_override == 1 and win._mon.initiative_modifier() == 1
    app.MainWindow._mon_set_init(win, None)                 # back to size-derived
    assert win._mon.initiative_override is None and win._mon.initiative_modifier() == 3


def test_mon_action_family_navigates_to_the_family_picker():
    calls = {}
    win = SimpleNamespace(_navigate=lambda d: calls.__setitem__("nav", d))
    app.MainWindow._mon_action(win, "family/Dragon")
    assert calls["nav"] == "monster-family/Dragon"      # Back-able sub-picker


def test_render_family_picker_renders_members():
    calls = {}
    families = [("Dragon", "MM/DD03842.htm", [("MM/DDr.htm", "Red", 1)])]
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
        content=SimpleNamespace(_view=view), _mon_image_url=lambda m: "",
        _spell_link_index=lambda: None,
        _mon_status=lambda s: calls.__setitem__("status", s))
    assert app.MainWindow._render_monster_sheet(win) is True
    assert "Orc" in calls["html"] and calls["status"] == "Orc"


def test_render_monster_sheet_is_blank_when_none():
    calls = {}
    win = SimpleNamespace(
        _mon=None, _mon_saved_id=None, _mon_image_url=lambda m: "",
        _spell_link_index=lambda: None,
        content=SimpleNamespace(_view=SimpleNamespace(setHtml=lambda h: calls.__setitem__("html", h))),
        _mon_status=lambda s: None)
    assert app.MainWindow._render_monster_sheet(win) is True
    assert "Stat Block" in calls["html"]            # a blank editable sheet


def test_mon_image_url_builds_from_source_site():
    win = SimpleNamespace(_cache_image=lambda url, path: None)   # don't hit the network
    m = Monster(source_page="MM/DD03797.htm", image="ANKHEG.gif")
    url = app.MainWindow._mon_image_url(win, m)
    # remote URL when uncached, or a data: URI when a previous run already cached it
    assert url == app.BASE_URL + "MM/ANKHEG.gif" or url.startswith("data:image")
    assert app.MainWindow._mon_image_url(win, Monster()) == ""   # no image -> no url


# ── end-to-end: real DB parse -> sheet -> save -> load (Qt view faked) ─────────

@needs_db
def test_import_pick_save_load_end_to_end(tmp_path):
    htmls = []
    win = SimpleNamespace(
        db=db.connect(RULES_DB),
        _mon=None, _mon_saved_id=None, _mon_index=None, _mon_page_cache=None,
        _mon_library=MonsterLibrary(db.connect(tmp_path / "user.db")),
        content=SimpleNamespace(_view=SimpleNamespace(setHtml=htmls.append)),
        _mon_image_url=lambda m: "", _spell_link_index=lambda: None, _mon_status=lambda s: None,
        _fresh_monster=app.MainWindow._fresh_monster,
    )
    win._parse_mm_page = lambda url: app.MainWindow._parse_mm_page(win, url)

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
    app.MainWindow._mon_pick_variant(win, "MM/DD03805.htm", 0)
    assert "Bear" in win._mon.name and "Bear" in htmls[-1]
    app.MainWindow._mon_pick_variant(win, "MM/DD03805.htm", 99)     # out of range: no-op
    assert "Bear" in win._mon.name

    # save to the user DB, then load it back
    app.MainWindow._mon_save(win)
    assert win._mon_saved_id is not None and len(win._mon_library.all()) == 1
    saved_name = win._mon.name
    win._mon, win._mon_saved_id = None, None
    app.MainWindow._mon_load(win, win._mon_library.all()[0]["id"])
    assert win._mon.name == saved_name

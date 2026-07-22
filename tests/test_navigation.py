"""Tests for navigation.py — the per-tab back/forward state machine, the pure
destination grammar (link_to_destination, takes_full_width, route_destination),
the browse-pane policy (pane_action), and link routing (route_link)."""
import pytest

from navigation import (
    History, FULLWIDTH_SCREENS, link_to_destination, takes_full_width,
    pane_action, Trigger, Pane,
    route_link, Ask, AskSetModel, AskRefresh, AskStop, CmAction, MonAction, NewTab, Navigate,
    route_mon, MonSet, MonTier, MonInit, MonPick, MonPickVariant, MonLoad, MonDelete,
    MonFamily, MonPicker, MonNew, MonSave, MonExport,
    route_destination, SIMPLE_SCREENS, Dest, Page, Toc, Screen, Spells, Proficiencies,
    Charactermancer, AskScreen, MonsterPicker, MonsterSheet, MonsterFamily, MonsterVariant,
)


# ── destination grammar ───────────────────────────────────────────────────────

def test_link_to_destination_maps_routing_prefixes():
    assert link_to_destination("toc/PHB") == "toc:PHB"
    assert link_to_destination("screen/dmscreen") == "dmscreen"
    # already-canonical paths pass through untouched
    assert link_to_destination("PHB/DD01671.htm") == "PHB/DD01671.htm"
    assert link_to_destination("proficiencies") == "proficiencies"
    assert link_to_destination("proficiencies#thieving") == "proficiencies#thieving"
    # a monster's spell-like link resolves to the compendium scrolled to that spell
    assert link_to_destination("spell/charm-person") == "spells#spell-charm-person"


def test_takes_full_width_screens_vs_book_pages():
    for dest in FULLWIDTH_SCREENS:
        assert takes_full_width(dest), dest
    assert takes_full_width("proficiencies")
    assert takes_full_width("proficiencies#thieving")     # matched by prefix
    assert takes_full_width("spells#spell-charm-person")  # compendium at an anchor
    for dest in ("PHB/DD01671.htm", "toc:PHB", "CT/DD00123.htm", ""):
        assert not takes_full_width(dest), dest


def test_takes_full_width_covers_monster_subviews():
    assert takes_full_width("monster")                       # the picker
    assert takes_full_width("monster-sheet")                 # the sheet
    assert takes_full_width("monster-variant/MM/DD03805.htm")  # the variant chooser
    assert not takes_full_width("MM/DD03797.htm")            # a book page still isn't


# ── browse-pane policy ────────────────────────────────────────────────────────

def test_pane_action_full_width_always_closes():
    for dest in ("splash", "dmscreen", "spells", "proficiencies", "proficiencies#x"):
        for trigger in Trigger:
            assert pane_action(dest, trigger) is Pane.CLOSE, (dest, trigger)


def test_pane_action_book_opens_only_on_a_link():
    for dest in ("PHB/DD01671.htm", "toc:PHB", "CT/DD00123.htm"):
        assert pane_action(dest, Trigger.LINK) is Pane.OPEN, dest
        assert pane_action(dest, Trigger.NAVIGATE) is Pane.LEAVE, dest
        assert pane_action(dest, Trigger.TAB_CHANGE) is Pane.LEAVE, dest


# ── link routing ──────────────────────────────────────────────────────────────

def _route(url, on_jarvis_page=False):
    return route_link(url, on_jarvis_page=on_jarvis_page)


def test_route_ask_question_is_url_decoded_and_trimmed():
    assert _route("ask/how%20does%20thac0%20work") == Ask("how does thac0 work")
    assert _route("ask/%20%20surprise%20") == Ask("surprise")     # leading/trailing trimmed


def test_route_ask_set_model_is_decoded_and_trimmed():
    assert _route("ask-setmodel/llama3.1%3A8b") == AskSetModel("llama3.1:8b")


def test_route_ask_refresh_variants():
    assert _route("ask-refresh") == AskRefresh()
    assert _route("ask-new") == AskRefresh()          # both reset the conversation


def test_route_ask_stop():
    assert _route("ask-stop") == AskStop()


def test_route_cm_action_is_passed_through_verbatim():
    # builder payloads are not URL-decoded — they reach _cm_action raw
    assert _route("cm/set-race/Elf") == CmAction("set-race/Elf")
    assert _route("cm/pick%20me") == CmAction("pick%20me")


def test_route_mon_action_is_passed_through_verbatim():
    assert _route("mon/save") == MonAction("save")
    assert _route("mon/pick/MM/DD03797.htm") == MonAction("pick/MM/DD03797.htm")
    assert _route("mon/set/climate_terrain/Any%20land") == MonAction("set/climate_terrain/Any%20land")


# ── the monster-sheet action grammar (route_mon) ──────────────────────────────

def test_route_mon_classifies_each_verb():
    assert route_mon("import") == MonPicker()
    assert route_mon("new") == MonNew()
    assert route_mon("save") == MonSave()
    assert route_mon("roll20") == MonExport()
    assert route_mon("family/Dragon") == MonFamily("Dragon")
    assert route_mon("pick/MM/DD03797.htm") == MonPick("MM/DD03797.htm")
    assert route_mon("load/7") == MonLoad(7)
    assert route_mon("delete/7") == MonDelete(7)


def test_route_mon_set_decodes_the_value_and_splits_once():
    """monText() percent-encodes the value, so a field's own slashes survive the
    round trip and only the *first* separator splits field from value."""
    assert route_mon("set/climate_terrain/Any%20land") == MonSet("climate_terrain", "Any land")
    assert route_mon("set/damage_attack/1-4%2F1-4") == MonSet("damage_attack", "1-4/1-4")
    assert route_mon("set/combat/") == MonSet("combat", "")     # cleared to empty
    assert route_mon("set/") is None                            # no field named


def test_route_mon_coerces_indices_and_ids():
    assert route_mon("tier/2") == MonTier(2)
    assert route_mon("tier/base") == MonTier(None)              # "Base (as written)"
    assert route_mon("tier/garbage") == MonTier(None)           # unparseable -> base
    assert route_mon("init/5") == MonInit(5)
    assert route_mon("init/-2") == MonInit(-2)
    assert route_mon("init/") == MonInit(None)                  # blank -> size-derived
    assert route_mon("init/x") == MonInit(None)
    assert route_mon("pickvar/MM/DD03805.htm/2") == MonPickVariant("MM/DD03805.htm", 2)
    assert route_mon("pickvar/MM/DD03805.htm/x") is None        # unparseable index
    assert route_mon("load/x") is None and route_mon("delete/") is None


def test_route_mon_ignores_an_unknown_verb():
    assert route_mon("detonate/everything") is None
    assert route_mon("") is None


def test_route_newtab_resolves_the_inner_destination():
    assert _route("newtab/toc/PHB") == NewTab("toc:PHB")
    assert _route("newtab/CT/DD00123.htm") == NewTab("CT/DD00123.htm")
    assert _route("newtab/screen/dmscreen") == NewTab("dmscreen")


def test_route_plain_links_navigate_the_current_tab():
    assert _route("PHB/DD01671.htm") == Navigate("PHB/DD01671.htm")
    assert _route("toc/PHB") == Navigate("toc:PHB")
    assert _route("screen/dmscreen") == Navigate("dmscreen")


def test_route_on_the_jarvis_page_opens_plain_links_in_a_new_tab():
    # a citation clicked on the Ask page must not clobber the Q&A
    assert _route("MM/DD09912.htm", on_jarvis_page=True) == NewTab("MM/DD09912.htm")
    assert _route("toc/PHB", on_jarvis_page=True) == NewTab("toc:PHB")
    # but the ask/cm control routes are unaffected by which page we're on
    assert _route("ask-stop", on_jarvis_page=True) == AskStop()
    assert _route("cm/x", on_jarvis_page=True) == CmAction("x")


def test_empty_history():
    h = History()
    assert h.current() is None
    assert not h.can_back() and not h.can_forward()
    assert h.back() is None and h.forward() is None


def test_push_and_current():
    h = History()
    h.push("splash")
    assert h.current() == "splash"
    assert not h.can_back() and not h.can_forward()
    h.push("PHB/DD01671.htm")
    assert h.current() == "PHB/DD01671.htm"
    assert h.can_back() and not h.can_forward()


def test_back_forward_roundtrip():
    h = History()
    for d in ("splash", "spells", "ask"):
        h.push(d)
    assert h.current() == "ask"
    assert h.back() == "spells"
    assert h.back() == "splash"
    assert h.back() is None          # already at the start
    assert h.current() == "splash"
    assert h.forward() == "spells"
    assert h.forward() == "ask"
    assert h.forward() is None       # already at the end


def test_push_discards_forward_history():
    h = History()
    for d in ("a", "b", "c"):
        h.push(d)
    h.back(); h.back()               # now at "a"
    assert h.can_forward()
    h.push("x")                      # branching from "a" drops "b"/"c"
    assert h.entries == ["a", "x"]
    assert h.current() == "x"
    assert not h.can_forward()


def test_restore_from_state():
    h = History(["splash", "spells", "ask"], pos=1)
    assert h.current() == "spells"
    assert h.can_back() and h.can_forward()
    assert h.forward() == "ask"


# ── route_destination (the dispatch grammar) ─────────────────────────────────
#
# Extracted from MainWindow._render_destination, which was the only place that
# knew the full set. See docs/audit-2-plan.md finding 3.

@pytest.mark.parametrize("dest,expected", [
    ("toc:PHB",                     Toc("PHB")),
    ("toc:CT",                      Toc("CT")),
    ("splash",                      Screen("splash")),
    ("dmscreen",                    Screen("dmscreen")),
    ("actions",                     Screen("actions")),
    ("ask",                         AskScreen()),
    ("charactermancer",             Charactermancer()),
    ("spells",                      Spells("")),
    ("spells#spell-fireball",       Spells("spell-fireball")),
    ("proficiencies",               Proficiencies("")),
    ("proficiencies#prof-riding",   Proficiencies("prof-riding")),
    ("monster",                     MonsterPicker()),
    ("monster-sheet",               MonsterSheet()),
    ("monster-family/Dragon",       MonsterFamily("Dragon")),
    ("monster-variant/MM/DD1.htm",  MonsterVariant("MM/DD1.htm")),
    ("PHB/DD01671.htm",             Page("PHB/DD01671.htm")),
    ("",                            Page("")),
])
def test_route_destination_classifies(dest, expected):
    assert route_destination(dest) == expected


def test_unknown_destination_is_a_page():
    """page_urls are the open-ended part of the grammar, so anything unrecognised
    falls through to Page and fails at render time rather than here."""
    assert route_destination("monster-typo") == Page("monster-typo")
    assert route_destination("not-a-screen") == Page("not-a-screen")


def test_every_route_destination_result_is_tagged():
    for dest in ("toc:PHB", "splash", "spells", "monster-sheet", "PHB/x.htm", ""):
        assert isinstance(route_destination(dest), Dest)


def test_simple_screens_all_route_to_screen():
    for name in SIMPLE_SCREENS:
        assert route_destination(name) == Screen(name)


def test_takes_full_width_agrees_with_route_destination():
    """takes_full_width derives from route_destination now; FULLWIDTH_SCREENS is the
    independent list that catches the classification drifting."""
    for dest in FULLWIDTH_SCREENS:
        assert takes_full_width(dest), dest
        assert not isinstance(route_destination(dest), (Page, Toc)), dest
    for dest in ("PHB/DD01671.htm", "toc:PHB", ""):
        assert not takes_full_width(dest), dest


def test_fragment_only_split_on_own_prefix():
    """A page_url containing '#' is still a page, not a fragmented screen."""
    assert route_destination("PHB/DD01.htm#anchor") == Page("PHB/DD01.htm#anchor")
    assert route_destination("spellsomething") == Page("spellsomething")

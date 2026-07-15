"""Tests for navigation.py — the per-tab back/forward state machine, the pure
destination grammar (link_to_destination, takes_full_width), the browse-pane
policy (pane_action), and link routing (route_link)."""
from navigation import (
    History, FULLWIDTH_SCREENS, link_to_destination, takes_full_width,
    pane_action, Trigger, Pane,
    route_link, Ask, AskSetModel, AskRefresh, AskStop, CmAction, MonAction, NewTab, Navigate,
)


# ── destination grammar ───────────────────────────────────────────────────────

def test_link_to_destination_maps_routing_prefixes():
    assert link_to_destination("toc/PHB") == "toc:PHB"
    assert link_to_destination("screen/dmscreen") == "dmscreen"
    # already-canonical paths pass through untouched
    assert link_to_destination("PHB/DD01671.htm") == "PHB/DD01671.htm"
    assert link_to_destination("proficiencies") == "proficiencies"
    assert link_to_destination("proficiencies#thieving") == "proficiencies#thieving"


def test_takes_full_width_screens_vs_book_pages():
    for dest in FULLWIDTH_SCREENS:
        assert takes_full_width(dest), dest
    assert takes_full_width("proficiencies")
    assert takes_full_width("proficiencies#thieving")     # matched by prefix
    for dest in ("PHB/DD01671.htm", "toc:PHB", "CT/DD00123.htm", ""):
        assert not takes_full_width(dest), dest


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

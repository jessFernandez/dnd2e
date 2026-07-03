"""Tests for navigation.History — the per-tab back/forward state machine."""
from navigation import History


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

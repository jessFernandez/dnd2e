"""Unit tests for Jarvis answer post-processing (link-fixing + house-rule marks)."""
from rules_agent import _linkify, _mark_house_rules

TITLES = {
    "PHB/DD01673.htm": "Figuring the To-Hit Number",
    "PHB/DD01422.htm": "Rolling Ability Scores",
}


def test_linkify_bracketed_bare_url():
    out = _linkify("Sources:\n[dnd:///PHB/DD01673.htm]", TITLES)
    assert "[Figuring the To-Hit Number](dnd:///PHB/DD01673.htm)" in out


def test_linkify_bare_url_in_prose():
    out = _linkify("see dnd:///PHB/DD01422.htm for details", TITLES)
    assert "[Rolling Ability Scores](dnd:///PHB/DD01422.htm)" in out


def test_linkify_preserves_existing_link():
    src = "[Custom Text](dnd:///PHB/DD01673.htm)"
    assert _linkify(src, TITLES) == src


def test_linkify_unknown_url_falls_back_to_filename():
    out = _linkify("[dnd:///XYZ/DD99999.htm]", {})
    assert "[DD99999](dnd:///XYZ/DD99999.htm)" in out


def test_mark_house_rules_label():
    assert _mark_house_rules("House rule: no critical hits.").startswith("⚔️ **House Rule:**")


def test_mark_house_rules_inline_citation():
    assert "(⚔️ house rule)" in _mark_house_rules("Damage is capped (house rule).")


def test_mark_house_rules_idempotent():
    once = _mark_house_rules("House Rule: x")
    assert _mark_house_rules(once) == once

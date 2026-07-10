"""The Codex of Worldly Craft reference screen (proficiencies_html.py).

Pure string templating over char_rules.NONWEAPON_PROFICIENCIES, and previously
untested. These pin the parts that can silently go wrong: the anchor slugs the
sidebar depends on, the bullet-vs-paragraph prose rendering, and the guarantee
that every skill actually lands on the page.
"""
import re

import char_rules as cr
import proficiencies_html as ph


def test_slug_is_url_safe_and_stable():
    assert ph.slug("Bowyer/Fletcher") == "bowyer-fletcher"
    assert ph.slug("Animal Handling") == "animal-handling"
    assert ph.slug("Reading/Writing") == "reading-writing"
    assert ph.slug("  Weird---Name!!  ") == "weird-name"


def test_slots_label():
    assert ph._slots_label(0) == "Free"
    assert ph._slots_label(1) == "1 slot"
    assert ph._slots_label(2) == "2 slots"


def test_classes_label():
    assert ph._classes_label(()) == "All classes"
    assert ph._classes_label(("Warrior",)) == "Warrior"
    assert ph._classes_label(("Warrior", "Rogue")) == "Warrior · Rogue"


def test_render_desc_makes_a_list_only_from_several_bullets():
    one = ph._render_desc("A lead line.\n* just one bullet")
    assert "<ul>" not in one and "<p>" in one          # a single bullet isn't a list

    many = ph._render_desc("Pick one:\n* alpha\n* beta\n* gamma")
    assert many.count("<li>") == 3
    assert "<p>Pick one:</p>" in many                  # the lead line survives as prose


def test_render_desc_escapes_prose():
    out = ph._render_desc("tags <b> & \"quotes\" are escaped")
    assert "<b>" not in out
    assert "&lt;b&gt;" in out and "&amp;" in out


def test_render_desc_empty_is_empty():
    assert ph._render_desc("") == ""
    assert ph._render_desc(None) == ""
    # Runs of blank lines between paragraphs collapse away, not into empty <p>s.
    out = ph._render_desc("first\n\n   \n\nsecond")
    assert out == "<p>first</p><p>second</p>"


def test_letters_and_grouped_partition_every_skill():
    groups = ph.grouped()
    # Every proficiency lands in exactly one letter bucket.
    counted = sum(len(v) for v in groups.values())
    assert counted == len(cr.NONWEAPON_PROFICIENCIES)
    # letters() lists exactly the buckets, in order.
    assert ph.letters() == list(groups)
    assert list(groups) == sorted(groups)             # alphabetical
    # Each bucket holds only names starting with its letter, sorted.
    for L, profs in groups.items():
        names = [p.name for p in profs]
        assert all(n[0].upper() == L for n in names)
        assert names == sorted(names, key=str.lower)


def test_generate_is_one_document_with_every_skill_anchored():
    html = ph.generate()
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert cr.PROFICIENCY_BOOK in html
    # Every skill has its card, at the id the sidebar's slug() will link to.
    for name in cr.NONWEAPON_PROFICIENCIES:
        assert f'id="prof-{ph.slug(name)}"' in html, name
    # The A–Z index links resolve to real section anchors on the same page.
    for letter in re.findall(r'href="#letter-([A-Z])"', html):
        assert f'id="letter-{letter}"' in html


def test_generate_escapes_a_hostile_skill_name(monkeypatch):
    hostile = cr.Proficiency(name='Sneak <script>"x"', ability="Dexterity",
                             modifier=0, slots=1, classes=("Rogue",))
    monkeypatch.setattr(cr, "NONWEAPON_PROFICIENCIES", {hostile.name: hostile})
    html = ph.generate()
    assert "<script>" not in html
    assert "Sneak &lt;script&gt;" in html

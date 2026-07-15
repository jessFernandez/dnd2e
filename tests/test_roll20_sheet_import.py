"""Runs the Roll20 sheet's import mappers in a real JavaScript engine.

A live game showed "[object Object]" in the Weapon Proficiencies column: the export
had changed weapon_profs from a list of names to a list of {name, slots, rung}
objects, and the sheet deployed in Roll20 still had the old mapper, which dropped
the object straight into a text field.

The sheet's mappers are JavaScript embedded in HTML, so asserting on substrings
proves nothing. These tests pull the real mapper source out of sheet.html and run it
in QJSEngine against a real payload from roll20_export, checking that every value it
produces is something a sheet field can actually hold -- never a stringified object.
"""
import json
import os
import re
import sys

import pytest

import roll20_export
from character import Character
from charactermancer import Charactermancer

QJSEngine = pytest.importorskip("PyQt5.QtQml").QJSEngine
from PyQt5.QtCore import QCoreApplication      # noqa: E402

SHEET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "roll20_sheet", "sheet.html")


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


def _mapper_source(section: str) -> str:
    """The mapper function the sheet passes to addRows() for one repeating section.

    Brace-matched rather than regexed: the mappers contain nested `{}` (the legacy
    fallback block), which a lazy regex would truncate."""
    html = open(SHEET, encoding="utf-8").read()
    m = re.search(r'addRows\(data\.\w+,\s*"%s",\s*function' % re.escape(section), html)
    assert m, f"no addRows mapper for section {section!r} in sheet.html"
    start = html.index("function", m.start())
    body = html.index("{", start)
    depth = 0
    for i in range(body, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
    raise AssertionError(f"unbalanced braces in the {section!r} mapper")


def _run_mapper(section: str, item) -> dict:
    """Run the sheet's real mapper over one item and return the fields it produces."""
    eng = QJSEngine()
    # `num` is the sheet's own coercion helper, needed by the mappers.
    eng.evaluate("var num = function(v, d){ v = parseFloat(v); "
                 "return isNaN(v) ? d : v; };")
    eng.evaluate(f"var mapper = {_mapper_source(section)};")
    out = eng.evaluate(f"JSON.stringify(mapper({json.dumps(item)}));")
    assert not out.isError(), out.toString()
    return json.loads(out.toString())


def _fighter() -> Character:
    import random
    cm = Charactermancer(rng=random.Random(1))
    c = cm.character
    c.abilities = {"Strength": 16, "Dexterity": 14, "Constitution": 15,
                   "Intelligence": 12, "Wisdom": 11, "Charisma": 10, "Perception": 12}
    cm.set_race("Human")
    cm.set_class("Fighter")
    cm.set_level(7)                       # fills hp_rolls, so max_hp() works
    c.name = "Gornak"
    c.weapon_profs = {"Long Sword": "specialist", "Dagger": "proficient"}
    return c


def test_weapon_proficiency_rows_never_stringify_an_object():
    """The bug: an object dropped into wpsname rendered as "[object Object]"."""
    payload = roll20_export.character_to_roll20(_fighter())
    assert payload["weapon_profs"], "the fixture should export some proficiencies"
    for entry in payload["weapon_profs"]:
        row = _run_mapper("wps", entry)
        assert "[object Object]" not in str(row["wpsname"])
        assert isinstance(row["wpsname"], str) and row["wpsname"]
        assert isinstance(row["wpsslots"], (int, float))


def test_weapon_proficiency_row_labels_carry_the_mastery_rung():
    payload = roll20_export.character_to_roll20(_fighter())
    labels = {_run_mapper("wps", e)["wpsname"] for e in payload["weapon_profs"]}
    assert "Long Sword (specialist)" in labels    # the rung is appended...
    assert "Dagger" in labels                     # ...but plain proficiency isn't noise


def test_weapon_proficiency_mapper_tolerates_a_legacy_name_string():
    # An older export sent bare names. The mapper must degrade to a plain name rather
    # than render "[object Object]", so a sheet/export version skew stays readable.
    row = _run_mapper("wps", "Long Sword")
    assert row["wpsname"] == "Long Sword"
    assert row["wpsslots"] == 1


def test_every_repeating_section_maps_to_flat_field_values():
    """No mapper may put a dict/list into a sheet field -- that's what produced the bug."""
    c = _fighter()
    c.inventory = {"Long Sword": 1}
    c.worn = []
    c.nonweapon_profs = {"Riding, Land-Based": 1}
    payload = roll20_export.character_to_roll20(c)
    for section, key in (("weapons", "weapons"), ("wps", "weapon_profs"),
                         ("nwp", "nwp"), ("gear1", "gear"), ("armor", "armor")):
        for entry in payload.get(key) or []:
            for field, value in _run_mapper(section, entry).items():
                assert isinstance(value, (str, int, float)), \
                    f"{section}.{field} is {type(value).__name__}, not a flat value"
                assert "[object Object]" not in str(value), f"{section}.{field}"

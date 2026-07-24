"""The DM Screen's rules tables must agree with char_rules.

`dmscreen_html` carried five of the engine's tables as hand-typed literals: THAC0
by level, character saving throws, turning undead, warrior attacks. Nothing related
them to `char_rules`, and one had already drifted — the Priest THAC0 column smoothed
the 3-level bands and was wrong at levels 3, 6, 9, 12, 15 and 18, while the Rogue
column showed the printed progression instead of the campaign's (rogues advance at
the priest rate here, a gap of up to 3 points by 20th). A DM reading the card and a
player reading the builder got different numbers for the same character.

The cards now compute from char_rules. These tests are what keeps them that way:
they parse the *rendered HTML* rather than calling the card functions, so a future
edit that reintroduces a literal fails here even if it never touches char_rules.

`tests/test_architecture.py` checks that modules import the right things; it cannot
check that a module which already imports char_rules actually gets its numbers from
there. This file closes that gap for the surface where being wrong matters most.
"""
import html
import re

import pytest

import char_rules as cr
import dmscreen_html


@pytest.fixture(scope="module")
def cards():
    """{card title: [row, …]}, each row a list of cell strings, from the real HTML."""
    page = dmscreen_html.generate()
    out = {}
    for block in page.split('<div class="card ')[1:]:
        m = re.search(r'<span class="card-title">(.*?)</span>', block)
        if not m:
            continue
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", block, re.S):
            cells = [html.unescape(re.sub(r"<.*?>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if cells:
                rows.append(cells)
        out[html.unescape(m.group(1))] = rows
    return out


# ── THAC0 ────────────────────────────────────────────────────────────────────

#: The class the card's four group columns are rendered from.
_GROUP_REP = {"Warrior": "Fighter", "Priest": "Cleric", "Rogue": "Thief", "Wizard": "Mage"}


def test_thac0_card_matches_char_rules(cards):
    """Every cell of the THAC0 card, all four columns, levels 1–20."""
    rows = cards["THAC0 by Level"]
    header, body = rows[0], rows[1:]
    groups = header[1:]
    assert groups == ["Warrior", "Priest", "Rogue", "Wizard"]
    assert len(body) == 20, "the card should cover levels 1-20"

    for row in body:
        level = int(row[0])
        for group, shown in zip(groups, row[1:]):
            expected = cr.thac0(_GROUP_REP[group], level)
            assert int(shown) == expected, (
                f"{group} level {level}: card says {shown}, char_rules says {expected}"
            )


def test_thac0_card_uses_the_house_rule_not_the_printed_table(cards):
    """The regression that started this file.

    The campaign's rogues advance at the priest rate. If the card ever goes back to
    the printed progression it will still be *a* valid table — just not this game's —
    so assert the difference explicitly rather than trusting the loop above to be
    read carefully.
    """
    if not cr.HOUSE_RULES.rogue_attack_as_priest:
        pytest.skip("house rule is off; the card should then show the printed table")
    body = cards["THAC0 by Level"][1:]
    rogue_col = [int(r[3]) for r in body]
    raw = [cr.thac0("Thief", lvl, house_rules=False) for lvl in range(1, 21)]
    housed = [cr.thac0("Thief", lvl) for lvl in range(1, 21)]
    assert rogue_col == housed
    assert rogue_col != raw, "the card is showing RAW rogue THAC0, not the house rule"


def test_priest_thac0_is_flat_within_each_three_level_band(cards):
    """Priests improve 2 points every 3 levels, so 1/2/3 share a value, as do 4/5/6.
    The old literal interpolated between the steps; this is that bug, named."""
    body = cards["THAC0 by Level"][1:]
    priest = [int(r[2]) for r in body]
    for band_start in range(0, 18, 3):
        band = priest[band_start:band_start + 3]
        assert len(set(band)) == 1, (
            f"levels {band_start + 1}-{band_start + 3} should share a THAC0, got {band}"
        )


# ── saving throws ────────────────────────────────────────────────────────────

def test_saving_throw_card_matches_char_rules(cards):
    """Every band of every group, all five categories."""
    rows = cards["Character Saving Throws"]
    header, body = rows[0], rows[1:]
    assert header[:2] == ["Class", "Level"]

    expected = []
    for group in ("Priest", "Rogue", "Warrior", "Wizard"):
        for label, saves in cr.saving_throw_bands(group):
            expected.append([group, label.replace("-", "–")]
                            + [str(saves[cat]) for cat in cr.SAVE_CATEGORIES])
    assert body == expected


def test_saving_throw_bands_cover_every_level(cards):
    """The card's bands must not leave a level unaccounted for: walking 1-25 through
    cr.saving_throws has to land in the band the card shows for that level."""
    for group, rep in _GROUP_REP.items():
        bands = cr.saving_throw_bands(group)
        for level in range(1, 26):
            actual = cr.saving_throws(rep, level)
            match = [saves for label, saves in bands if _in_band(label, level)]
            assert len(match) == 1, f"{group} level {level} matched {len(match)} bands"
            assert match[0] == actual


def _in_band(label: str, level: int) -> bool:
    if label.endswith("+"):
        return level >= int(label[:-1])
    if "-" in label:
        lo, hi = label.split("-")
        return int(lo) <= level <= int(hi)
    return level == int(label)


# ── turning undead ───────────────────────────────────────────────────────────

def test_turning_undead_card_matches_char_rules(cards):
    rows = cards["Turning Undead"]
    header, body = rows[0], rows[1:]
    assert header == ["Undead Type / HD"] + [
        label for label, _lvl in dmscreen_html._TURN_COLUMNS]
    assert len(body) == len(cr.TURN_UNDEAD_TYPES)

    for row, undead in zip(body, cr.TURN_UNDEAD_TYPES):
        assert row[0] == undead.replace("-", "–")
        for (_label, level), shown in zip(dmscreen_html._TURN_COLUMNS, row[1:]):
            value = cr.turn_undead("Cleric", level).get(undead)
            assert shown == ("–" if value is None else str(value)), (
                f"{undead} at cleric level {level}: card {shown!r}, rules {value!r}"
            )


def test_turning_undead_banded_columns_really_are_flat():
    """The last three columns are bands (10–11, 12–13, 14+), each rendered from one
    representative level. If the table ever stops being flat across a band the card
    would silently show only half of it."""
    def row(level):
        return tuple(str(cr.turn_undead("Cleric", level).get(t)) for t in cr.TURN_UNDEAD_TYPES)

    assert row(10) == row(11)
    assert row(12) == row(13)
    for level in range(14, 26):
        assert row(14) == row(level)


def test_turning_undead_footnote_matches_the_rulebook():
    """PHB Table 61: "An additional 2d4 creatures of this type are turned." The note
    said 2d6 — wrong, and on the one card a DM reads mid-combat."""
    page = dmscreen_html.generate()
    assert "2d4" in page
    assert "2d6 turned" not in page


# ── warrior attacks ──────────────────────────────────────────────────────────

def test_warrior_attacks_card_matches_char_rules(cards):
    rows = cards["Warrior Melee Attacks"][1:]
    labels = {"1 / round": (1, 1), "3/2 rounds": (3, 2), "2 / round": (2, 1)}
    for band, label in rows:
        expected = labels[label]
        for level in _levels_in(band):
            assert cr.attacks_per_round("Fighter", level) == expected, (
                f"warrior level {level}: card says {label}"
            )


def _levels_in(band: str):
    if band.endswith("+"):
        return range(int(band[:-1]), 26)
    lo, hi = band.split("–")
    return range(int(lo), int(hi) + 1)

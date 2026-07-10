"""Structural invariants of the rules engine.

Two kinds of check that a cell-by-cell transcription test (test_rulebook_tables)
can't make:

  * Properties every progression must have regardless of the exact numbers -- saves
    and THAC0 never get worse as you level, XP thresholds strictly climb, spell slots
    never shrink. These catch a transposed row the cell check would miss, and they
    guard the XP and attack tables, which have no cell test.
  * The whole-engine sweep: build every legal race x class x level and confirm nothing
    raises and no derived value is nonsensical. This is the test that would have caught
    the level-control bugs found by hand during the audit, and it's cheap.

All pure; no DB needed.
"""
import itertools

import pytest

import char_rules as cr
from character import Character
from charactermancer import Charactermancer


LEVELS = range(1, 21)


# ── progression properties ───────────────────────────────────────────────────

@pytest.mark.parametrize("class_name", cr.CLASSES)
def test_saving_throws_never_worsen_as_you_level(class_name):
    prev = None
    for level in range(1, 26):                       # past every band's upper edge
        saves = cr.saving_throws(class_name, level)   # must resolve at every level
        assert set(saves) == set(cr.SAVE_CATEGORIES)
        if prev is not None:
            for cat in cr.SAVE_CATEGORIES:
                assert saves[cat] <= prev[cat], f"{class_name} {cat} worsened at {level}"
        prev = saves


@pytest.mark.parametrize("class_name", cr.CLASSES)
def test_thac0_never_worsens_as_you_level(class_name):
    values = [cr.thac0(class_name, lvl) for lvl in range(1, 26)]
    assert values == sorted(values, reverse=True)     # non-increasing


@pytest.mark.parametrize("class_name", cr.CLASSES)
def test_attacks_per_round_never_decrease(class_name):
    def rate(lvl):
        a, r = cr.attacks_per_round(class_name, lvl)
        return a / r
    rates = [rate(lvl) for lvl in LEVELS]
    assert rates == sorted(rates)
    # Only warriors ever exceed one attack per round.
    if cr.CLASSES[class_name].group != "Warrior":
        assert set(rates) == {1.0}


@pytest.mark.parametrize("class_name", cr.CLASSES)
def test_xp_thresholds_strictly_ascend(class_name):
    table = cr._XP[class_name]
    assert table == sorted(table)
    assert len(set(table)) == len(table)              # strictly, no repeats
    assert table[0] == 0                              # 1st level is free


@pytest.mark.parametrize("class_name", cr.CLASSES)
def test_level_for_xp_inverts_xp_for_level(class_name):
    table = cr._XP[class_name]
    for level in range(1, len(table) + 1):
        xp = cr.xp_for_level(class_name, level)
        assert cr.level_for_xp(class_name, xp) == level
        if level > 1:
            assert cr.level_for_xp(class_name, xp - 1) == level - 1   # one short = prior level


@pytest.mark.parametrize("class_name", ("Mage", "Cleric", "Illusionist", "Druid",
                                        "Paladin", "Ranger", "Bard"))
def test_spell_slots_never_shrink_as_you_level(class_name):
    prev_total = 0
    prev_top = 0
    for level in LEVELS:
        slots = cr.spell_slots(class_name, level)      # {spell_level: count}
        total = sum(slots.values())
        top = max(slots) if slots else 0
        assert total >= prev_total, f"{class_name} lost slots at {level}"
        assert top >= prev_top, f"{class_name} lost a spell level at {level}"
        prev_total, prev_top = total, top


# ── whole-engine sweep ───────────────────────────────────────────────────────

def _legal_combos():
    for race, cls in itertools.product(cr.RACES, cr.CLASSES):
        if cr.race_allows(race, cls):
            cap = cr.max_level(race, cls) or 20
            for level in range(1, min(cap, 20) + 1):
                yield race, cls, level


ALL_COMBOS = list(_legal_combos())


def test_the_sweep_covers_every_class_and_a_range_of_levels():
    # Guard against the generator silently yielding nothing.
    assert len({c for _, c, _ in ALL_COMBOS}) == len(cr.CLASSES)
    assert len(ALL_COMBOS) > 200
    assert max(lvl for _, _, lvl in ALL_COMBOS) >= 15


@pytest.mark.parametrize("race,cls,level", ALL_COMBOS,
                         ids=lambda v: v if isinstance(v, str) else str(v))
def test_every_legal_build_derives_cleanly(race, cls, level):
    cm = Charactermancer()
    c = cm.character
    c.abilities = {a: 15 for a in c.ability_names()}   # qualifies for every class
    cm.set_race(race)
    cm.set_class(cls)
    cm.set_level(level)

    # None of these may raise for any legal build.
    hp = c.max_hp()
    c.thac0(); c.saving_throws(); c.attacks_per_round()
    c.spell_slots(); c.max_spell_level(); c.turn_undead()
    c.thief_skill_scores(); c.armor_class(); c.movement()

    # A freshly-built character is never over budget or below its own level in HP.
    assert c.weapon_slots_left() >= 0
    assert c.nonweapon_slots_left() >= 0
    assert c.thief_points_left() >= 0
    assert hp is None or hp >= level

    # Serialization round-trips exactly.
    data = c.to_dict()
    assert Character.from_dict(data).to_dict() == data

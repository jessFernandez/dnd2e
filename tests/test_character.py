"""Tests for character.py — the in-progress character build."""
import random

import pytest

import character as ch
import char_rules as cr


# ── ability rolling ──────────────────────────────────────────────────────────

def test_4d6_drop_lowest_stays_in_range():
    rng = random.Random(1234)
    rolls = [ch.roll_4d6_drop_lowest(rng) for _ in range(2000)]
    assert all(3 <= r <= 18 for r in rolls)
    assert min(rolls) == 3 and max(rolls) == 18       # both extremes are reachable
    assert sum(rolls) / len(rolls) > 11               # drop-lowest skews above 3d6's 10.5


def test_roll_pool_has_one_score_per_ability_and_is_stored():
    c = ch.Character()                                   # house rules on -> 7 (incl. Perception)
    pool = c.roll_pool(random.Random(7))
    assert len(pool) == 7 and c.rolled_pool == pool
    assert all(3 <= s <= 18 for s in pool)
    assert len(ch.Character(house_rules=False).roll_pool(random.Random(7))) == 6


# ── assignment + validation ──────────────────────────────────────────────────

FULL = {"Strength": 12, "Dexterity": 13, "Constitution": 14,
        "Intelligence": 11, "Wisdom": 10, "Charisma": 9, "Perception": 12}


def _with(**over):
    c = ch.Character()
    for a, s in {**FULL, **over}.items():
        c.assign_ability(a, s)
    return c


def test_assignment_and_completeness():
    c = ch.Character()
    assert not c.has_all_abilities()
    c = _with()
    assert c.has_all_abilities() and c.abilities_valid()


def test_unknown_ability_rejected():
    with pytest.raises(ValueError):
        ch.Character().assign_ability("Luck", 12)


# ── movement + spell limits ──────────────────────────────────────────────────

def test_movement_by_race():
    assert _with().movement() == 12                       # no race yet -> default 12
    c = _with(); c.race = "Human"
    assert c.movement() == 12
    c.race = "Dwarf"
    assert c.movement() == 6


def test_wizard_spell_limit_capped_by_intelligence():
    c = _with(Intelligence=11); c.race, c.char_class = "Human", "Mage"
    assert c.spellcasting_group() == "wizard"
    assert c.spell_limit() == cr.intelligence_mods(11).max_spells_per_level  # 7
    assert c.spells_left() == 7 and c.can_add_spell()
    c.spells = list("abcdefg")                            # 7 chosen -> full
    assert c.spells_left() == 0 and not c.can_add_spell()


def test_wizard_high_intelligence_is_unlimited():
    c = _with(Intelligence=19); c.race, c.char_class = "Human", "Mage"
    assert c.spell_limit() is None and c.spells_left() is None
    c.spells = list("abcdefghij")
    assert c.can_add_spell()                              # no cap at Int 19+ ("All")


def test_priest_spell_limit_from_wisdom_slots():
    c = _with(Wisdom=14); c.race, c.char_class = "Human", "Cleric"
    assert c.spellcasting_group() == "priest"
    assert c.spell_limit() == 3                           # 1 base + 2 Wis bonus
    c.spells = ["x", "y", "z"]
    assert c.spells_left() == 0 and not c.can_add_spell()


def test_noncaster_has_no_spell_limit():
    c = _with(); c.race, c.char_class = "Human", "Fighter"
    assert c.spell_limit() is None and c.can_add_spell()


def test_out_of_range_scores_flagged():
    c = _with(Strength=19, Charisma=2)
    assert c.has_all_abilities()
    assert not c.abilities_valid()
    assert set(c.invalid_abilities()) == {("Strength", 19), ("Charisma", 2)}


def test_clear_abilities_resets():
    c = _with()
    c.exceptional_str = 50
    c.clear_abilities()
    assert c.abilities == {} and c.exceptional_str is None


# ── race adjustments + eligibility ───────────────────────────────────────────

def test_final_abilities_apply_race():
    c = _with(Constitution=14, Charisma=9)
    c.race = "Dwarf"                                   # +1 Con, -1 Cha
    fa = c.final_abilities()
    assert fa["Constitution"] == 15 and fa["Charisma"] == 8
    assert c.abilities["Constitution"] == 14           # base untouched


def test_eligible_races_and_classes():
    c = _with(**{"Strength": 13, "Dexterity": 13, "Constitution": 14,
                 "Intelligence": 11, "Wisdom": 14, "Charisma": 10})
    assert "Human" in c.eligible_races() and "Dwarf" in c.eligible_races()
    # Ranger qualifies (Str13/Dex13/Con14/Wis14); Paladin does not (needs Cha17).
    classes = c.eligible_classes()
    assert "Ranger" in classes and "Fighter" in classes and "Paladin" not in classes


def test_eligible_classes_narrow_by_race():
    c = _with(Intelligence=12)
    c.race = "Dwarf"
    assert "Mage" not in c.eligible_classes()          # dwarves can't be mages
    c.race = "Elf"
    assert "Mage" in c.eligible_classes()


def test_eligible_classes_empty_without_full_scores():
    c = ch.Character()
    c.assign_ability("Strength", 15)
    assert c.eligible_classes() == [] and c.eligible_races() == []


# ── alignment restrictions ───────────────────────────────────────────────────

def test_alignment_options_reflect_class():
    c = _with()
    assert len(c.eligible_alignments()) == 9           # no class chosen -> all
    c.char_class = "Paladin"
    assert c.eligible_alignments() == ["Lawful Good"]
    c.char_class = "Fighter"
    assert len(c.eligible_alignments()) == 9


# ── derived statistics ───────────────────────────────────────────────────────

def test_derived_combat_stats():
    c = _with(Constitution=16)
    c.race, c.char_class = "Human", "Fighter"
    assert c.hit_die() == 10
    assert c.max_hp() == 10 + 2                         # d10 max + Con-16 warrior bonus
    assert c.thac0() == 20 and c.attack_bonus() == 0
    assert c.saving_throws()["Spell"] == 17
    assert c.weapon_slots() == 4 and c.nonweapon_slots() == 3 + 2  # Fighter 3 + Int-11 bonus (2)


def test_house_ruled_mage_hp_uses_d6():
    c = _with(Constitution=15, Intelligence=12)
    c.race, c.char_class = "Human", "Mage"
    assert c.hit_die() == 6                             # house rule
    assert c.max_hp() == 6 + 1                          # d6 + Con-15 (+1)
    c.house_rules = False
    assert c.hit_die() == 4 and c.max_hp() == 4 + 1


def test_derived_stats_none_without_class():
    c = _with()
    assert c.thac0() is None and c.max_hp() is None and c.saving_throws() is None


def test_rogue_attacks_as_priest_under_house_rules():
    c = _with(Dexterity=12)
    c.race, c.char_class = "Human", "Thief"
    assert c.thac0(3) == 20                             # priest rate (house rule)
    c.house_rules = False
    assert c.thac0(3) == 19                             # standard rogue table


def test_exceptional_strength_only_for_warrior_18():
    c = _with(Strength=18)
    c.race, c.char_class = "Human", "Fighter"
    assert c.rolls_exceptional_strength() is True
    c.char_class = "Mage"
    assert c.rolls_exceptional_strength() is False      # wizards don't
    c.char_class, c.race = "Fighter", "Halfling"
    assert c.rolls_exceptional_strength() is False      # halfling fighters don't


def test_xp_bonus_from_prime_requisites():
    c = _with(Strength=16)
    c.char_class = "Fighter"
    assert c.xp_bonus() is True
    c2 = _with(Strength=15)
    c2.char_class = "Fighter"
    assert c2.xp_bonus() is False


def test_max_level_from_race_and_class():
    c = _with()
    c.race, c.char_class = "Dwarf", "Fighter"
    assert c.max_level() == 15
    c.race = "Human"
    assert c.max_level() is None                        # unlimited


# ── serialization ─────────────────────────────────────────────────────────────

def test_round_trip_serialization():
    c = _with(Strength=18)
    c.name, c.race, c.char_class, c.alignment = "Gornak", "Human", "Fighter", "Lawful Good"
    c.exceptional_str = 87
    c.age_level = 2
    restored = ch.Character.from_dict(c.to_dict())
    assert restored.name == "Gornak" and restored.race == "Human"
    assert restored.char_class == "Fighter" and restored.exceptional_str == 87
    assert restored.abilities == c.abilities
    assert restored.perception() == c.perception() and restored.age_level == 2
    assert restored.attack_bonus() == c.attack_bonus()


# ── house-rule Perception + aging ─────────────────────────────────────────────

def test_perception_is_a_seventh_house_rule_ability():
    c = ch.Character()
    assert "Perception" in c.ability_names() and len(c.ability_names()) == 7
    c.assign_ability("Perception", 16)
    assert c.perception() == 16 and c.perception_mods().surprise == 1
    assert c.has_all_abilities() is False              # the six standard ones aren't set yet


def test_no_perception_without_house_rules():
    c = ch.Character(house_rules=False)
    assert "Perception" not in c.ability_names() and len(c.ability_names()) == 6
    with pytest.raises(ValueError):
        c.assign_ability("Perception", 12)             # not an ability when house rules are off


def test_aging_effects_are_cumulative_or_none():
    c = ch.Character()
    assert c.aging_effects() is None                   # age_level 0
    c.age_level = 1
    assert c.aging_effects() == (2, 1)
    c.age_level = 3
    assert c.aging_effects() == (10, 4)


# ── proficiency budgets + skills ─────────────────────────────────────────────

def test_proficiency_slot_budgets():
    c = _with(Intelligence=13)
    c.race, c.char_class = "Human", "Fighter"
    assert c.weapon_slots_total() == 4
    assert c.nonweapon_slots_total() == 3 + 3           # Fighter 3 + Int-13 bonus (3)
    c.weapon_profs = ["Long Sword", "Light Crossbow"]   # 1 + 0 (crossbow free)
    assert c.weapon_slots_used() == 1 and c.weapon_slots_left() == 3
    c.weapon_profs.append("Long Bow")                   # +2 (house rule)
    assert c.weapon_slots_used() == 3


def test_proficiency_skill_uses_house_rule_extra_slots():
    c = _with(Strength=15, Intelligence=13)
    c.race, c.char_class = "Human", "Fighter"
    c.nonweapon_profs = {"Swimming": 1}                 # base cost, Str check +0
    assert c.proficiency_skill("Swimming") == 15
    c.nonweapon_profs["Swimming"] = 3                   # 2 extra slots -> +4 (house rule)
    assert c.proficiency_skill("Swimming") == 15 + 4
    c.nonweapon_profs["Mountaineering"] = 2             # no ability check (special)
    assert c.proficiency_skill("Mountaineering") is None


def test_can_buy_ambidexterity_warrior_or_rogue_only():
    c = _with()
    c.race, c.char_class = "Human", "Fighter"
    assert c.can_buy_ambidexterity() is True
    c.char_class = "Mage"
    assert c.can_buy_ambidexterity() is False
    c.char_class = "Fighter"; c.ambidextrous = True
    assert c.can_buy_ambidexterity() is False           # already ambidextrous


def test_serialization_preserves_proficiencies():
    c = _with()
    c.race, c.char_class = "Human", "Fighter"
    c.weapon_profs = ["Long Sword"]
    c.nonweapon_profs = {"Swimming": 2}
    c.bought_ambidexterity = True
    r = ch.Character.from_dict(c.to_dict())
    assert r.weapon_profs == ["Long Sword"] and r.nonweapon_profs == {"Swimming": 2}
    assert r.bought_ambidexterity is True


# ── equipment & spells ───────────────────────────────────────────────────────

def test_equipment_derived_stats():
    c = _with(Dexterity=16)
    c.race, c.char_class = "Human", "Fighter"
    armor = cr.items_in_category("Armor")[0]["name"]
    c.inventory = {armor: 1}
    c.worn = [armor]
    worn_ac = c.armor_class()
    c.worn = []
    assert c.armor_class() < worn_ac                       # wearing armor improves AC
    assert c.total_weight() >= (cr.item(armor).get("weight") or 0)
    assert c.spellcasting_group() is None                  # a fighter casts nothing
    c.char_class = "Mage"
    assert c.spellcasting_group() == "wizard"
    c.char_class = "Cleric"
    assert c.spellcasting_group() == "priest"


def test_serialization_preserves_equipment_and_spells():
    import json
    c = _with()
    c.race, c.char_class = "Human", "Cleric"
    c.money_cp = 12345
    c.inventory = {"Gambeson, Body": 1}
    c.worn = ["Gambeson, Body"]
    c.spells = ["Bless", "Cure Light Wounds"]
    r = ch.Character.from_dict(json.loads(json.dumps(c.to_dict())))
    assert r.money_cp == 12345 and r.inventory == c.inventory
    assert r.worn == c.worn and r.spells == c.spells

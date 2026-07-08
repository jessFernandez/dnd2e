"""Tests for char_rules.py — the structured 2e character-creation model.

Values are checked against the imported PHB/DMG tables (the spot-checks below cite
their table numbers). The house-rule tests pin the campaign overrides so they
can't silently drift from calculator.py or the prose in setup_house_rules.py.
"""
import pytest

import char_rules as cr


# ── Ability modifier tables (PHB Tables 1–6) ─────────────────────────────────

def test_strength_core_values():
    assert cr.strength_mods(18).hit == 1 and cr.strength_mods(18).dmg == 2
    assert cr.strength_mods(3).hit == -3
    assert cr.strength_mods(1).bend_bars == 0
    assert cr.strength_mods(25).dmg == 14 and cr.strength_mods(25).bend_bars == 99


def test_exceptional_strength_bands():
    assert cr.strength_mods(18, "18/76-90").dmg == 4
    assert cr.strength_mods(18, "18/00").hit == 3
    # a percentile roll resolves to the right band
    assert cr.strength_mods(18, 85).dmg == 4          # 76–90
    assert cr.strength_mods(18, 50).dmg == 3          # 01–50
    assert cr.strength_mods(18, 100).hit == 3         # 00
    # without the percentile, an 18 is the ordinary 18 row
    assert cr.strength_mods(18).dmg == 2


def test_dexterity_defensive_ac_is_negative_when_good():
    assert cr.dexterity_mods(18).defensive_ac == -4
    assert cr.dexterity_mods(3).defensive_ac == 4
    assert cr.dexterity_mods(12).defensive_ac == 0    # 7–14 band


def test_constitution_warrior_gets_higher_bonus():
    con = cr.constitution_mods(18)
    assert con.hp_adj == 2 and con.hp_adj_warrior == 4
    assert cr.constitution_mods(3).hp_adj == -2


def test_intelligence_spell_columns():
    assert cr.intelligence_mods(9).max_spell_level == 4
    assert cr.intelligence_mods(18).learn_spell == 85
    assert cr.intelligence_mods(19).max_spells_per_level == 999   # "All"


def test_wisdom_priest_bonus_spells_are_cumulative():
    # Table 5: a Wis-18 priest gets 2×1st, 2×2nd, 1×3rd, 1×4th.
    assert cr.priest_bonus_spells(18) == {1: 2, 2: 2, 3: 1, 4: 1}
    assert cr.priest_bonus_spells(13) == {1: 1}
    assert cr.priest_bonus_spells(12) == {}            # none below 13
    assert cr.wisdom_mods(3).magic_defense == -3


def test_priest_spell_slots_level1_includes_only_castable_bonus():
    assert cr.priest_spell_slots(1, 10) == {1: 1}      # base only, no bonus below Wis 13
    assert cr.priest_spell_slots(1, 14) == {1: 3}      # 1 base + 2 bonus (Wis 13,14)
    # a level-1 priest can't cast 2nd+ level spells, so those bonus spells don't apply
    assert cr.priest_spell_slots(1, 18) == {1: 3}


def test_charisma_henchmen_and_reaction():
    assert cr.charisma_mods(18).max_henchmen == 15
    assert cr.charisma_mods(18).loyalty_base == 8
    assert cr.charisma_mods(1).reaction == -7


def test_generic_ability_mods_dispatch():
    assert cr.ability_mods("Wisdom", 16).magic_defense == 2
    assert cr.ability_mods("Charisma", 9).max_henchmen == 4


def test_perception_takes_surprise_from_dex_and_illusion_from_int():
    # surprise adjustment mirrors the Dexterity reaction column, indexed by the
    # Perception score (house rule moves it off Dexterity)
    assert cr.perception_mods(16).surprise == cr.dexterity_mods(16).reaction == 1
    assert cr.perception_mods(3).surprise == -3
    assert cr.perception_mods(18).surprise == 2
    # illusion immunity only kicks in at 19+ (unreachable by a roll, modelled anyway)
    assert cr.perception_mods(15).illusion_immunity == 0
    assert cr.perception_mods(19).illusion_immunity == 1
    assert cr.perception_mods(25).illusion_immunity == 7
    assert cr.ability_mods("Perception", 17).surprise == 2       # dispatch by name


def test_house_abilities_adds_perception_only_under_house_rules():
    ha = cr.house_abilities(True)
    assert ha[-1] == "Perception" and len(ha) == 7 and ha[:6] == cr.ABILITIES
    assert cr.house_abilities(False) == cr.ABILITIES


# ── Races (Tables 7, 8, DMG Table 7) ─────────────────────────────────────────

def test_racial_adjustments_applied():
    base = {"Strength": 10, "Dexterity": 12, "Constitution": 13, "Charisma": 14}
    dwarf = cr.apply_racial_adjustments("Dwarf", base)
    assert dwarf["Constitution"] == 14 and dwarf["Charisma"] == 13
    assert base["Constitution"] == 13                  # original untouched
    halfling = cr.apply_racial_adjustments("Halfling", base)
    assert halfling["Dexterity"] == 13 and halfling["Strength"] == 9


def test_racial_requirements_pass_and_fail():
    ok = {"Strength": 10, "Dexterity": 10, "Constitution": 12,
          "Intelligence": 10, "Wisdom": 10, "Charisma": 10}
    assert cr.meets_racial_requirements("Dwarf", ok) == []
    low_con = dict(ok, Constitution=9)                 # dwarf needs Con ≥ 11
    fails = cr.meets_racial_requirements("Dwarf", low_con)
    assert fails == [("Constitution", 11, 18, 9)]


def test_race_base_movement():
    # PHB: humans/elves/half-elves move 12; dwarves/gnomes/halflings move 6.
    assert cr.RACES["Human"].movement == 12 and cr.RACES["Elf"].movement == 12
    assert cr.RACES["Half-Elf"].movement == 12
    assert cr.RACES["Dwarf"].movement == 6 and cr.RACES["Gnome"].movement == 6
    assert cr.RACES["Halfling"].movement == 6


def test_race_class_permissions_and_level_limits():
    assert cr.race_allows("Human", "Paladin") is True
    assert cr.race_allows("Dwarf", "Mage") is False
    assert cr.race_allows("Elf", "Mage") is True
    assert cr.max_level("Human", "Fighter") is None    # unlimited
    assert cr.max_level("Dwarf", "Fighter") == 15
    assert cr.max_level("Halfling", "Thief") == 15
    assert cr.max_level("Half-Elf", "Bard") is None    # U in DMG Table 7
    with pytest.raises(ValueError):
        cr.max_level("Dwarf", "Mage")


# ── Classes: requirements, XP, HD, THAC0, saves (Tables 13, 14/20/23/25, 53, 60)

def test_class_minimums():
    assert cr.meets_class_minimums("Fighter", {"Strength": 9}) == []
    assert cr.meets_class_minimums("Fighter", {"Strength": 8}) == [("Strength", 9, 8)]
    paladin_fail = cr.meets_class_minimums(
        "Paladin", {"Strength": 12, "Constitution": 9, "Wisdom": 13, "Charisma": 16})
    assert paladin_fail == [("Charisma", 17, 16)]


def test_xp_thresholds_and_level_lookup():
    assert cr.xp_for_level("Fighter", 1) == 0
    assert cr.xp_for_level("Fighter", 9) == 250000
    assert cr.xp_for_level("Mage", 2) == 2500
    assert cr.xp_for_level("Paladin", 3) == 4500       # shares the Ranger table
    assert cr.level_for_xp("Fighter", 0) == 1
    assert cr.level_for_xp("Fighter", 2000) == 2
    assert cr.level_for_xp("Fighter", 1999) == 1
    assert cr.level_for_xp("Fighter", 10 ** 9) == 20   # capped at tabulated max


def test_thac0_matches_phb_table_53():
    # Standard progressions, verified against Calculated THAC0s (Table 53).
    assert cr.thac0("Fighter", 1, house_rules=False) == 20
    assert cr.thac0("Fighter", 20, house_rules=False) == 1
    assert cr.thac0("Cleric", 4, house_rules=False) == 18
    assert cr.thac0("Cleric", 19, house_rules=False) == 8
    assert cr.thac0("Thief", 3, house_rules=False) == 19    # rogue: 1 per 2 levels
    assert cr.thac0("Thief", 20, house_rules=False) == 11
    assert cr.thac0("Mage", 4, house_rules=False) == 19     # wizard: 1 per 3 levels
    assert cr.thac0("Mage", 20, house_rules=False) == 14


def test_saving_throws_table_60():
    warrior1 = cr.saving_throws("Fighter", 1)
    assert warrior1["Paralyzation/Poison/Death"] == 14 and warrior1["Spell"] == 17
    assert cr.saving_throws("Cleric", 1)["Rod/Staff/Wand"] == 14
    assert cr.saving_throws("Mage", 1)["Spell"] == 12
    assert cr.saving_throws("Thief", 21)["Rod/Staff/Wand"] == 4   # 21+ band


# ── House-rule override layer ────────────────────────────────────────────────

def test_hit_die_house_rules():
    assert cr.hit_die("Mage") == 6 and cr.hit_die("Mage", house_rules=False) == 4
    assert cr.hit_die("Thief") == 8 and cr.hit_die("Thief", house_rules=False) == 6
    assert cr.hit_die("Fighter") == 10                 # warriors unchanged


def test_max_hp_first_level_uses_house_hd_and_warrior_con():
    # Fighter d10 + Con-18 warrior bonus (+4) = 14.
    assert cr.max_hp_at_first_level("Fighter", 18) == 14
    # House-ruled mage: d6 (not d4) + Con-15 (+1) = 7.
    assert cr.max_hp_at_first_level("Mage", 15) == 7
    assert cr.max_hp_at_first_level("Mage", 15, house_rules=False) == 5


def test_rogue_attacks_at_priest_rate_under_house_rules():
    # House rule: rogues advance like priests (⅔/level).
    assert cr.thac0("Thief", 3) == cr.thac0("Cleric", 3) == 20
    assert cr.thac0("Thief", 7) == cr.thac0("Cleric", 7) == 16
    # ...and worse than the standard rogue table would give at low level.
    assert cr.thac0("Thief", 3, house_rules=False) == 19


def test_attack_bonus_is_20_minus_thac0():
    assert cr.attack_bonus("Fighter", 1) == 0
    assert cr.attack_bonus("Fighter", 11) == 10        # THAC0 10 -> +10
    # unify: char_rules and calculator agree on the conversion
    import calculator
    assert calculator.thac0_to_bonus(15) == cr.thac0_to_bonus(15) == 5


def test_proficiency_slots():
    assert cr.weapon_slots("Fighter", 1) == 4
    assert cr.weapon_slots("Fighter", 4) == 5          # +1 every 3 levels
    assert cr.nonweapon_slots("Mage", 1) == 4
    assert cr.nonweapon_slots("Mage", 4) == 5
    assert cr.nonproficiency_penalty("Mage") == -5
    # Intelligence grants bonus nonweapon slots (optional rule): Int 14 -> +4.
    assert cr.nonweapon_slots("Fighter", 1, int_score=14) == 3 + 4


def test_house_rule_weapon_slot_costs():
    assert cr.weapon_slot_cost("crossbow") == 0
    assert cr.weapon_slot_cost("Long Bow") == 2
    assert cr.weapon_slot_cost("long sword") == 1
    assert cr.weapon_slot_cost("crossbow", house_rules=False) == 1


def test_house_rule_proficiency_bonus_and_check_target():
    assert cr.proficiency_bonus_per_slot() == 2
    assert cr.proficiency_bonus_per_slot(house_rules=False) == 1
    assert cr.proficiency_check_target() == 21
    assert cr.proficiency_check_target(house_rules=False) is None


def test_aging_is_cumulative():
    assert cr.aging_totals(1) == (2, 1)
    assert cr.aging_totals(2) == (7, 2)                # 2+5 penalty, 1+1 bonus
    assert cr.aging_totals(3) == (10, 4)               # +3 penalty, +2 bonus
    with pytest.raises(ValueError):
        cr.aging_totals(4)


def test_ambidexterity_house_rules():
    assert cr.is_ambidextrous("Human", "Ranger") is True          # rangers always
    assert cr.is_ambidextrous("Human", "Fighter", handedness_roll=10) is True
    assert cr.is_ambidextrous("Human", "Fighter", handedness_roll=4) is False
    assert cr.HOUSE_RULES.ambidexterity_slot_cost == 1


def test_xp_bonus_requires_all_prime_requisites_16():
    assert cr.xp_bonus_qualifies("Fighter", {"Strength": 16}) is True
    assert cr.xp_bonus_qualifies("Fighter", {"Strength": 15}) is False
    # Ranger needs Str, Dex, AND Wis all ≥ 16.
    assert cr.xp_bonus_qualifies("Ranger", {"Strength": 16, "Dexterity": 16, "Wisdom": 16}) is True
    assert cr.xp_bonus_qualifies("Ranger", {"Strength": 16, "Dexterity": 16, "Wisdom": 15}) is False


# ── Character-level convenience ──────────────────────────────────────────────

def test_eligible_classes_respects_minimums_and_race():
    abilities = {"Strength": 9, "Dexterity": 9, "Constitution": 10,
                 "Intelligence": 9, "Wisdom": 9, "Charisma": 10}
    human = cr.eligible_classes(abilities)
    assert "Fighter" in human and "Mage" in human and "Cleric" in human and "Thief" in human
    assert "Paladin" not in human                      # needs Cha 17
    # A dwarf with the same stats can't be a mage even though the stats qualify.
    dwarf = cr.eligible_classes(abilities, race="Dwarf")
    assert "Mage" not in dwarf and "Fighter" in dwarf


def test_eligible_races():
    strong = {"Strength": 12, "Dexterity": 12, "Constitution": 12,
              "Intelligence": 12, "Wisdom": 12, "Charisma": 12}
    races = cr.eligible_races(strong)
    assert "Human" in races and "Dwarf" in races
    # Elf needs Dex ≥ 6 and Int ≥ 8; drop Int below 8 to disqualify.
    assert "Elf" not in cr.eligible_races(dict(strong, Intelligence=5))


def test_proficiency_book_is_well_formed():
    # The campaign sourcebook loads as data (from nonweapon_book.py): every skill
    # has the schema the charactermancer relies on, and no prerequisite dangles.
    assert cr.PROFICIENCY_BOOK and len(cr.NONWEAPON_PROFICIENCIES) == 88
    allowed_abilities = ("",) + cr.ABILITIES + (cr.PERCEPTION,)
    for name, p in cr.NONWEAPON_PROFICIENCIES.items():
        assert p.name == name and p.slots >= 0
        assert p.source == cr.PROFICIENCY_BOOK
        assert p.ability in allowed_abilities
        assert all(cls in ("Warrior", "Rogue", "Wizard", "Priest") for cls in p.classes)
        assert all(req in cr.NONWEAPON_PROFICIENCIES for req in p.prereq)
    # spot-check rows transcribed from the sheet
    assert cr.NONWEAPON_PROFICIENCIES["Healing"].slots == 1
    assert cr.NONWEAPON_PROFICIENCIES["Healing"].prereq == ("Anatomy",)
    assert cr.NONWEAPON_PROFICIENCIES["Swimming"].ability == "Strength"
    assert cr.NONWEAPON_PROFICIENCIES["Alchemy"].classes == ("Wizard",)


def test_proficiency_class_filtering_and_prereqs():
    assert cr.proficiency_available("Alchemy", "Mage")          # wizard-only skill
    assert not cr.proficiency_available("Alchemy", "Fighter")
    assert cr.proficiency_available("Swimming", "Thief")        # no class list = open to all
    assert not cr.proficiency_prereqs_met("Healing", set())
    assert cr.proficiency_prereqs_met("Healing", {"Anatomy"})
    assert cr.proficiency_dependents("Anatomy", {"Healing", "Swimming"}) == ["Healing"]
    for p in cr.proficiencies_for_class("Cleric"):             # self-consistent filter
        assert cr.proficiency_available(p, "Cleric")


# ── equipment: money, AC, encumbrance, item catalog ──────────────────────────

def test_starting_money_armor_class_encumbrance():
    import random
    cp = cr.roll_starting_money("Fighter", random.Random(0))
    assert cp % 100 == 0 and 5000 <= cp <= 20000          # 5d4×10 gp → cp
    assert cr.armor_class(0, 10) == 10                     # base, no Dex bonus
    assert cr.armor_class(3, 10) == 13                     # +3 armor
    assert cr.armor_class(0, 18) == 14                     # Dex 18 → +4 ascending
    assert cr.asc_to_desc(cr.armor_class(0, 18)) == 20 - 14
    assert cr.encumbrance_status(1, 15) == "Unencumbered"
    assert cr.encumbrance_status(10_000, 10) == "Overloaded"


def test_item_catalog_loaded():
    assert len(cr.ITEMS) > 100
    armor = cr.items_in_category("Armor")
    assert armor and all("ac_bonus" in a for a in armor)
    assert any(w.get("damage") for w in cr.items_in_category("Weapon"))
    assert cr.item(armor[0]["name"])["category"] == "Armor"
    assert cr.item("not-a-real-item") is None

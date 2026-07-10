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


# ── Spell progression (PHB Tables 21, 24, 17, 18, 32) ────────────────────────

def test_wizard_progression_matches_table_21():
    assert cr.wizard_spell_slots(1) == {1: 1}
    assert cr.wizard_spell_slots(5) == {1: 4, 2: 2, 3: 1}
    assert cr.wizard_spell_slots(12) == {1: 4, 2: 4, 3: 4, 4: 4, 5: 4, 6: 1}
    assert cr.wizard_spell_slots(20) == {1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 4, 7: 3, 8: 3, 9: 2}


def test_intelligence_caps_the_highest_wizard_spell_level():
    # Int 9 -> max spell level 4, so a 12th-level mage loses his 5th and 6th
    assert cr.wizard_spell_slots(12, int_score=9) == {1: 4, 2: 4, 3: 4, 4: 4}
    assert cr.max_spell_level("Mage", 20, int_score=18) == 9


def test_specialist_wizard_gains_one_extra_spell_per_level():
    assert cr.wizard_spell_slots(5) == {1: 4, 2: 2, 3: 1}
    assert cr.spell_slots("Illusionist", 5, int_score=18) == {1: 5, 2: 3, 3: 2}
    assert cr.spell_slots("Mage", 5, int_score=18) == {1: 4, 2: 2, 3: 1}   # not a specialist


def test_priest_progression_matches_table_24_with_wisdom_bonus():
    # base row 9 is 4/4/3/2/1; Wis 13 adds one 1st-level bonus spell
    assert cr.priest_spell_slots(9, 13) == {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}
    assert cr.priest_spell_slots(9, 10) == {1: 4, 2: 4, 3: 3, 4: 2, 5: 1}   # no bonus


def test_priest_top_two_spell_levels_are_gated_on_wisdom():
    # Table 24 footnotes: 6th needs Wis 17+, 7th needs Wis 18+
    assert 6 not in cr.priest_spell_slots(11, 16)
    assert 6 in cr.priest_spell_slots(11, 17)
    assert 7 not in cr.priest_spell_slots(14, 17)
    assert 7 in cr.priest_spell_slots(14, 18)


def test_paladin_and_ranger_cast_late_and_get_no_wisdom_bonus():
    assert cr.spell_slots("Paladin", 8) == {}           # nothing before 9th
    assert cr.spell_slots("Paladin", 9) == {1: 1}
    assert cr.spell_slots("Ranger", 7) == {}            # nothing before 8th
    assert cr.spell_slots("Ranger", 8) == {1: 1}
    # PHB is explicit: neither gains bonus spells for high Wisdom
    assert cr.spell_slots("Paladin", 9, wis=18) == {1: 1}
    assert cr.spell_slots("Ranger", 8, wis=18) == {1: 1}
    # a ranger's slots stop improving after the table's last row (16th)
    assert cr.spell_slots("Ranger", 20) == cr.spell_slots("Ranger", 16) == {1: 3, 2: 3, 3: 3}


def test_bard_casts_wizard_spells_from_second_level():
    assert cr.spell_slots("Bard", 1, int_score=16) == {}
    assert cr.spell_slots("Bard", 2, int_score=16) == {1: 1}
    assert cr.spell_slots("Bard", 20, int_score=18) == {1: 4, 2: 4, 3: 4, 4: 4, 5: 4, 6: 3}


def test_spell_caster_group_and_noncasters():
    assert cr.spell_caster_group("Mage") == "wizard"
    assert cr.spell_caster_group("Bard") == "wizard"      # bards cast wizard spells
    assert cr.spell_caster_group("Cleric") == "priest"
    assert cr.spell_caster_group("Paladin") == "priest"   # ...and paladins priest spells
    assert cr.spell_caster_group("Ranger") == "priest"
    for cls in ("Fighter", "Thief"):
        assert cr.spell_caster_group(cls) is None
        assert cr.spell_slots(cls, 20) == {}
        assert cr.max_spell_level(cls, 20) == 0


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


# ── Leveling: HP accumulation + attacks per round ────────────────────────────

def test_hp_die_levels_stops_at_name_level():
    # Warriors stop rolling HD after 9th; wizards after 10th.
    assert [cr.hp_die_levels("Fighter", n) for n in (1, 2, 9, 10, 15)] == [0, 1, 8, 8, 8]
    assert cr.hp_die_levels("Mage", 12) == 9


def test_hp_at_level_1_matches_best_case():
    assert cr.hp_at_level("Fighter", 1, 16, []) == cr.max_hp_at_first_level("Fighter", 16)


def test_hp_accumulates_roll_plus_con_per_hit_die():
    b = cr.con_hp_bonus("Fighter", 16)                 # +2 per HD for a warrior
    assert cr.hp_at_level("Fighter", 3, 16, [5, 6]) == (10 + b) + (5 + b) + (6 + b)


def test_hp_past_name_level_is_flat_with_no_die_or_con():
    b = cr.con_hp_bonus("Fighter", 16)
    hp = cr.hp_at_level("Fighter", 11, 16, [6] * 8)    # 8 rolled HD, then 2 flat levels
    assert hp == (10 + b) + 8 * (6 + b) + 2 * cr.GROUPS["Warrior"].hp_after


def test_each_level_yields_at_least_one_hp():
    # Mage (house d6) with Con 3 (-2/HD): a rolled 1 would be -1, clamped to +1.
    assert cr.hp_at_level("Mage", 2, 3, [1]) == cr.max_hp_at_first_level("Mage", 3) + 1


def test_hp_at_level_requires_enough_rolls():
    with pytest.raises(ValueError):
        cr.hp_at_level("Fighter", 5, 16, [4, 5])       # needs 4 rolls, given 2


def test_attacks_per_round_warriors_only():
    assert [cr.attacks_per_round("Fighter", n) for n in (1, 6, 7, 12, 13, 20)] == \
        [(1, 1), (1, 1), (3, 2), (3, 2), (2, 1), (2, 1)]
    assert cr.attacks_per_round("Paladin", 7) == (3, 2)   # paladins/rangers are warriors
    assert cr.attacks_per_round("Ranger", 13) == (2, 1)
    for cls in ("Mage", "Cleric", "Thief"):
        assert cr.attacks_per_round(cls, 20) == (1, 1)    # never advances


# ── Combat & Tactics: weapon groups + barred weapons (CT Ch4/Ch7) ────────────

def test_every_weapon_has_group_and_access_data():
    # data integrity: the CT tables must cover the whole roster, no strays
    assert set(cr.WEAPON_TIGHT_GROUPS) == set(cr.WEAPONS)
    assert set(cr.WEAPON_ACCESS) == set(cr.WEAPONS)
    for w in cr.WEAPONS:
        for tight in cr.weapon_tight_groups(w):
            assert tight in cr.TIGHT_TO_BROAD, f"{w}: tight group {tight} has no broad group"


def test_weapon_belongs_to_several_tight_groups():
    # CT/DD02744: a short sword is Ancient, Middle Eastern and Short
    assert cr.weapon_tight_groups("Short Sword") == ("Ancient", "Middle Eastern", "Short")
    assert cr.weapon_tight_groups("Broad Sword") == ("Ancient", "Roman", "Medium")
    assert cr.weapon_broad_groups("Short Sword") == ("Swords",)   # all three roll up to Swords


def test_weapons_outside_any_group():
    # "Unrelated" is not a group; absent weapons belong to none.
    for w in ("Trident", "Quarterstaff", "Sling"):
        assert cr.weapon_tight_groups(w) == ()
        assert cr.weapon_broad_groups(w) == ()


def test_weapon_group_members():
    assert cr.weapon_group_members("Crossbows") == ("Light Crossbow", "Heavy Crossbow")
    assert cr.weapon_group_members("Bows") == ("Short Bow", "Long Bow")
    assert cr.weapon_group_members("Large") == ("Bastard Sword", "Two-Handed Sword")
    assert cr.weapon_group_members("Nonexistent") == ()


def test_familiarity_is_union_over_tight_groups():
    # proficient in Short Sword -> familiar with everything sharing any of its
    # three tight groups: Broad Sword (Ancient), Scimitar (Middle Eastern), Dagger (Short)
    profs = ["Short Sword"]
    for w in ("Broad Sword", "Scimitar", "Dagger"):
        assert cr.is_familiar(w, profs), w
    assert not cr.is_familiar("Short Sword", profs)      # already proficient
    assert not cr.is_familiar("Halberd", profs)          # unrelated group
    assert not cr.is_familiar("Quarterstaff", profs)     # group-less: never familiar
    # crossbows are their own tight group
    assert cr.is_familiar("Heavy Crossbow", ["Light Crossbow"])


def test_barred_weapon_penalty_matches_ct_worked_example():
    # CT/DD02624: a wizard pays 2 slots total for a long sword (available to rogues)
    # and 3 for a two-handed sword (warrior-only). Base cost is 1 slot.
    assert 1 + cr.barred_weapon_penalty("Long Sword", "Mage") == 2
    assert 1 + cr.barred_weapon_penalty("Two-Handed Sword", "Mage") == 3
    # rogues/priests reaching for a warrior weapon pay one extra slot
    assert cr.barred_weapon_penalty("Two-Handed Sword", "Thief") == 1
    assert cr.barred_weapon_penalty("Halberd", "Cleric") == 1
    # nobody is barred from their own tier, and warriors are never barred
    assert cr.barred_weapon_penalty("Dagger", "Mage") == 0
    assert cr.barred_weapon_penalty("Long Sword", "Thief") == 0
    for w in cr.WEAPONS:
        assert cr.barred_weapon_penalty(w, "Fighter") == 0


def test_weapon_rung_ladder_is_class_and_level_gated():
    # Only a single-class fighter climbs past specialisation, and only with levels.
    assert cr.weapon_rung_ladder("Fighter", 1) == ("proficient", "specialist")
    assert cr.weapon_rung_ladder("Fighter", 5) == ("proficient", "specialist", "master")
    assert cr.weapon_rung_ladder("Fighter", 6)[-1] == "high_master"
    assert cr.weapon_rung_ladder("Fighter", 9)[-1] == "grand_master"
    # paladins and rangers take expertise instead, and stop there
    for cls in ("Paladin", "Ranger"):
        assert cr.weapon_rung_ladder(cls, 20) == ("proficient", "expert")
    # everyone else stops at proficiency, however high they climb
    for cls in ("Mage", "Cleric", "Thief", "Bard"):
        assert cr.weapon_rung_ladder(cls, 20) == ("proficient",)
    assert cr.max_weapon_rung("Fighter", 9) == "grand_master"


def test_rung_costs_layer_house_rules_and_barred_penalty_on_ct():
    # CT: proficiency 1 slot, expertise/specialisation 2, mastery 3, high 4, grand 5
    for rung, total in (("proficient", 1), ("specialist", 2), ("master", 3),
                        ("high_master", 4), ("grand_master", 5)):
        assert cr.weapon_prof_cost("Long Sword", rung, "Fighter") == total
    # house rules ride on top of the proficiency slot: crossbows free, bows cost 2
    assert cr.weapon_prof_cost("Light Crossbow", "proficient", "Fighter") == 0
    assert cr.weapon_prof_cost("Light Crossbow", "specialist", "Fighter") == 1
    assert cr.weapon_prof_cost("Long Bow", "proficient", "Fighter") == 2
    # ...and so does the barred-weapon penalty (a wizard's long sword costs 2)
    assert cr.weapon_prof_cost("Long Sword", "proficient", "Mage") == 2


def test_next_and_prev_rung_walk_the_ladder():
    assert cr.next_weapon_rung("proficient", "Fighter", 1) == "specialist"
    assert cr.next_weapon_rung("specialist", "Fighter", 1) is None      # needs 5th
    assert cr.next_weapon_rung("specialist", "Fighter", 5) == "master"
    assert cr.next_weapon_rung("expert", "Ranger", 20) is None          # top for a ranger
    assert cr.prev_weapon_rung("master", "Fighter", 5) == "specialist"
    assert cr.prev_weapon_rung("proficient", "Fighter", 5) is None


def test_specialises_flags_the_mastery_rungs():
    assert not cr.specialises("proficient") and not cr.specialises("expert")
    for rung in ("specialist", "master", "high_master", "grand_master"):
        assert cr.specialises(rung)


def test_every_earnable_rung_has_a_gameplay_summary():
    # Every rung a class can actually climb to (beyond plain proficiency) explains
    # itself, so no bought rung shows up in the builder with no "what it does".
    earnable = set()
    for class_name in cr.CLASSES:
        for rung in cr.weapon_rung_ladder(class_name, level=20):
            if rung != "proficient":
                earnable.add(rung)
    assert earnable == {"expert", "specialist", "master", "high_master", "grand_master"}
    for rung in earnable:
        assert cr.rung_summary(rung), rung
        assert cr.rung_page(rung)


def test_unbought_rungs_have_no_summary():
    # Nothing to describe for states the player never spends a slot to reach.
    for rung in ("proficient", "familiar", "nonproficient"):
        assert cr.rung_summary(rung) == ""
        assert cr.rung_page(rung) is None


def test_rung_summaries_name_their_signature_effect():
    assert "+2 to damage" in cr.rung_summary("specialist")
    assert "+3" in cr.rung_summary("master")
    assert "16+" in cr.rung_summary("high_master")          # the better crit range
    assert "extra attack" in cr.rung_summary("grand_master")
    assert "no bonus to hit or damage" in cr.rung_summary("expert")


def test_barred_penalty_is_zero_before_a_class_is_chosen():
    assert cr.barred_weapon_penalty("Two-Handed Sword", None) == 0
    assert cr.weapon_prof_cost("Two-Handed Sword", "proficient", None) == 1


def test_shield_types_map_to_ct_table():
    assert set(cr.SHIELD_TYPES.values()) <= set(cr.SHIELD_PROFICIENCY)
    assert cr.SHIELD_TYPES["Shield, Aspis"] == "medium"          # DM ruling
    assert cr.SHIELD_PROFICIENCY["medium"]["proficient_ac"] == 3
    assert cr.SHIELD_PROFICIENCY["buckler"]["attackers"] == 1


def test_shield_keeps_its_homebrew_bonus_until_proficient():
    # The homebrew item owns the normal bonus (our aspis is +2 where CT's medium
    # shield is +1); CT's table only supplies the proficient upgrade.
    assert cr.shield_ac_bonus("Shield, Aspis") == cr.item("Shield, Aspis")["ac_bonus"] == 2
    assert cr.shield_ac_bonus("Shield, Aspis", proficient=True) == 3
    # a buckler gains no AC from proficiency, and never drops below its own value
    assert cr.shield_ac_bonus("Shield, Buckler") == 1
    assert cr.shield_ac_bonus("Shield, Buckler", proficient=True) == 1
    assert cr.shield_ac_bonus("Chain, Full") == 0                # not a shield


def test_armor_items_excludes_shields():
    items = cr.armor_items()
    assert "Chain, Full" in items and "Helm, Full" in items
    assert not any(cr.is_shield(i) for i in items)


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
    # unify: the calculator re-exports char_rules' combat math rather than owning it
    import calculator
    for name in ("thac0_to_bonus", "bonus_to_thac0", "desc_to_asc", "asc_to_desc",
                 "to_hit_need", "hit_chance", "is_critical"):
        assert getattr(calculator, name) is getattr(cr, name), name


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

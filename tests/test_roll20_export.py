"""Tests for roll20_export.py — the app -> Roll20 sheet JSON mapping."""
import char_rules as cr
import roll20_export as rx
from character import Character


def _cleric() -> Character:
    c = Character()
    for a in c.ability_names():
        c.assign_ability(a, 15)
    c.assign_ability("Wisdom", 13)
    c.assign_ability("Dexterity", 16)
    c.race, c.char_class, c.name = "Human", "Cleric", "Bryn"
    c.money_cp = 3456
    armor = cr.items_in_category("Armor")[0]["name"]
    c.inventory = {armor: 1, "Dagger": 1}
    c.worn = [armor]
    c.nonweapon_profs = {"Healing": 1, "Anatomy": 1}
    c.weapon_profs = {"Mace": "proficient"}
    c.spells = {"Bless": 1}
    return c


def test_export_core_mapping():
    c = _cleric()
    d = rx.character_to_roll20(c)
    assert d["willpower"] == 13                       # Wisdom exported as willpower
    # AC comes only from the Armor section (below); no direct armor_bonus scalar.
    assert d["armor_base"] == 10 and "armor_bonus" not in d
    assert d["move"] == 12                             # Human base movement
    assert d["attack_base"] == c.attack_bonus()
    assert (d["gp"], d["sp"], d["cp"]) == (34, 5, 6)  # 3456 cp split
    assert d["save_ppd"] == c.saving_throws()["Paralyzation/Poison/Death"]
    assert d["save_spell"] == c.saving_throws()["Spell"]


def test_export_repeating_sections():
    c = _cleric()
    d = rx.character_to_roll20(c, {"Bless": {"school": "Combat", "casting_time": "1 rd"}})
    dagger = next(w for w in d["weapons"] if w["name"] == "Dagger")
    assert dagger["damage"] == "1d4"                  # 'd4' normalized to '1d4'
    assert {"name": "Mace", "slots": 1, "rung": "proficient"} in d["weapon_profs"]
    healing = next(n for n in d["nwp"] if n["name"] == "Healing")
    assert healing["stat"] == "willpower"             # Wisdom-based prof -> willpower token
    assert healing["base"] == c.proficiency_skill("Healing") - c.final_abilities()["Wisdom"]
    assert any(g["name"] == "Dagger" for g in d["gear"])
    sp = d["spells"][0]
    assert sp["name"] == "Bless" and sp["level"] == 1 and sp["castingTime"] == 1


def test_export_armor_and_spell_details():
    c = _cleric()
    details = {"Bless": {"level": 1, "school": "Combat", "range": "60 yds", "casting_time": "1 rd",
                         "save": "None", "aoe": "50-ft cube", "duration": "6 rds", "damage": "",
                         "materials": "holy water", "components": "V, S, M",
                         "description": "Bless raises morale and to-hit."}}
    d = rx.character_to_roll20(c, details)
    # equipped armor -> armor array for the sheet's Armor section
    assert d["armor"] and d["armor"][0]["aequipped"] == 1
    assert d["armor"][0]["aac"] == cr.item(c.worn[0])["ac_bonus"]
    # spell enrichment
    sp = d["spells"][0]
    assert sp["description"].startswith("Bless")
    assert sp["save"] == "None" and sp["materials"] == "holy water"
    assert sp["verbal"] == 1 and sp["somatic"] == 1 and sp["material"] == 1


def test_export_spells_carry_their_own_level():
    c = _cleric()
    c.spells = {"Bless": 1, "Silence": 2, "Prayer": 3}
    d = rx.character_to_roll20(c)
    by_name = {s["name"]: s["level"] for s in d["spells"]}
    assert by_name == {"Bless": 1, "Silence": 2, "Prayer": 3}   # drives repeating_spells<N>


def test_export_reflects_shield_and_armor_proficiency():
    c = _cleric()
    c.inventory = {"Chain, Full": 1, "Shield, Aspis": 1}
    c.worn = ["Chain, Full", "Shield, Aspis"]
    c.shield_profs = ["Shield, Aspis"]
    c.armor_profs = ["Chain, Full"]
    d = rx.character_to_roll20(c)
    aac = {a["name"]: a["aac"] for a in d["armor"]}
    assert aac["Shield, Aspis"] == 3                # +2 -> +3 for a proficient wielder
    weights = {g["name"]: g["weight"] for g in d["gear"]}
    assert weights["Chain, Full"] == 20.0           # half encumbrance, as the builder shows
    assert weights["Shield, Aspis"] == cr.item("Shield, Aspis")["weight"]


def test_export_carries_level_and_xp():
    import random
    c = _cleric()
    d = rx.character_to_roll20(c)
    assert d["player_level"] == 1 and d["xp"] == 0      # default level-1 build
    c.set_level(6, rng=random.Random(3))
    c.xp = 55000
    d = rx.character_to_roll20(c)
    assert d["player_level"] == 6 and d["xp"] == 55000
    assert d["hp_max"] == c.max_hp()                     # HP follows the level
    assert d["attack_base"] == c.attack_bonus()          # so do THAC0-derived stats


def test_movement_by_race():
    c = _cleric()
    assert rx.character_to_roll20(c)["move"] == 12    # Human
    c.race = "Dwarf"
    assert rx.character_to_roll20(c)["move"] == 6      # demihuman
    c.race = "Halfling"
    assert rx.character_to_roll20(c)["move"] == 6


def test_money_split_and_damage_norm():
    assert rx._split_money(12345) == {"gp": 123, "sp": 4, "cp": 5}
    assert rx._split_money(0) == {"gp": 0, "sp": 0, "cp": 0}
    assert rx._norm_damage("d8") == "1d8"
    assert rx._norm_damage("2d4") == "2d4"
    assert rx._norm_damage("") == ""


# ── monster export (monster_to_roll20) ────────────────────────────────────────

from monster import Monster


def test_monster_export_maps_house_rule_numbers():
    m = Monster(name="Ankheg", hit_dice="3", thac0="17", armor_class="2",
                no_of_attacks="1", damage_attack="3-18", movement="12", size="L",
                xp_value="175", morale="Unsteady")
    j = rx.monster_to_roll20(m)
    assert j["character_name"] == "Ankheg"
    assert j["attack_base"] == 3           # 20 - 17
    assert j["armor_base"] == 18           # ascending AC (20 - 2)
    assert j["hp_max"] == 14 and j["hp"] == 14   # 3 HD * 4.5, rounded
    assert j["xp"] == 175 and j["move"] == 12 and j["player_level"] == 3


def test_monster_export_saves_as_a_warrior_of_its_hit_dice():
    j = rx.monster_to_roll20(Monster(name="Brute", hit_dice="8", armor_class="4"))
    assert j["save_ppd"] == cr.monster_saving_throws(8)["Paralyzation/Poison/Death"]
    assert j["save_bw"] == cr.monster_saving_throws(8)["Breath Weapon"]


def test_a_creature_under_one_hit_die_saves_as_a_level_0_warrior():
    """The MM writes sub-1-HD creatures as a die minus a penalty ('1-1') or straight in
    hit points ('1 hp') — both save on the level-0 Warrior band, which is worse than a
    1 HD monster's, not the same."""
    assert rx._hd_level("1-1") == 0 and rx._hd_level("1 hp") == 0
    assert rx._hd_level("1-4 hp") == 0
    assert rx._hd_level("3") == 3 and rx._hd_level("9 (40 hp)") == 9    # dice, not hp
    weak = rx.monster_to_roll20(Monster(name="Stirge", hit_dice="1-1", armor_class="8"))
    assert weak["save_ppd"] == cr.monster_saving_throws(0)["Paralyzation/Poison/Death"]
    assert weak["save_ppd"] > cr.monster_saving_throws(1)["Paralyzation/Poison/Death"]


def test_monster_hp_rounds_half_up_and_reads_the_hit_point_forms():
    assert rx._hp_from_hd("1") == 5 and rx._hp_from_hd("3") == 14      # half up, not to even
    assert rx._hp_from_hd("5+2") == 25
    assert rx._hp_from_hd("1 hp") == 1                                 # written in hit points
    assert rx._hp_from_hd("1-4 hp") == 4                               # the top of the range
    assert rx._hp_from_hd("9 (40 hp)") == 40                           # both given: trust the hp
    assert rx._hp_from_hd("") == 0


def test_monster_export_splits_attacks_into_weapons_with_size_speed():
    m = Monster(name="Cat", hit_dice="3", thac0="17", size="L",
                damage_attack="1-4 (claw)/1-4 (claw)/2-8 (bite)")
    weapons = rx.monster_to_roll20(m)["weapons"]
    assert [w["name"] for w in weapons] == ["claw", "claw", "bite"]
    assert [w["damage"] for w in weapons] == ["1d4", "1d4", "2d4"]   # ranges -> dice
    assert all(w["tohit"] == 3 for w in weapons)                     # the attack bonus
    assert all(w["speed"] == 6 for w in weapons)                     # Large -> initiative +6


def test_monster_export_uses_the_selected_tier():
    from monster import Monster as M
    age = {"kind": "age", "header_rows": 2, "rows": [
        ["", "", "", "", "", "", "", "", ""],
        ["Age", "Lgt", "Lgt", "AC", "Weapon", "Wizard", "MR", "Type", "Value"],
        ["1", "3-6", "2-5", "4", "2d4", "Nil", "Nil", "Nil", "4,000"],
        ["12", "96", "80", "-7", "24d4", "9", "45%", "Hx3", "20,000"]]}
    m = M(name="Dragon", armor_class="1 (base)", thac0="9 (base)", hit_dice="12",
          extra_tables=[age], selected_tier=1)                       # oldest age
    j = rx.monster_to_roll20(m)
    assert j["armor_base"] == 27 and j["xp"] == 20000                # AC -7 -> 27, tiered XP


def test_monster_export_links_spell_like_abilities():
    import monster_spells
    idx = monster_spells.build_index(["Charm Person", "Suggestion"])
    details = {"Charm Person": {"level": 1, "school": "Enchantment", "components": "V, S"}}
    m = Monster(name="Fiend", hit_dice="10",
                combat="It can cast charm person and suggestion at will.")
    spells = rx.monster_to_roll20(m, details, idx)["spells"]
    names = {s["name"]: s for s in spells}
    assert "Charm Person" in names and names["Charm Person"]["level"] == 1
    assert names["Charm Person"]["verbal"] == 1 and names["Charm Person"]["somatic"] == 1


def test_monster_export_no_attacks_or_spells_is_empty():
    j = rx.monster_to_roll20(Monster(name="Blob", hit_dice="2", damage_attack="Nil"))
    assert j["weapons"] == [] and j["spells"] == []

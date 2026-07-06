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
    c.weapon_profs = ["Mace"]
    c.spells = ["Bless"]
    return c


def test_export_core_mapping():
    c = _cleric()
    d = rx.character_to_roll20(c)
    assert d["willpower"] == 13                       # Wisdom exported as willpower
    assert d["armor_base"] == 10 and d["armor_bonus"] == c.worn_ac_bonus()
    assert d["attack_base"] == c.attack_bonus()
    assert (d["gp"], d["sp"], d["cp"]) == (34, 5, 6)  # 3456 cp split
    assert d["save_ppd"] == c.saving_throws()["Paralyzation/Poison/Death"]
    assert d["save_spell"] == c.saving_throws()["Spell"]


def test_export_repeating_sections():
    c = _cleric()
    d = rx.character_to_roll20(c, {"Bless": {"school": "Combat", "casting_time": "1 rd"}})
    dagger = next(w for w in d["weapons"] if w["name"] == "Dagger")
    assert dagger["damage"] == "1d4"                  # 'd4' normalized to '1d4'
    assert "Mace" in d["weapon_profs"]
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


def test_money_split_and_damage_norm():
    assert rx._split_money(12345) == {"gp": 123, "sp": 4, "cp": 5}
    assert rx._split_money(0) == {"gp": 0, "sp": 0, "cp": 0}
    assert rx._norm_damage("d8") == "1d8"
    assert rx._norm_damage("2d4") == "2d4"
    assert rx._norm_damage("") == ""

"""Tests for monster_tiers.py — HD / age scaling of a Monster (pure, Qt-free)."""
from monster import Monster
import monster_tiers as mt


# ── HD-conditional strings ────────────────────────────────────────────────────

def test_hd_conditional_thac0_becomes_tiers():
    m = Monster(thac0="5-6 HD: 15 7-8 HD: 13 9-10 HD: 11")
    ts = mt.tiers(m)
    assert [t.label for t in ts] == ["5-6 HD", "7-8 HD", "9-10 HD"]
    assert ts[0].overrides == {"hit_dice": "5-6", "thac0": "15"}
    assert ts[-1].overrides == {"hit_dice": "9-10", "thac0": "11"}


def test_hd_conditional_handles_plus_specs_and_missing_space():
    # "6+6 HD: 13 9+9 HD:11" — a '+' HD spec and a colon with no following space
    m = Monster(thac0="6+6 HD: 13 9+9 HD:11")
    assert [t.label for t in mt.tiers(m)] == ["6+6 HD", "9+9 HD"]
    assert mt.tiers(m)[1].overrides == {"hit_dice": "9+9", "thac0": "11"}


def test_single_conditional_step_is_not_a_tier():
    assert mt.tiers(Monster(thac0="8 HD: 13")) == []       # one value = the base, no choice
    assert mt.tiers(Monster(thac0="17-13")) == []          # a plain range is not tiers


def test_xp_conditional_also_scales():
    m = Monster(thac0="16+16 HD: 16 24+24 HD: 14",
                xp_value="16+16 HD: 16,000 24+24 HD: 24,000")
    ts = mt.tiers(m)
    assert ts[0].overrides == {"hit_dice": "16+16", "thac0": "16", "xp_value": "16,000"}
    assert ts[1].overrides["xp_value"] == "24,000"


def test_hp_conditional_keeps_unit_and_skips_hit_dice():
    # the Beholder writes THAC0 by hit points, not HD — the tier shouldn't claim HD
    m = Monster(thac0="45-49 hp: 11 50-59 hp: 9")
    ts = mt.tiers(m)
    assert [t.label for t in ts] == ["45-49 HP", "50-59 HP"]
    assert ts[0].overrides == {"thac0": "11"}              # no hit_dice override


# ── age tables ────────────────────────────────────────────────────────────────

def _dragon_age_table():
    return {"kind": "age", "header_rows": 2, "rows": [
        ["", "Body", "Tail", "", "Breath", "Spells", "", "Treas.", "XP"],
        ["Age", "Lgt. (')", "Lgt. (')", "AC", "Weapon", "Wizard", "MR", "Type", "Value"],
        ["1", "3-6", "2-5", "4", "2d4+1", "Nil", "Nil", "Nil", "4,000"],
        ["12", "96-105", "80-87", "-7", "24d4+12", "9", "45%", "Hx3", "20,000"]]}


def test_dragon_age_table_maps_columns_to_fields():
    m = Monster(armor_class="1 (base)", extra_tables=[_dragon_age_table()])
    ts = mt.tiers(m)
    assert [t.label for t in ts] == ["Age 1", "Age 12"]
    assert ts[0].overrides == {"armor_class": "4", "breath_weapon": "2d4+1",
                               "magic_resistance": "Nil", "treasure": "Nil", "xp_value": "4,000"}
    assert ts[1].overrides["armor_class"] == "-7" and ts[1].overrides["xp_value"] == "20,000"
    assert ts[1].overrides["breath_weapon"] == "24d4+12"     # breath scales with age (Phase B)


def test_mummy_style_age_table_scales_hd_and_thac0():
    table = {"kind": "age", "header_rows": 1, "rows": [
        ["Age", "To Hit", "AC", "HD", "THAC0"],
        ["99 or less", "+1", "2", "8+3", "11"],
        ["500 or more", "+4", "-3", "13+3", "7"]]}
    ts = mt.tiers(Monster(extra_tables=[table]))
    assert ts[0].label == "Age 99 (or less)"
    assert ts[0].overrides == {"armor_class": "2", "hit_dice": "8+3", "thac0": "11"}
    assert ts[1].overrides["thac0"] == "7"                 # "To Hit" column is skipped (no field)


def test_age_table_wins_over_conditional_when_both_present():
    m = Monster(thac0="5-6 HD: 15 7-8 HD: 13", extra_tables=[_dragon_age_table()])
    assert [t.label for t in mt.tiers(m)] == ["Age 1", "Age 12"]   # richer source


# ── applying a tier ───────────────────────────────────────────────────────────

def test_apply_tier_recomputes_house_rule_derivations():
    m = Monster(armor_class="1 (base)", thac0="9 (base)", extra_tables=[_dragon_age_table()])
    scaled = mt.apply_tier(m, mt.tiers(m)[1])              # Age 12: AC -7
    assert scaled.armor_class == "-7" and scaled.ascending_ac() == "27"
    assert m.armor_class == "1 (base)"                     # base monster is untouched


def test_active_index_and_monster_track_selected_tier():
    m = Monster(thac0="5-6 HD: 15 7-8 HD: 13 9-10 HD: 11")
    assert mt.active_index(m) is None                      # unset -> base
    assert mt.active_monster(m) is m
    m.selected_tier = 2
    assert mt.active_index(m) == 2
    assert mt.active_monster(m).thac0 == "11" and mt.active_monster(m).attack_bonus() == "9"


def test_out_of_range_selected_tier_falls_back_to_base():
    m = Monster(thac0="5-6 HD: 15 7-8 HD: 13", selected_tier=9)
    assert mt.active_index(m) is None                      # stale index -> base
    assert mt.active_monster(m) is m


def test_no_scaling_monster_has_no_tiers():
    assert mt.tiers(Monster(name="Ankheg", thac0="17-13", armor_class="2")) == []
    assert mt.active_monster(Monster(thac0="17-13")) is not None


def test_selected_tier_survives_a_dict_roundtrip():
    m = Monster(name="Dragon", selected_tier=3)
    assert Monster.from_dict(m.to_dict()).selected_tier == 3

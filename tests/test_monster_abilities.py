"""Tests for monster_abilities.py — ability/save chips read from a Monster's prose."""
import os

import pytest

import db
from monster import Monster
import monster_abilities as ma

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


# ── ability types ─────────────────────────────────────────────────────────────

def test_ability_types_tags_the_vocabulary():
    m = Monster(combat="Its gaze turns victims to stone; the bite injects poison.")
    assert ma.ability_types(m) == ["Gaze attack", "Poison", "Petrification"]  # vocab order


def test_ability_types_reads_the_terse_fields_too():
    # the mechanics can sit in the pointer fields, not just Combat
    m = Monster(special_attacks="Energy drain", special_defenses="Regeneration")
    assert "Level drain" in ma.ability_types(m) and "Regeneration" in ma.ability_types(m)


def test_ability_types_dedupes_and_orders():
    m = Monster(combat="Poison spray.", special_attacks="poison")     # mentioned twice
    assert ma.ability_types(m) == ["Poison"]


def test_ability_types_avoids_obvious_false_friends():
    assert ma.ability_types(Monster(combat="A fearsome, fearless brute.")) == []  # not "Fear"
    assert ma.ability_types(Monster(combat="Its deadly gaze petrifies.")) == ["Gaze attack", "Petrification"]
    assert ma.ability_types(Monster(combat="It gazes lazily at the horizon.")) == []  # verb, not an attack


def test_plain_brute_has_no_chips():
    assert ma.chips(Monster(combat="It hits things with a club.")) == []


# ── saving throws ─────────────────────────────────────────────────────────────

def test_saving_throws_canonicalizes_categories():
    m = Monster(combat="Victims must save vs. poison or die, and save vs. spells for half.")
    assert ma.saving_throws(m) == ["Save vs. Poison", "Save vs. Spells"]


def test_saving_throws_fold_ragged_phrasing_onto_categories():
    m = Monster(combat="A save vs. breath weapon reduces the damage; save vs. paralyzation negates.")
    assert ma.saving_throws(m) == ["Save vs. Paralyzation", "Save vs. Breath Weapon"]


def test_saving_throws_captures_a_signed_modifier():
    m = Monster(combat="Opponents make their saving throws at -2.")
    assert ma.saving_throws(m) == ["Save −2"]                 # rendered with a real minus sign


def test_chips_are_abilities_then_saves():
    m = Monster(combat="Its poison bite forces a save vs. poison.")
    assert ma.chips(m) == ["Poison", "Save vs. Poison"]


# ── structured per-ability detail ─────────────────────────────────────────────

def test_abilities_extract_save_damage_and_range():
    m = Monster(combat="Anyone within 30 feet must save vs. petrification or turn to "
                       "stone. Its bite injects poison (save vs. poison) for 2d6 damage.")
    abils = {a.name: a for a in ma.abilities(m)}
    assert abils["Petrification"].save == "Save vs. Petrification"
    assert abils["Petrification"].range == "30 feet"
    assert abils["Poison"].damage == "2d6"
    assert abils["Poison"].save == "Save vs. Poison"


def test_abilities_pull_mechanics_from_the_following_sentence():
    # the keyword sentence carries no numbers; the save/damage land in the next line
    m = Monster(combat="The dragon breathes a cone of frost. Victims save vs. breath "
                       "weapon or take 4d8 points of damage.")
    breath = next(a for a in ma.abilities(m) if a.name == "Breath weapon")
    assert breath.save == "Save vs. Breath Weapon" and breath.damage == "4d8"
    assert "cone of frost" in breath.text          # the naming sentence is kept too


def test_abilities_extract_frequency():
    m = Monster(combat="It can turn invisible at will.")
    inv = next(a for a in ma.abilities(m) if a.name == "Invisibility")
    assert inv.frequency == "at will"


def test_abilities_drop_rows_with_no_extractable_fact():
    # an immunity mention names the ability but yields no save/damage/range/frequency
    m = Monster(combat="These creatures are immune to charm and sleep. They fight without fear.")
    assert ma.abilities(m) == []                    # nothing promoted; chips still list them
    assert "Charm" in ma.ability_types(m)           # ...but the index keeps them


def test_ability_facts_order_damage_range_freq_then_save():
    m = Monster(combat="A 20-foot cone deals 3d6 damage, save vs. breath weapon for half, once per turn.")
    (a,) = ma.abilities(m)
    assert a.facts() == ["3d6", "20-foot cone", "once per turn", "Save vs. Breath Weapon"]


# ── against the real Monstrous Manual ─────────────────────────────────────────

@needs_db
def test_real_medusa_surfaces_gaze_and_petrification():
    conn = db.connect(RULES_DB)
    import monster_parser
    row = None
    for url, title in db.list_monster_pages(conn):
        r = db.get_page(conn, url)
        for mm in monster_parser.parse_stat_block(r["content_html"], r["title"], url):
            if mm.name == "Medusa":
                row = mm
    conn.close()
    assert row is not None
    types = ma.ability_types(row)
    assert "Gaze attack" in types and "Petrification" in types
    assert any("Petrification" in s for s in ma.saving_throws(row))

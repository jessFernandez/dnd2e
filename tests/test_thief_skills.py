"""Thieving skills (PHB Tables 26-29) and turning undead (Table 61).

The turning table is transcribed by hand, so the first test here checks the
structural property the book's table has -- every row is the row above shifted
one column right -- which is what a transcription typo breaks.
"""
import char_rules as cr
import roll20_export
from character import Character
from charactermancer import Charactermancer, THIEF_POINT_STEP


def _thief(dex=13, race="Human", char_class="Thief", level=1) -> Character:
    c = Character()
    c.abilities = {"Strength": 12, "Dexterity": dex, "Constitution": 12,
                   "Intelligence": 12, "Wisdom": 12, "Charisma": 12, "Perception": 12}
    c.race, c.char_class, c.level = race, char_class, level
    return c


# ── Table 61 ─────────────────────────────────────────────────────────────────

def test_turning_table_is_a_diagonal():
    rows = [cr._TURN_UNDEAD[k] for k in cr.TURN_UNDEAD_TYPES]
    for r in range(1, len(rows)):
        for col in range(1, len(rows[r])):
            assert rows[r][col] == rows[r - 1][col - 1], (
                f"{cr.TURN_UNDEAD_TYPES[r]} column {col + 1} breaks the diagonal")


def test_only_clerics_and_paladins_turn_undead():
    assert cr.turn_undead_level("Cleric", 1) == 1
    assert cr.turn_undead_level("Druid", 9) is None
    assert cr.turn_undead_level("Fighter", 9) is None
    assert cr.turn_undead("Thief", 5) is None


def test_paladins_turn_as_priests_two_levels_lower():
    assert cr.turn_undead_level("Paladin", 1) is None
    assert cr.turn_undead_level("Paladin", 2) is None      # would be level 0
    assert cr.turn_undead_level("Paladin", 3) == 1
    assert cr.turn_undead("Paladin", 3) == cr.turn_undead("Cleric", 1)


def test_turning_results_read_off_the_right_column():
    cleric1 = cr.turn_undead("Cleric", 1)
    assert cleric1["Skeleton or 1 HD"] == 10
    assert cleric1["Ghast"] is None                        # cannot touch it yet
    # The high columns collapse: 10-11, 12-13, 14+.
    assert cr.turn_undead("Cleric", 10) == cr.turn_undead("Cleric", 11)
    assert cr.turn_undead("Cleric", 12) == cr.turn_undead("Cleric", 13)
    assert cr.turn_undead("Cleric", 14) == cr.turn_undead("Cleric", 30)
    assert cr.turn_undead("Cleric", 6)["Skeleton or 1 HD"] == "D"
    assert cr.turn_undead("Cleric", 8)["Skeleton or 1 HD"] == "D*"
    assert cr.turn_undead("Cleric", 14)["Special"] == 13


# ── Tables 26-29 ─────────────────────────────────────────────────────────────

def test_only_thieves_and_bards_have_thieving_skills():
    assert cr.thief_skills_for_class("Thief") == cr.THIEF_SKILLS
    assert len(cr.thief_skills_for_class("Bard")) == 4
    assert cr.thief_skills_for_class("Fighter") == ()
    assert cr.thief_skill_class("Ranger") is None
    assert not _thief(char_class="Ranger").has_thief_skills()


def test_base_scores_differ_between_thief_and_bard():
    assert cr.thief_skill_base("Thief", "Climb Walls") == 60
    assert cr.thief_skill_base("Bard", "Climb Walls") == 50


def test_racial_and_dexterity_adjustments():
    assert cr.thief_racial_adjustment("Halfling", "Hide in Shadows") == 15
    assert cr.thief_racial_adjustment("Gnome", "Climb Walls") == -15
    assert cr.thief_racial_adjustment("Human", "Pick Pockets") == 0
    # Table 28 only touches five skills, and clamps at both ends.
    assert cr.thief_dex_adjustment(19, "Open Locks") == 20
    assert cr.thief_dex_adjustment(25, "Open Locks") == 20
    assert cr.thief_dex_adjustment(3, "Move Silently") == -20
    assert cr.thief_dex_adjustment(19, "Climb Walls") == 0
    assert cr.thief_dex_adjustment(14, "Pick Pockets") == 0


def test_leather_is_the_baseline_the_base_scores_assume():
    for skill in cr.THIEF_SKILLS:
        assert cr.thief_armor_adjustment("leather", skill) == 0
    assert cr.thief_armor_adjustment("none", "Move Silently") == 10
    assert cr.thief_armor_adjustment("chain_ring", "Climb Walls") == -25


def test_armor_kind_takes_the_worst_piece_worn():
    assert cr.thief_armor_kind([]) == "none"
    assert cr.thief_armor_kind(["Leather, Body"]) == "leather"
    assert cr.thief_armor_kind(["Gambeson, Body"]) == "padded_studded"
    assert cr.thief_armor_kind(["Leather, Limbs", "Chain, Body"]) == "chain_ring"
    # Helms are not body armor, and neither are non-armor items.
    assert cr.thief_armor_kind(["Helm, Full", "Torch"]) == "none"


def test_a_skill_score_sums_every_adjustment():
    c = _thief(dex=17, race="Halfling")
    c.thief_skills["Hide in Shadows"] = 10
    # base 5 + halfling 15 + Dex 18 (+10, the halfling's +1 applies) + no armor (+5)
    # + 10 spent. The score reads off the *final* abilities, racial bonus included.
    assert c.thief_skill_score("Hide in Shadows") == 45
    c.worn = ["Leather, Body"]
    assert c.thief_skill_score("Hide in Shadows") == 40   # loses the no-armor +5


def test_scores_are_capped_at_95_percent():
    c = _thief(dex=19, race="Halfling", level=8)
    c.thief_skills["Climb Walls"] = cr.thief_max_points_in_skill("Thief", 8)
    assert c.thief_skill_score("Climb Walls") == cr.THIEF_SKILL_MAX


def test_a_non_thief_scores_nothing():
    assert _thief(char_class="Fighter").thief_skill_score("Climb Walls") is None
    assert _thief(char_class="Fighter").thief_skill_scores() == {}


def test_discretionary_points_grow_with_level():
    assert cr.thief_discretionary_points("Thief", 1) == 60
    assert cr.thief_discretionary_points("Thief", 4) == 150
    assert cr.thief_discretionary_points("Bard", 1) == 20
    assert cr.thief_discretionary_points("Bard", 3) == 50
    assert cr.thief_discretionary_points("Fighter", 5) == 0
    assert cr.thief_max_points_in_skill("Thief", 1) == 30
    assert cr.thief_max_points_in_skill("Thief", 3) == 60
    assert cr.thief_max_points_in_skill("Fighter", 3) == 0


# ── spending the points ──────────────────────────────────────────────────────

def _mancer(char_class="Thief", **kw) -> Charactermancer:
    cm = Charactermancer(character=_thief(char_class=char_class, **kw))
    return cm


def test_points_spend_and_refund_in_blocks():
    cm = _mancer()
    c = cm.character
    assert cm.dispatch("thiefup/Open Locks")
    assert c.thief_points_in("Open Locks") == THIEF_POINT_STEP
    assert c.thief_points_left() == 60 - THIEF_POINT_STEP
    assert cm.dispatch("thiefdown/Open Locks")
    assert "Open Locks" not in c.thief_skills          # emptied, not left at zero
    assert c.thief_points_left() == 60


def test_cannot_overspend_the_budget_or_the_per_skill_cap():
    cm = _mancer()
    c = cm.character
    for _ in range(6):                                 # 30 points: the 1st-level cap
        cm.add_thief_points("Read Languages")
    assert c.thief_points_in("Read Languages") == 30
    assert not c.can_add_thief_point("Read Languages")
    cm.add_thief_points("Read Languages")
    assert c.thief_points_in("Read Languages") == 30    # refused, silently

    for _ in range(6):                                 # spend the other 30
        cm.add_thief_points("Open Locks")
    assert c.thief_points_left() == 0
    assert not c.can_add_thief_point("Pick Pockets")


def test_points_cannot_be_poured_into_a_skill_already_at_the_ceiling():
    # A human thief's Climb Walls starts at 60 + 10 (no armor); 25 points reach 95.
    cm = _mancer()
    c = cm.character
    for _ in range(5):
        cm.add_thief_points("Climb Walls")
    assert c.thief_skill_score("Climb Walls") == cr.THIEF_SKILL_MAX
    # The per-skill cap is 30 and 25 are spent, but a sixth block would buy nothing.
    assert not c.can_add_thief_point("Climb Walls")
    cm.add_thief_points("Climb Walls")
    assert c.thief_points_in("Climb Walls") == 25
    assert c.thief_points_left() == 35                 # kept for a skill that gains


def test_a_bard_may_only_spend_on_a_bards_skills():
    c = _thief(char_class="Bard")
    assert not c.can_add_thief_point("Open Locks")      # not a bard skill
    assert c.can_add_thief_point("Climb Walls")


def test_lowering_the_level_reclaims_points_that_no_longer_exist():
    cm = _mancer(level=4)
    c = cm.character
    cm.set_level(4)
    for _ in range(12):                                 # 60 points into one skill
        cm.add_thief_points("Move Silently")
    assert c.thief_points_in("Move Silently") == 60
    cm.set_level(1)
    # 1st level allows 60 points overall and only 30 in one skill.
    assert c.thief_points_in("Move Silently") == 30
    assert c.thief_points_left() == 30


def test_a_race_with_a_lower_level_cap_reclaims_the_points_it_takes_away():
    cm = _mancer(race="Human", level=20)          # humans have no thief level cap
    c = cm.character
    cm.set_level(20)
    for skill in c.thief_skill_names():
        while c.can_add_thief_point(skill):
            cm.add_thief_points(skill)
    spent_at_20 = c.thief_points_used()
    assert spent_at_20 > cr.thief_discretionary_points("Thief", 12)

    cm.set_race("Dwarf")                          # dwarven thieves stop at 12th
    assert c.level == 12
    cap = cr.thief_max_points_in_skill("Thief", 12)
    assert c.thief_points_used() < spent_at_20    # the reclaim actually gave points back
    assert c.thief_points_left() >= 0
    assert all(spent <= cap for spent in c.thief_skills.values())


def test_changing_class_away_from_thief_drops_the_points():
    cm = _mancer()
    cm.add_thief_points("Hide in Shadows")
    cm.set_class("Fighter")
    assert cm.character.thief_skills == {}


def test_thief_skills_round_trip_through_save_and_load():
    c = _thief(dex=17)
    c.thief_skills["Detect Noise"] = 15
    back = Character.from_dict(c.to_dict())
    assert back.thief_skills == {"Detect Noise": 15}
    # A save written before thieving skills existed loads with none.
    data = c.to_dict()
    del data["thief_skills"]
    assert Character.from_dict(data).thief_skills == {}


# ── the sheet's four columns ─────────────────────────────────────────────────

def test_export_splits_a_skill_into_the_sheets_four_columns():
    c = _thief(dex=17, race="Halfling")
    c.thief_skills["Hide in Shadows"] = 10
    rows = {r["name"]: r for r in roll20_export._thief_skills(c)}
    hs = rows["Hide in Shadows"]
    assert hs["key"] == "HS"
    assert (hs["base"], hs["adj"], hs["armor"], hs["points"]) == (5, 25, 5, 10)
    # The columns sum to what the builder shows -- that's what the sheet displays.
    assert sum((hs["base"], hs["adj"], hs["armor"], hs["points"])) == \
        c.thief_skill_score("Hide in Shadows")


def test_export_is_empty_for_classes_without_thieving_skills():
    assert roll20_export._thief_skills(_thief(char_class="Cleric")) == []


def test_every_thief_skill_has_a_sheet_column():
    assert set(roll20_export._THIEF_SHEET_KEYS) == set(cr.THIEF_SKILLS)

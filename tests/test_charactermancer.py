"""Tests for charactermancer.py — the step-flow controller."""
import random

import pytest

from charactermancer import Charactermancer, STEPS, STEP_TITLES
from character import Character
import char_rules as cr

FULL = {"Strength": 13, "Dexterity": 13, "Constitution": 14,
        "Intelligence": 11, "Wisdom": 14, "Charisma": 10, "Perception": 12}


def _at_abilities_done() -> Charactermancer:
    cm = Charactermancer(rng=random.Random(1))
    for a, s in FULL.items():
        cm.set_ability(a, s)
    return cm


# ── step gating ──────────────────────────────────────────────────────────────

def test_starts_on_abilities_and_cannot_advance_empty():
    cm = Charactermancer()
    assert cm.step == "abilities" and cm.index == 0
    assert not cm.can_advance() and not cm.can_go_back()


def test_advance_gated_until_abilities_valid():
    cm = Charactermancer()
    cm.set_ability("Strength", 12)
    assert not cm.can_advance()                        # only one score set
    cm2 = _at_abilities_done()
    assert cm2.can_advance()
    assert cm2.advance() and cm2.step == "race"
    assert cm2.can_go_back() and cm2.back() and cm2.step == "abilities"


def test_full_happy_path_through_the_flow():
    cm = _at_abilities_done()
    assert cm.advance() and cm.step == "race"
    cm.set_race("Human")
    assert cm.is_complete("race") and cm.advance() and cm.step == "class"
    cm.set_class("Ranger")                             # qualifies with these stats
    assert cm.is_complete("class") and cm.advance() and cm.step == "alignment"
    cm.set_alignment("Neutral Good")                   # allowed for ranger
    assert cm.is_complete("alignment") and cm.advance() and cm.step == "proficiencies"
    assert cm.advance() and cm.step == "equipment"     # proficiencies optional in v1
    assert cm.advance() and cm.step == "spells"        # equipment optional
    assert cm.advance() and cm.step == "details"       # spells optional
    assert not cm.is_complete("details")               # name required
    cm.set_name("Fenwick")
    assert cm.advance() and cm.step == "review"
    assert not cm.can_advance()                        # terminal


def test_cannot_advance_past_last_step():
    cm = _at_abilities_done()
    cm.index = len(STEPS) - 1
    assert not cm.can_advance() and not cm.advance()


# ── downstream invalidation ──────────────────────────────────────────────────

def test_changing_abilities_clears_now_illegal_race():
    cm = _at_abilities_done()
    cm.set_race("Elf")                                 # needs Int ≥ 8; ok at Int 11
    assert cm.character.race == "Elf"
    cm.set_ability("Intelligence", 5)                  # Elf now illegal
    assert cm.character.race is None


def test_changing_race_clears_illegal_class():
    cm = _at_abilities_done()
    cm.set_ability("Intelligence", 12)
    cm.set_race("Elf"); cm.set_class("Mage")
    assert cm.character.char_class == "Mage"
    cm.set_race("Dwarf")                               # dwarves can't be mages
    assert cm.character.char_class is None


def test_works_without_an_injected_rng():
    # Every roll goes through Charactermancer._roll, which falls back to the
    # `random` module. Tests always inject an rng, so this path was uncovered.
    cm = Charactermancer()
    for a in cm.character.ability_names():
        cm.set_ability(a, 18)
    cm.set_race("Human"); cm.set_class("Fighter")
    cm.roll_exceptional_strength()
    cm.roll_handedness()
    cm.roll_money()
    cm.dispatch("level/5")
    cm.dispatch("rerollhp")
    c = cm.character
    assert 1 <= c.exceptional_str <= 100
    assert 1 <= c.handedness_roll <= 10
    assert c.money_cp > 0
    assert c.level == 5 and len(c.hp_rolls) == 4


def test_dispatch_level_and_rerollhp():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Fighter")
    assert cm.dispatch("level/7")
    assert cm.character.level == 7 and len(cm.character.hp_rolls) == 6
    before = list(cm.character.hp_rolls)
    assert cm.dispatch("rerollhp")
    assert cm.character.hp_rolls != before and len(cm.character.hp_rolls) == 6
    assert not cm.dispatch("level/0")            # below 1 is refused
    assert not cm.dispatch("level/abc")          # non-numeric is refused
    assert cm.character.level == 7


def test_dispatch_level_clamps_to_racial_cap():
    cm = _at_abilities_done()
    cm.set_race("Dwarf"); cm.set_class("Fighter")
    cm.dispatch("level/20")
    assert cm.character.level == 15               # dwarf fighter cap


def test_html_class_step_has_level_control():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Fighter")
    cm.index = STEPS.index("class")
    html = cmh.generate(cm)
    assert 'href="dnd:///cm/level/2"' in html      # step up
    assert "At 1st level" in html                  # side-rail header is level-aware
    cm.dispatch("level/7")
    html = cmh.generate(cm)
    assert "At 7th level" in html
    assert "dnd:///cm/rerollhp" in html            # rolled hit dice can be rerolled


def test_html_level_control_disables_plus_at_racial_cap():
    cm = _at_abilities_done()
    cm.set_race("Dwarf"); cm.set_class("Fighter")
    cm.dispatch("level/15")
    cm.index = STEPS.index("class")                  # where the level field lives
    html = cmh.generate(cm)
    assert 'href="dnd:///cm/level/16"' not in html   # cannot exceed the cap
    assert "racial level limit" in html


def test_html_review_shows_level_and_advance_control():
    cm = _complete()
    cm.dispatch("level/9")
    cm.index = STEPS.index("review")
    html = cmh.generate(cm)
    assert "Combat (9th level)" in html
    assert "Attacks/round" in html and "3/2" in html   # warrior 3/2 from 7th
    assert "dnd:///cm/level/" in html                  # level up from the sheet


def test_html_spells_step_shows_a_section_per_castable_level():
    cm = _cleric_at_profs()                       # Wis 14
    cm.dispatch("level/5")                        # Table 24 row 5 = 3/3/1, +2 Wis bonus at 1st
    cm.index = STEPS.index("spells")
    cm.spell_catalog = [{"name": "Bless", "school": "Combat", "level": 1},
                        {"name": "Silence", "school": "Guardian", "level": 2}]
    html = cmh.generate(cm)
    assert "up to 3rd-level spells" in html
    for label in ("1st level", "2nd level", "3rd level"):
        assert label in html
    assert "dnd:///cm/addspell/Silence" in html    # 2nd-level spells are now offered
    # per-spell-level budgets: 5 first-level (3 base + 2 Wisdom bonus), 3 second, 1 third
    assert "0 of 5 memorized" in html
    assert "0 of 3 memorized" in html
    assert "0 of 1 memorized" in html


def test_html_spells_step_placeholder_for_late_casters():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Ranger")   # rangers cast nothing before 8th
    cm.index = STEPS.index("spells")
    html = cmh.generate(cm)
    assert "No spells at 1st level" in html
    assert "gains no spells until a higher level" in html


def test_spell_added_at_its_own_level_and_budgeted_separately():
    cm = _cleric_at_profs()
    cm.dispatch("level/5")
    cm.spell_catalog = [{"name": "Bless", "school": "C", "level": 1},
                        {"name": "Silence", "school": "G", "level": 2},
                        {"name": "Prayer", "school": "C", "level": 3},
                        {"name": "Chant", "school": "C", "level": 3}]
    cm.dispatch("addspell/Bless")
    cm.dispatch("addspell/Silence")
    cm.dispatch("addspell/Prayer")
    assert cm.character.spells == {"Bless": 1, "Silence": 2, "Prayer": 3}
    # only one 3rd-level slot at 5th level, so the second 3rd-level pick is refused
    cm.dispatch("addspell/Chant")
    assert "Chant" not in cm.character.spells
    # ...but the 1st-level budget (5) is untouched by that
    assert cm.character.can_add_spell(1) and not cm.character.can_add_spell(3)


def test_ordinal_suffixes():
    assert [cmh._ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]


def test_changing_race_reclamps_level_to_the_new_racial_cap():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Fighter")
    cm.character.set_level(18, rng=random.Random(1))
    assert cm.character.level == 18                     # humans are uncapped
    cm.set_race("Dwarf")                               # dwarf fighters cap at 15
    assert cm.character.level == 15
    assert len(cm.character.hp_rolls) == cr.hp_die_levels("Fighter", 15)


def test_changing_class_resyncs_the_hit_dice_count():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Fighter")
    cm.character.set_level(10, rng=random.Random(2))
    assert len(cm.character.hp_rolls) == 8              # warrior name level is 9
    cm.set_class("Mage")                               # wizard name level is 10
    assert cm.character.char_class == "Mage"
    assert len(cm.character.hp_rolls) == 9              # a 9th die is rolled
    assert cm.character.max_hp() is not None            # and HP still computes


def test_changing_class_clears_illegal_alignment():
    cm = _at_abilities_done()                          # FULL stats qualify for Ranger
    cm.set_class("Fighter"); cm.set_alignment("Chaotic Evil")
    assert cm.character.alignment == "Chaotic Evil"
    cm.set_class("Ranger")                             # good alignments only
    assert cm.character.char_class == "Ranger"
    assert cm.character.alignment is None


# ── goto (progress rail) ─────────────────────────────────────────────────────

def test_goto_requires_prior_steps_complete():
    cm = _at_abilities_done()
    assert cm.goto("race")                             # abilities done -> allowed
    assert not cm.goto("class")                        # race not chosen yet
    assert cm.step == "race"
    cm.set_race("Human")
    assert cm.goto("class") and cm.step == "class"


def test_goto_rejects_unknown_step():
    assert not Charactermancer().goto("nonsense")


# ── dispatch (link actions) ──────────────────────────────────────────────────

def test_dispatch_roll_and_mode():
    cm = Charactermancer(rng=random.Random(42))
    assert cm.dispatch("roll")
    assert len(cm.character.rolled_pool) == 7          # six abilities + Perception
    assert cm.dispatch("mode/manual") and cm.ability_mode == "manual"


def test_dispatch_assign_and_navigation():
    cm = Charactermancer()
    for a, s in FULL.items():
        assert cm.dispatch(f"assign/{a}/{s}")
    assert cm.character.abilities_valid()
    assert cm.dispatch("next") and cm.step == "race"
    assert cm.dispatch("race/Human") and cm.character.race == "Human"
    assert cm.dispatch("back") and cm.step == "abilities"


def test_dispatch_alignment_with_space():
    cm = _at_abilities_done()
    cm.dispatch("class/Fighter")
    assert cm.dispatch("align/Lawful Good")
    assert cm.character.alignment == "Lawful Good"


def test_dispatch_rejects_garbage():
    cm = Charactermancer()
    assert not cm.dispatch("")
    assert not cm.dispatch("assign/Strength/notanumber")
    assert not cm.dispatch("bogusverb/x")
    # a well-formed assign to an unknown ability is handled (True) but sets nothing
    assert cm.dispatch("assign/Luck/12")
    assert "Luck" not in cm.character.abilities


def test_dispatch_next_blocked_when_incomplete_returns_false():
    cm = Charactermancer()
    assert not cm.dispatch("next")                     # abilities not done
    assert cm.step == "abilities"


def test_roll_auto_arranges_a_valid_full_set():
    cm = Charactermancer(rng=random.Random(3))
    cm.dispatch("roll")
    assert cm.character.abilities_valid()               # all six assigned, in range
    # highest rolled value lands on Strength (arranged high→low)
    assert cm.character.abilities["Strength"] == max(cm.character.rolled_pool)


# ── HTML rendering (charactermancer_html) ────────────────────────────────────

import charactermancer_html as cmh


def test_html_renders_abilities_step():
    cm = Charactermancer()
    html = cmh.generate(cm)
    assert "<!DOCTYPE html>" in html and "Create a Character" in html
    assert "Ability Scores" in html
    assert "dnd:///cm/roll" in html                    # the roll action is present
    assert "Next ›" in html
    # Next is gated closed until scores are set
    assert 'class="nav-btn primary off"' in html


def test_html_shows_eligibility_after_full_scores():
    cm = _at_abilities_done()
    html = cmh.generate(cm)
    assert "Eligibility" in html
    assert "Fighter" in html and "Human" in html       # class + race chips
    assert 'href="dnd:///cm/next"' in html             # Next now enabled (a real link)


def test_html_every_step_renders():
    cm = _at_abilities_done()
    for step in STEPS:
        cm.index = STEPS.index(step)
        html = cmh.generate(cm)
        assert "</html>" in html and STEP_TITLES[step] in html


def test_html_roll_mode_shows_dice():
    cm = Charactermancer(rng=random.Random(9))
    cm.dispatch("roll")
    html = cmh.generate(cm)
    assert 'class="die"' in html                        # rolled values shown as dice


# ── Race step rendering ──────────────────────────────────────────────────────

def test_html_race_step_lists_races_with_adjustments():
    cm = _at_abilities_done()
    cm.index = STEPS.index("race")
    html = cmh.generate(cm)
    for r in ("Human", "Dwarf", "Elf", "Gnome", "Half-Elf", "Halfling"):
        assert r in html
    assert "+1 Dex" in html and "-1 Con" in html         # elf adjustments shown
    assert 'href="dnd:///cm/race/Human"' in html         # eligible race is clickable


def test_html_race_step_disables_and_explains_ineligible():
    cm = _at_abilities_done()
    cm.set_ability("Constitution", 9)                    # below Dwarf's Con 11 minimum
    cm.index = STEPS.index("race")
    html = cmh.generate(cm)
    assert 'href="dnd:///cm/race/Dwarf"' not in html     # Dwarf not selectable
    assert "pick-card sel" not in html or cm.character.race is None
    assert "Requires" in html and "Con" in html          # the failing requirement is shown


def test_html_race_shows_selection_and_summary():
    cm = _at_abilities_done()
    cm.set_race("Elf")
    cm.index = STEPS.index("race")
    html = cmh.generate(cm)
    assert "pick-card sel" in html                        # a card is marked selected
    assert "Your Character" in html                       # summary panel present


# ── Class step rendering ─────────────────────────────────────────────────────

def test_html_class_step_lists_classes_and_derived_preview():
    cm = _at_abilities_done()
    cm.set_race("Human")
    cm.index = STEPS.index("class")
    html = cmh.generate(cm)
    assert "Fighter" in html and "Ranger" in html
    assert 'href="dnd:///cm/class/Fighter"' in html
    assert "Hit die d" in html                            # per-class HD shown


def test_html_class_step_explains_unavailable_by_race():
    cm = _at_abilities_done()
    cm.set_ability("Intelligence", 12)                    # qualifies for Mage on stats
    cm.set_race("Dwarf")                                  # ...but dwarves can't be mages
    cm.index = STEPS.index("class")
    html = cmh.generate(cm)
    assert 'href="dnd:///cm/class/Mage"' not in html
    assert "cannot be Mages" in html


def test_html_class_summary_shows_combat_stats_once_chosen():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Fighter")
    cm.index = STEPS.index("class")
    html = cmh.generate(cm)
    assert "Attack bonus" in html and "THAC0" in html
    assert "Saving throws" in html
    assert "Max HP" in html


# ── app.py wiring (exercised without spinning up the QtWebEngine view) ───────
# _cm_action / _on_content_navigate only touch self._cm and a render call, so we
# bind the unbound MainWindow methods to a light stand-in (same pattern as the
# _ask_stop lifecycle test) and assert the routing + dispatch behaviour.

from types import SimpleNamespace

import app


def _win(**over):
    calls = []
    win = SimpleNamespace(_cm=None, _render_charactermancer=lambda: calls.append("render"),
                          _set_spell_catalog=lambda: None)
    win._render_calls = calls
    for k, v in over.items():
        setattr(win, k, v)
    return win


def test_cm_action_creates_dispatches_and_rerenders():
    win = _win()
    app.MainWindow._cm_action(win, "assign/Strength/15")
    assert isinstance(win._cm, Charactermancer)
    assert win._cm.character.abilities.get("Strength") == 15
    assert win._render_calls == ["render"]


def test_cm_action_unquotes_path():
    win = _win()
    # set up a class so the alignment sticks, then send an encoded space
    app.MainWindow._cm_action(win, "assign/Strength/13")
    for a, s in {"Dexterity": 13, "Constitution": 14, "Intelligence": 11,
                 "Wisdom": 14, "Charisma": 10}.items():
        app.MainWindow._cm_action(win, f"assign/{a}/{s}")
    app.MainWindow._cm_action(win, "class/Fighter")
    app.MainWindow._cm_action(win, "align/Lawful%20Good")
    assert win._cm.character.alignment == "Lawful Good"


def test_cm_action_restart_resets_build():
    win = _win()
    app.MainWindow._cm_action(win, "assign/Strength/15")
    app.MainWindow._cm_action(win, "restart")
    assert not win._cm.character.has_all_abilities()
    assert win._cm.character.abilities == {}


def test_on_content_navigate_routes_cm_prefix():
    routed = []
    win = SimpleNamespace(_cm_action=lambda p: routed.append(p))
    app.MainWindow._on_content_navigate(win, "cm/roll")
    assert routed == ["roll"]                            # cm/ stripped, sent to _cm_action


# ── Details-step controller actions ──────────────────────────────────────────

def test_set_gender_and_roll_handedness():
    cm = Charactermancer(rng=random.Random(2))
    assert cm.dispatch("gender/Female") and cm.character.gender == "Female"
    assert cm.dispatch("handedness")
    assert cm.character.handedness_roll in range(1, 11)


def test_ranger_is_auto_ambidextrous():
    cm = _at_abilities_done()
    cm.set_race("Human"); cm.set_class("Ranger")
    cm.roll_handedness()
    assert cm.character.ambidextrous is True             # ranger, regardless of the die


# ── Alignment / Details / Review rendering ───────────────────────────────────

def _complete(name="Gornak", race="Human", klass="Fighter", align="Lawful Good"):
    cm = _at_abilities_done()
    cm.set_race(race); cm.set_class(klass); cm.set_alignment(align); cm.set_name(name)
    return cm


def test_html_alignment_unrestricted_lists_all_nine():
    cm = _complete()
    cm.index = STEPS.index("alignment")
    html = cmh.generate(cm)
    for al in ("Lawful Good", "True Neutral", "Chaotic Evil"):
        assert f'dnd:///cm/align/{al}' in html          # all nine are selectable


def test_html_alignment_restricted_for_ranger():
    cm = _complete(klass="Ranger", align="Neutral Good")
    cm.index = STEPS.index("alignment")
    html = cmh.generate(cm)
    assert "dnd:///cm/align/Neutral Good" in html        # good allowed
    assert "dnd:///cm/align/Chaotic Evil" not in html    # evil not selectable
    assert "restricted to" in html


def test_html_details_form_fields():
    cm = _complete()
    cm.index = STEPS.index("details")
    html = cmh.generate(cm)
    assert "cmText('name'" in html and "cmText('gender'" in html
    # Handedness moved to the Proficiencies step (it gates ambidexterity).
    assert "dnd:///cm/handedness" not in html


def test_html_review_renders_sheet_and_save():
    cm = _complete()
    cm.index = STEPS.index("review")
    html = cmh.generate(cm)
    assert "Gornak" in html                              # the sheet name
    assert "Human Fighter" in html and "Lawful Good" in html
    assert "Attack bonus" in html and "Saving throws" in html
    assert "dnd:///cm/save" in html and "dnd:///cm/restart" in html


def test_html_saved_list_on_review_and_abilities():
    saved = [(1, "Mira", "Elf", "Mage", "True Neutral")]
    cm = _complete()
    cm.index = STEPS.index("review")
    html = cmh.generate(cm, saved)
    assert "Mira" in html and "dnd:///cm/load/1" in html and "dnd:///cm/delete/1" in html
    cm.index = 0                                         # the load panel also appears at the start
    assert "dnd:///cm/load/1" in cmh.generate(cm, saved)


def test_html_review_survives_incomplete_character():
    cm = _at_abilities_done()                            # no class chosen
    cm.index = STEPS.index("review")
    html = cmh.generate(cm)                              # must not raise
    assert "</html>" in html


# ── save / load / delete wiring (temp in-memory user DB) ─────────────────────

import db
from character_library import CharacterLibrary


def _win_with_db(cm, user_db=None):
    """A stand-in with the real MainWindow save/load/delete helpers bound to it,
    so _cm_action exercises the actual DB wiring (via CharacterLibrary) without a
    live window."""
    user_db = user_db or db.connect(":memory:")
    win = SimpleNamespace(_cm=cm, user_db=user_db,
                          _char_library=CharacterLibrary(user_db),
                          _render_charactermancer=lambda: None,
                          _set_spell_catalog=lambda: None)
    win._cm_save = lambda: app.MainWindow._cm_save(win)
    win._cm_load = lambda cid: app.MainWindow._cm_load(win, cid)
    win._cm_delete = lambda cid: app.MainWindow._cm_delete(win, cid)
    return win


def test_app_save_load_delete_roundtrip():
    cm = _complete()
    win = _win_with_db(cm)
    app.MainWindow._cm_action(win, "save")
    assert win._cm.saved_id is not None
    rows = db.all_characters(win.user_db)
    assert len(rows) == 1 and rows[0]["name"] == "Gornak"

    # load into a fresh builder sharing the same DB
    win2 = _win_with_db(Charactermancer(), user_db=win.user_db)
    app.MainWindow._cm_action(win2, f"load/{win._cm.saved_id}")
    assert win2._cm.character.name == "Gornak"
    assert win2._cm.character.char_class == "Fighter"
    assert win2._cm.step == "review"                    # opens on the finished sheet
    assert win2._cm.saved_id == win._cm.saved_id

    # re-saving an already-saved build updates in place (still one row)
    app.MainWindow._cm_action(win2, "save")
    assert len(db.all_characters(win.user_db)) == 1

    # delete
    app.MainWindow._cm_action(win2, f"delete/{win2._cm.saved_id}")
    assert db.all_characters(win.user_db) == []
    assert win2._cm.saved_id is None


def test_app_load_ignores_bad_id():
    win = _win_with_db(Charactermancer())
    db.ensure_characters_schema(win.user_db)
    app.MainWindow._cm_action(win, "load/999")           # no such row -> no crash
    app.MainWindow._cm_action(win, "load/notanint")      # non-int -> no crash
    assert win._cm.character.name == ""


# ── house-rule Perception + aging in the builder ─────────────────────────────

def test_abilities_step_includes_perception_with_its_effects():
    cm = Charactermancer()                               # empty; house rules on
    html = cmh.generate(cm)
    assert "Perception" in html                          # a 7th ability row
    assert "assign/Perception/" in html                  # it has its own selector
    cm2 = _at_abilities_done()
    assert "surprise" in cmh.generate(cm2)               # its derived effect is shown


def test_perception_shown_on_review_sheet():
    cm = _complete()
    cm.index = STEPS.index("review")
    assert ">Per<" in cmh.generate(cm)                   # Perception in the sheet's ability grid


def test_perception_not_offered_without_house_rules():
    cm = Charactermancer(character=Character(house_rules=False))
    assert "assign/Perception/" not in cmh.generate(cm)


def _warrior_18str():
    """A build that qualifies for Fighter with an 18 Strength (rolls exceptional)."""
    cm = Charactermancer(rng=random.Random(1))
    for a, s in {"Strength": 18, "Dexterity": 13, "Constitution": 14,
                 "Intelligence": 11, "Wisdom": 12, "Charisma": 10, "Perception": 12}.items():
        cm.set_ability(a, s)
    return cm


def test_exceptional_strength_gates_class_step_until_rolled():
    cm = _warrior_18str()
    cm.index = STEPS.index("class")
    cm.set_class("Fighter")
    assert cm.character.rolls_exceptional_strength() is True
    assert cm.character.exceptional_str is None
    assert not cm.can_advance()                          # blocked until the d100 is rolled
    assert cm.dispatch("exstr")
    assert 1 <= cm.character.exceptional_str <= 100
    assert cm.can_advance()                              # now allowed


def test_exceptional_strength_not_required_for_non_warrior():
    cm = _warrior_18str()
    cm.set_ability("Intelligence", 12)
    cm.index = STEPS.index("class")
    cm.set_class("Mage")                                 # wizard, no exceptional Strength
    assert cm.character.rolls_exceptional_strength() is False
    assert cm.can_advance()


def test_exceptional_strength_cleared_when_no_longer_a_warrior():
    cm = _warrior_18str()
    cm.set_ability("Intelligence", 12)
    cm.set_class("Fighter"); cm.roll_exceptional_strength()
    assert cm.character.exceptional_str is not None
    cm.set_class("Mage")                                 # switch off the warrior group
    assert cm.character.exceptional_str is None          # stale percentile dropped


def test_html_class_step_prompts_and_shows_exceptional_strength():
    cm = _warrior_18str()
    cm.index = STEPS.index("class")
    cm.set_class("Fighter")
    html = cmh.generate(cm)
    assert "dnd:///cm/exstr" in html and "Exceptional Strength" in html
    cm.roll_exceptional_strength()
    html2 = cmh.generate(cm)
    assert "18/" in html2                                # the rolled band is displayed
    assert "re-roll" in html2


def test_html_abilities_notes_exceptional_strength_when_no_class():
    cm = _warrior_18str()                                # 18 Str, no class yet
    html = cmh.generate(cm)
    assert "warrior class" in html                       # informational heads-up


def test_details_step_has_aging_and_dispatch_applies_it():
    cm = _complete()
    cm.index = STEPS.index("details")
    html = cmh.generate(cm)
    assert "dnd:///cm/age/2" in html and "Venerable" in html
    assert cm.dispatch("age/2") and cm.character.age_level == 2
    html2 = cmh.generate(cm)
    assert "physical" in html2 and "mental" in html2     # the placement guidance appears


# ── Proficiencies step ───────────────────────────────────────────────────────

def _fighter_at_profs():
    cm = _complete()                                     # Human Fighter, FULL stats
    cm.index = STEPS.index("proficiencies")
    return cm


def test_weapon_proficiency_house_rule_costs():
    cm = _fighter_at_profs()
    c = cm.character
    assert c.weapon_slots_total() == 4
    cm.dispatch("addweapon/Light Crossbow")              # free (house rule)
    assert c.weapon_slots_used() == 0 and "Light Crossbow" in c.weapon_profs
    cm.dispatch("addweapon/Long Bow")                    # 2 slots (house rule)
    assert c.weapon_slots_used() == 2
    cm.dispatch("rmweapon/Long Bow")
    assert c.weapon_slots_used() == 0


def test_cannot_overspend_weapon_slots():
    cm = _fighter_at_profs()
    c = cm.character
    for w in ("Long Sword", "Short Sword", "Dagger", "Mace"):   # 4 x 1 slot = full
        cm.dispatch(f"addweapon/{w}")
    assert c.weapon_slots_left() == 0
    cm.dispatch("addweapon/Club")
    assert "Club" not in c.weapon_profs                  # over budget -> rejected


def test_nonweapon_extra_slot_is_plus_two():
    cm = _fighter_at_profs()
    c = cm.character
    cm.dispatch("addprof/Swimming")
    base = c.proficiency_skill("Swimming")
    cm.dispatch("profplus/Swimming")
    assert c.proficiency_skill("Swimming") == base + 2   # house rule
    cm.dispatch("profminus/Swimming")
    assert c.nonweapon_profs["Swimming"] == 1            # back to base cost
    cm.dispatch("rmprof/Swimming")
    assert "Swimming" not in c.nonweapon_profs


def test_proficiency_name_containing_slash_dispatches():
    cm = _fighter_at_profs()
    assert cm.dispatch("addprof/Bowyer/Fletcher")        # the '/' in the name survives
    assert "Bowyer/Fletcher" in cm.character.nonweapon_profs


def _cleric_at_profs() -> Charactermancer:
    cm = _at_abilities_done()
    cm.set_race("Human")
    cm.set_class("Cleric")
    cm.set_alignment("Lawful Good")
    cm.index = STEPS.index("proficiencies")
    return cm


def test_weapon_mastery_ladder_climb_and_descend():
    cm = _fighter_at_profs()
    cm.dispatch("addweapon/Long Sword")
    c = cm.character
    assert c.weapon_profs == {"Long Sword": "proficient"} and c.weapon_slots_used() == 1
    cm.dispatch("wpnup/Long Sword")
    assert c.weapon_profs["Long Sword"] == "specialist" and c.weapon_slots_used() == 2
    cm.dispatch("wpnup/Long Sword")                  # mastery needs 5th level
    assert c.weapon_profs["Long Sword"] == "specialist"
    cm.dispatch("wpndown/Long Sword")
    assert c.weapon_profs["Long Sword"] == "proficient" and c.weapon_slots_used() == 1
    cm.dispatch("wpndown/Long Sword")                # can't go below proficient
    assert c.weapon_profs["Long Sword"] == "proficient"


def test_mastery_unlocks_with_level():
    cm = _fighter_at_profs()
    cm.dispatch("level/9")                           # 6 weapon slots at 9th
    cm.dispatch("addweapon/Long Sword")
    for _ in range(4):
        cm.dispatch("wpnup/Long Sword")
    c = cm.character
    assert c.weapon_profs["Long Sword"] == "grand_master"
    assert c.weapon_slots_used() == 5                # 1 + 4 extra slots


def test_a_fighter_may_specialise_in_only_one_weapon():
    cm = _fighter_at_profs()
    cm.dispatch("addweapon/Long Sword")
    cm.dispatch("addweapon/Dagger")
    cm.dispatch("wpnup/Long Sword")
    assert cm.character.weapon_profs["Long Sword"] == "specialist"
    cm.dispatch("wpnup/Dagger")                      # refused: already specialised
    assert cm.character.weapon_profs["Dagger"] == "proficient"
    assert cm.character.specialised_weapon() == "Long Sword"


def test_nonfighters_cannot_climb_past_their_rung():
    cm = _cleric_at_profs()
    cm.dispatch("addweapon/Mace")
    cm.dispatch("wpnup/Mace")
    assert cm.character.weapon_profs["Mace"] == "proficient"   # priests stop here


def test_rung_climb_refused_when_slots_are_short():
    cm = _fighter_at_profs()
    for w in ("Long Sword", "Dagger", "Spear", "Club"):
        cm.dispatch("addweapon/" + w)                # 4 slots, all spent
    c = cm.character
    assert c.weapon_slots_left() == 0
    cm.dispatch("wpnup/Long Sword")                  # no slot for the extra rung
    assert c.weapon_profs["Long Sword"] == "proficient"


def test_familiarity_is_reported_for_untrained_weapons():
    cm = _fighter_at_profs()
    cm.dispatch("addweapon/Short Sword")             # Ancient/Middle Eastern/Short
    c = cm.character
    assert c.weapon_rung("Scimitar") == "familiar"   # shares Middle Eastern
    assert c.weapon_rung("Halberd") == "nonproficient"
    assert c.weapon_rung("Quarterstaff") == "nonproficient"   # group-less
    assert c.weapon_rung("Short Sword") == "proficient"


def test_weapon_group_grants_the_whole_tight_group_for_two_slots():
    cm = _fighter_at_profs()
    cm.dispatch("addgroup/Medium")                   # Broad Sword + Long Sword
    c = cm.character
    assert c.weapon_groups == ["Medium"]
    assert c.weapon_slots_used() == cr.WEAPON_GROUP_SLOT_COST == 2
    for w in cr.weapon_group_members("Medium"):
        assert c.weapon_rung(w) == "proficient"
    assert c.weapon_profs == {}                      # no per-weapon entries needed


def test_buying_a_group_refunds_the_proficiencies_it_now_grants():
    cm = _fighter_at_profs()
    cm.dispatch("addweapon/Long Sword")              # 1 slot
    assert cm.character.weapon_slots_used() == 1
    cm.dispatch("addgroup/Medium")                   # covers Long Sword
    c = cm.character
    assert c.weapon_profs == {}                      # the redundant entry is refunded
    assert c.weapon_slots_used() == 2                # just the group


def test_group_covered_weapon_can_still_be_specialised_for_the_extra_slot_only():
    cm = _fighter_at_profs()
    cm.dispatch("addgroup/Medium")
    c = cm.character
    cm.dispatch("wpnup/Long Sword")                  # proficiency already paid by the group
    assert c.weapon_profs == {"Long Sword": "specialist"}
    assert c.weapon_prof_cost("Long Sword") == 1     # only the extra rung slot
    assert c.weapon_slots_used() == 3                # 2 group + 1 extra
    cm.dispatch("wpndown/Long Sword")                # back to group-granted proficiency
    assert c.weapon_profs == {} and c.weapon_slots_used() == 2


def test_group_covered_weapon_is_not_bought_individually():
    cm = _fighter_at_profs()
    cm.dispatch("addgroup/Crossbows")
    cm.dispatch("addweapon/Light Crossbow")          # already granted -> no entry
    assert cm.character.weapon_profs == {}


def test_group_members_confer_familiarity():
    cm = _fighter_at_profs()
    cm.dispatch("addgroup/Middle Eastern")           # Short Sword + Scimitar
    c = cm.character
    # Short Sword is also Ancient and Short, so those groups' weapons are familiar
    assert c.weapon_rung("Broad Sword") == "familiar"     # shares Ancient
    assert c.weapon_rung("Dagger") == "familiar"          # shares Short
    assert c.weapon_rung("Halberd") == "nonproficient"


def test_removing_a_group_is_refused_when_it_would_overdraw():
    cm = _fighter_at_profs()
    c = cm.character
    cm.dispatch("addgroup/Medium")
    assert c.can_remove_weapon_group("Medium")
    cm.dispatch("rmgroup/Medium")
    assert c.weapon_groups == [] and c.weapon_slots_used() == 0


def test_weapon_groups_survive_a_save_load_round_trip():
    from character import Character
    cm = _fighter_at_profs()
    cm.dispatch("addgroup/Axes")
    back = Character.from_dict(cm.character.to_dict())
    assert back.weapon_groups == ["Axes"]
    assert back.weapon_rung("Battle Axe") == "proficient"


def test_legacy_weapon_prof_list_migrates_to_rungs():
    from character import Character
    c = _fighter_at_profs().character
    legacy = c.to_dict()
    legacy["weapon_profs"] = ["Long Sword", "Dagger"]   # the old flat list
    back = Character.from_dict(legacy)
    assert back.weapon_profs == {"Long Sword": "proficient", "Dagger": "proficient"}


def test_html_weapon_section_shows_rungs_and_steppers():
    cm = _fighter_at_profs()
    cm.dispatch("addweapon/Long Sword")
    html = cmh.generate(cm)
    assert "dnd:///cm/wpnup/Long Sword" in html
    assert "Proficient" in html and "Specialist" in html      # rung + ladder text
    cm.dispatch("wpnup/Long Sword")
    html = cmh.generate(cm)
    assert "dnd:///cm/wpndown/Long Sword" in html


def test_proficiency_class_availability_gating():
    cm = _fighter_at_profs()                             # Warrior
    cm.dispatch("addprof/Alchemy")                       # wizard-only -> rejected
    assert "Alchemy" not in cm.character.nonweapon_profs
    cm.dispatch("addprof/Hunting")                       # warrior-available -> accepted
    assert "Hunting" in cm.character.nonweapon_profs


def test_proficiency_prerequisite_gating_and_cascade():
    cm = _cleric_at_profs()
    c = cm.character
    cm.dispatch("addprof/Healing")                       # needs Anatomy -> blocked
    assert "Healing" not in c.nonweapon_profs
    cm.dispatch("addprof/Anatomy")
    cm.dispatch("addprof/Healing")                       # prereq met -> allowed
    assert {"Anatomy", "Healing"} <= set(c.nonweapon_profs)
    cm.dispatch("rmprof/Anatomy")                        # removing prereq cascades
    assert "Anatomy" not in c.nonweapon_profs and "Healing" not in c.nonweapon_profs


def test_changing_class_prunes_now_illegal_proficiencies():
    cm = _cleric_at_profs()
    c = cm.character
    cm.dispatch("addprof/Herbalism")                     # priest/wizard skill
    assert "Herbalism" in c.nonweapon_profs
    cm.set_class("Fighter")                              # warrior can't take it
    assert "Herbalism" not in c.nonweapon_profs


def test_ambidexterity_purchase_costs_one_slot():
    cm = _fighter_at_profs()
    c = cm.character
    assert cm.dispatch("ambi") and c.bought_ambidexterity is True
    assert c.weapon_slots_used() == 1
    cm.dispatch("ambi")
    assert c.bought_ambidexterity is False


def test_html_proficiencies_step_renders_with_house_rules():
    cm = _fighter_at_profs()
    html = cmh.generate(cm)
    assert "Weapon Proficiencies" in html and "Nonweapon Proficiencies" in html
    assert "crossbows are free" in html and "adds +2" in html
    assert "dnd:///cm/addweapon/Long Bow" in html
    assert "dnd:///cm/addprof/Swimming" in html
    # Handedness roll now lives here (it affects which proficiencies you take).
    assert "dnd:///cm/handedness" in html and "Roll d10" in html


def test_html_review_lists_chosen_proficiencies():
    cm = _complete()
    cm.character.weapon_profs = {"Long Sword": "specialist", "Dagger": "proficient"}
    cm.character.nonweapon_profs = {"Swimming": 1}
    cm.index = STEPS.index("review")
    html = cmh.generate(cm)
    assert "Long Sword (Specialist)" in html      # the rung is named on the sheet
    assert "Dagger" in html and "Dagger (" not in html   # plain proficiency isn't
    assert "Swimming" in html


# ── Equipment + Spells steps ─────────────────────────────────────────────────

def test_builder_has_equipment_and_spell_steps():
    assert "equipment" in STEPS and "spells" in STEPS
    assert STEP_TITLES["equipment"] == "Equipment" and STEP_TITLES["spells"] == "Spells"


def test_equipment_purchase_wear_sell_flow():
    cm = _fighter_at_profs()
    cm.index = STEPS.index("equipment")
    c = cm.character
    cm.dispatch("money")
    assert c.money_cp > 0
    armor = cr.items_in_category("Armor")[0]["name"]
    before = c.money_cp
    cm.dispatch("buy/" + armor)
    assert c.inventory.get(armor) == 1 and c.money_cp < before
    cm.dispatch("wear/" + armor)
    assert armor in c.worn
    cm.dispatch("sell/" + armor)                           # full refund undo
    assert armor not in c.inventory and armor not in c.worn and c.money_cp == before


def test_cannot_overspend_on_equipment():
    cm = _fighter_at_profs()
    c = cm.character
    c.money_cp = 1
    pricey = next(i["name"] for i in cr.ITEMS.values() if i["cost_cp"] > 1)
    cm.dispatch("buy/" + pricey)
    assert pricey not in c.inventory


def test_spell_pick_validated_against_catalog():
    cm = _cleric_at_profs()
    cm.index = STEPS.index("spells")
    cm.spell_catalog = [{"name": "Bless", "school": "Combat", "level": 1}]
    cm.dispatch("addspell/Bless")
    cm.dispatch("addspell/Fireball")                       # not in catalog -> rejected
    assert cm.character.spells == {"Bless": 1}
    cm.dispatch("rmspell/Bless")
    assert cm.character.spells == {}


def test_html_equipment_and_spells_steps_render():
    cm = _fighter_at_profs()
    cm.index = STEPS.index("equipment")
    cm.dispatch("money")
    h = cmh.generate(cm)
    assert "Equipment" in h and "Armor Class" in h and "dnd:///cm/buy/" in h
    cm2 = _cleric_at_profs()
    cm2.index = STEPS.index("spells")
    cm2.spell_catalog = [{"name": "Bless", "school": "Combat", "level": 1, "description": "x"}]
    assert "dnd:///cm/addspell/Bless" in cmh.generate(cm2)


def test_spell_pick_respects_level1_limit():
    cm = _cleric_at_profs()                                # Wis 14 -> 3 spells
    cm.index = STEPS.index("spells")
    names = ["Bless", "Cure Light Wounds", "Sanctuary", "Command"]
    cm.spell_catalog = [{"name": n, "school": "Combat", "level": 1} for n in names]
    for n in names:
        cm.dispatch("addspell/" + n)
    assert set(cm.character.spells) == set(names[:3])      # capped at the 3-spell limit
    cm.dispatch("rmspell/Bless")                           # free up a slot
    cm.dispatch("addspell/Command")
    assert "Command" in cm.character.spells and len(cm.character.spells) == 3


def test_html_spells_shows_limit_and_collapsible_info():
    cm = _cleric_at_profs()
    cm.index = STEPS.index("spells")
    cm.spell_catalog = [{"name": "Bless", "school": "Combat", "level": 1,
                         "description": "The caster raises morale for nearby allies."}]
    cm.dispatch("addspell/Bless")
    h = cmh.generate(cm)
    assert "left" in h and "memorized" in h                # spell budget bar
    assert "What it does" in h and "raises morale for nearby allies" in h   # collapsible

"""Tests for monster_spells.py — matching a monster's spell-like abilities to the
compendium — and the spellsscreen anchor scheme they link to."""
import monster_spells as ms
from spellsscreen_html import spell_slug

# A tiny stand-in compendium: multi-word names, distinctive/common single words that
# cue-gate (Entangle, Suggestion, Fear, Slow), and stoplisted words (Regenerate, Armor).
NAMES = ["Charm Person", "Dispel Magic", "Teleport Without Error", "Improved Invisibility",
         "Invisibility", "Entangle", "Suggestion", "Fear", "Slow", "Regenerate", "Armor"]


def _idx():
    return ms.build_index(NAMES)


def test_slug_is_stable_and_shared():
    assert spell_slug("Cone of Cold") == "cone-of-cold"
    assert spell_slug("Otto's Irresistible Dance") == "otto-s-irresistible-dance"


def test_multiword_names_always_match_without_a_cue():
    hits = ms.find("It wreathes itself in dispel magic and charm person.", _idx())
    assert hits == [("Dispel Magic", "dispel-magic"), ("Charm Person", "charm-person")]


def test_single_word_names_need_a_casting_cue():
    # bare mention: no link
    assert ms.find("The vines entangle their prey.", _idx()) == []
    # with a frequency cue: linked (the green-dragon case)
    assert ms.find("Very old: entangle once a day.", _idx()) == [("Entangle", "entangle")]
    assert ms.find("It casts suggestion.", _idx()) == [("Suggestion", "suggestion")]


def test_as_spell_and_as_wand_cues_catch_eye_ray_lists():
    # the beholder's numbered eye rays: "(as spell)" / "(as wand)" tag them, and the
    # tag carries to the adjacent item in the list (Slow has none of its own here)
    text = "7. Fear (as wand)\n\n8. Slow (as spell, single target)"
    assert ms.find(text, _idx()) == [("Fear", "fear"), ("Slow", "slow")]


def test_bare_common_word_without_a_cue_stays_out():
    assert ms.find("The dragon's foes attack without fear as it moves slow.", _idx()) == []


def test_stoplisted_single_words_never_match_even_with_a_cue():
    # trait words whose innate description reads like a cast — excluded regardless
    assert ms.find("The troll regenerates 3 points per round.", _idx()) == []      # not Regenerate
    assert ms.find("It conjures armor at will.", _idx()) == []                     # not Armor


def test_find_returns_canonical_capitalized_names():
    (hit,) = ms.find("it casts CHARM PERSON on foes.", _idx())
    assert hit == ("Charm Person", "charm-person")          # compendium casing, not the prose's


def test_find_prefers_the_longest_name():
    (hit,) = ms.find("The creature has improved invisibility always active.", _idx())
    assert hit == ("Improved Invisibility", "improved-invisibility")   # not bare "invisibility"


def test_find_dedupes_by_slug():
    hits = ms.find("Charm person, then charm person again.", _idx())
    assert hits == [("Charm Person", "charm-person")]       # once, canonical


def test_find_in_scans_all_prose_not_just_combat():
    from monster import Monster
    # a caster whose spell list sits in the description/ecology, not Combat
    m = Monster(combat="It bites.",
                description="It can cast dispel magic and charm person as a spell.",
                ecology="Sometimes it uses entangle once a day.")
    names = [n for n, _ in ms.find_in(m, _idx())]
    assert "Dispel Magic" in names and "Charm Person" in names and "Entangle" in names
    # a plain brute names nothing anywhere
    assert ms.find_in(Monster(description="A big dumb club-swinger."), _idx()) == []


def test_empty_index_and_text_are_safe():
    assert not ms.build_index([])                           # falsy when it knows no names
    assert ms.find("charm person", ms.build_index([])) == []
    assert ms.find("", _idx()) == []


# ── the compendium anchors the links target ───────────────────────────────────

def test_generate_emits_one_anchor_per_distinct_name():
    import spellsscreen_html
    spells = [
        {"name": "Alarm", "caster": "wizard", "level": 1, "school": "Abjuration"},
        {"name": "Alarm", "caster": "wizard", "level": 1, "school": "Evocation"},
        {"name": "Charm Person", "caster": "wizard", "level": 1, "school": "Enchantment"},
    ]
    html = spellsscreen_html.generate(spells)
    assert html.count('id="spell-alarm"') == 1          # duplicate name -> anchor once
    assert 'id="spell-charm-person"' in html

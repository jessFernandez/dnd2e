"""The house-rule combat math behind the Combat Converter window.

These rules live in char_rules (the single source of truth) and are imported here
directly, not through calculator.py, so they can be tested without pulling in Qt.
calculator.py re-exports them for its window and adds no logic of its own; the
re-export is cross-checked in test_char_rules.
"""
from char_rules import (
    thac0_to_bonus, bonus_to_thac0, desc_to_asc, asc_to_desc,
    to_hit_need, hit_chance, is_critical, CRIT_MIN_ROLL, CRIT_MIN_MARGIN,
)


def test_thac0_to_bonus():
    assert thac0_to_bonus(20) == 0
    assert thac0_to_bonus(15) == 5
    assert thac0_to_bonus(11) == 9


def test_thac0_bonus_roundtrip():
    for t in range(-5, 26):
        assert bonus_to_thac0(thac0_to_bonus(t)) == t


def test_ac_conversion():
    assert desc_to_asc(10) == 10      # unarmored
    assert desc_to_asc(0) == 20
    assert desc_to_asc(-5) == 25
    assert desc_to_asc(3) == 17       # plate mail


def test_ac_roundtrip():
    for d in range(-10, 13):
        assert asc_to_desc(desc_to_asc(d)) == d


def test_conversion_is_consistent_with_book_math():
    # level-6 fighter (THAC0 15) vs plate mail (descending AC 3):
    # the book target number equals the house-rule target number.
    thac0, ac_desc = 15, 3
    book_need = thac0 - ac_desc
    house_need = to_hit_need(thac0_to_bonus(thac0), desc_to_asc(ac_desc))
    assert house_need == book_need == 12


def test_to_hit_and_hit_chance():
    assert to_hit_need(5, 17) == 12
    assert hit_chance(12) == 45        # need 12+ -> 9 faces (12..20)
    assert hit_chance(1) == 95         # clamps to 2 (a natural 1 misses)
    assert hit_chance(25) == 5         # clamps to 20 (a natural 20 hits)


# ── the house-rule critical: natural 18+ that beats AC by 5+ ──────────────────

def test_critical_needs_both_a_high_roll_and_a_wide_margin():
    # bonus +8 vs AC 10: an 18 totals 26, beating AC by 16 -> crit.
    assert is_critical(18, 8, 10) is True
    # a natural 20 that only just connects (total 20 vs AC 20) is a hit, not a crit.
    assert is_critical(20, 0, 20) is False
    # a wide margin on a low die is not a crit either.
    assert is_critical(17, 15, 5) is False       # 17 < CRIT_MIN_ROLL


def test_critical_boundaries_track_the_constants():
    # Exactly CRIT_MIN_ROLL, clearing AC by exactly CRIT_MIN_MARGIN, is the edge case.
    ac = 12
    bonus = ac + CRIT_MIN_MARGIN - CRIT_MIN_ROLL     # so CRIT_MIN_ROLL total = ac + margin
    assert is_critical(CRIT_MIN_ROLL, bonus, ac) is True
    assert is_critical(CRIT_MIN_ROLL, bonus - 1, ac) is False   # one short of the margin
    assert is_critical(CRIT_MIN_ROLL - 1, bonus + 99, ac) is False  # one short of the roll

"""Unit tests for the house-rule combat conversions."""
from calculator import (
    thac0_to_bonus, bonus_to_thac0, desc_to_asc, asc_to_desc, to_hit_need, hit_chance,
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

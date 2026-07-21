"""char_rules.py — the structured, computable AD&D 2e character-creation model.

This is the foundation the charactermancer builds on. The rulebook is stored as
HTML pages (great for browsing/Jarvis) but a character *builder* needs the finite
chargen tables as data it can compute with: ability-score modifiers, racial
requirements/adjustments/level-limits, class requirements and XP/THAC0/saving-throw
progressions, and proficiency slots.

Every number here was transcribed from the imported PHB/DMG tables (Tables 1–8,
13, 14/20/23/25, 34, 53, 60 and DMG Table 7) — the same data the app already
serves — so the model can't drift from the rulebook.

Two design rules keep this a clean foundation:

  * **Pure and Qt-free.** Like toc.py / navigation.py, this module is plain data +
    functions, unit-tested without a running app.
  * **House rules are a computable override layer, not prose.** The campaign's
    ~15 chargen-relevant house rules live in `HOUSE_RULES` and are applied by the
    same functions the standard rules use (pass `house_rules=False` for RAW).
    The combat conversions (THAC0⇄attack-bonus, descending⇄ascending AC) are the
    single source of truth that calculator.py now imports, so the builder and the
    combat converter can't disagree.

Adding data later (e.g. a large list of nonweapon proficiencies) is new rows in
these structures, not new code.
"""
from dataclasses import dataclass

import nonweapon_book as _book
import equipment as _equipment


# ═══════════════════════════════════════════════════════════════════════════
#  Combat conversions — the campaign's core house rule (single source of truth).
#  calculator.py imports these; do not duplicate them there.
# ═══════════════════════════════════════════════════════════════════════════

def thac0_to_bonus(thac0: int) -> int:
    """House rule: THAC0 is removed; attack bonus = 20 − THAC0."""
    return 20 - thac0


def bonus_to_thac0(bonus: int) -> int:
    return 20 - bonus


def desc_to_asc(desc_ac: int) -> int:
    """House rule: ascending AC = 20 − descending AC."""
    return 20 - desc_ac


def asc_to_desc(asc_ac: int) -> int:
    return 20 - asc_ac


def to_hit_need(attack_bonus: int, target_asc_ac: int) -> int:
    """The raw d20 result needed to hit under the house rule (before nat-1/nat-20
    clamping): roll d20 + attack bonus and meet or beat the target's ascending AC."""
    return target_asc_ac - attack_bonus


def hit_chance(need: int) -> int:
    """Percent chance a d20 meets ``need``, clamped: a natural 1 always misses and a
    natural 20 always hits, so the chance is bounded to 5%–95%."""
    eff = max(2, min(20, need))
    return (21 - eff) * 5


#: The house-rule critical: a natural 18+ that also beats the target's AC by 5+.
CRIT_MIN_ROLL = 18
CRIT_MIN_MARGIN = 5


def is_critical(nat_roll: int, attack_bonus: int, target_asc_ac: int) -> bool:
    """Whether an attack is a critical hit under the house rule: the natural die is
    ``CRIT_MIN_ROLL`` or more *and* the total beats the target's ascending AC by at
    least ``CRIT_MIN_MARGIN``. (A high roll that only just connects is not a crit.)"""
    if nat_roll < CRIT_MIN_ROLL:
        return False
    return (nat_roll + attack_bonus) - target_asc_ac >= CRIT_MIN_MARGIN


#: Initiative speed factor for a creature attacking with natural weapons, keyed by
#: size category (DMG "Modifiers to the Initiative Roll"). Initiative is rolled low
#: — a bigger creature carries a larger modifier and so tends to act later. The DM
#: Screen (dmscreen_html) and the monster sheet both read this, so they can't
#: disagree — the same single-source-of-truth rule as the THAC0/AC conversions.
SIZE_INITIATIVE_MODIFIER = {
    "T": 0,    # Tiny
    "S": 3,    # Small
    "M": 3,    # Medium
    "L": 6,    # Large
    "H": 9,    # Huge
    "G": 12,   # Gargantuan
}


def monster_initiative_modifier(size_category: str):
    """The natural-attack initiative modifier for a size category letter
    (T/S/M/L/H/G), or None if unrecognized. Takes the first letter, case-folded,
    so ``"L"``, ``"l"`` and ``"Large"`` all resolve. See SIZE_INITIATIVE_MODIFIER."""
    key = (size_category or "").strip()[:1].upper()
    return SIZE_INITIATIVE_MODIFIER.get(key)


# ═══════════════════════════════════════════════════════════════════════════
#  Ability-score modifier tables (PHB Tables 1–6)
#  Stored as (low, high, mods) bands matching the printed rows; look up by score.
# ═══════════════════════════════════════════════════════════════════════════

def _band(rows, score):
    for lo, hi, mods in rows:
        if lo <= score <= hi:
            return mods
    raise ValueError(f"score {score} out of range 1–25")


@dataclass(frozen=True)
class StrengthMods:
    hit: int          # attack (to-hit) adjustment
    dmg: int          # damage adjustment
    weight_allow: int # lb. carried before encumbrance
    max_press: int    # lb.
    open_doors: int   # x-in-20 chance
    bend_bars: int    # % bend bars / lift gates


# Table 1. Score 18 exceptional-Strength bands use "18/xx" string keys.
_STRENGTH = {
    1:  StrengthMods(-5, -4, 1, 3, 1, 0),
    2:  StrengthMods(-3, -2, 1, 5, 1, 0),
    3:  StrengthMods(-3, -1, 5, 10, 2, 0),
    4:  StrengthMods(-2, -1, 10, 25, 3, 0),  5: StrengthMods(-2, -1, 10, 25, 3, 0),
    6:  StrengthMods(-1, 0, 20, 55, 4, 0),   7: StrengthMods(-1, 0, 20, 55, 4, 0),
    8:  StrengthMods(0, 0, 35, 90, 5, 1),    9: StrengthMods(0, 0, 35, 90, 5, 1),
    10: StrengthMods(0, 0, 40, 115, 6, 2),  11: StrengthMods(0, 0, 40, 115, 6, 2),
    12: StrengthMods(0, 0, 45, 140, 7, 4),  13: StrengthMods(0, 0, 45, 140, 7, 4),
    14: StrengthMods(0, 0, 55, 170, 8, 7),  15: StrengthMods(0, 0, 55, 170, 8, 7),
    16: StrengthMods(0, 1, 70, 195, 9, 10),
    17: StrengthMods(1, 1, 85, 220, 10, 13),
    18: StrengthMods(1, 2, 110, 255, 11, 16),
    19: StrengthMods(3, 7, 485, 640, 16, 50),
    20: StrengthMods(3, 8, 535, 700, 17, 60),
    21: StrengthMods(4, 9, 635, 810, 17, 70),
    22: StrengthMods(4, 10, 785, 970, 18, 80),
    23: StrengthMods(5, 11, 935, 1130, 18, 90),
    24: StrengthMods(6, 12, 1235, 1440, 19, 95),
    25: StrengthMods(7, 14, 1535, 1750, 19, 99),
}
# Exceptional Strength (score exactly 18 with a d100 percentile roll).
_STRENGTH_EXCEPTIONAL = {
    "18/01-50": StrengthMods(1, 3, 135, 280, 12, 20),
    "18/51-75": StrengthMods(2, 3, 160, 305, 13, 25),
    "18/76-90": StrengthMods(2, 4, 185, 330, 14, 30),
    "18/91-99": StrengthMods(2, 5, 235, 380, 15, 35),
    "18/00":    StrengthMods(3, 6, 335, 480, 16, 40),
}


def strength_mods(score, exceptional=None) -> StrengthMods:
    """Strength modifiers. For an 18 with exceptional Strength, pass a percentile
    band key like "18/76-90" (or a 1–100 roll) as `exceptional`."""
    if score == 18 and exceptional is not None:
        return _STRENGTH_EXCEPTIONAL[exceptional_str_band(exceptional)]
    return _STRENGTH[score]


def exceptional_str_band(roll) -> str:
    """Map a percentile roll (1–100, or 0/100 for 00) to its 18/xx band key."""
    if isinstance(roll, str):
        return roll
    r = 100 if roll in (0, 100) else roll
    if r <= 50:  return "18/01-50"
    if r <= 75:  return "18/51-75"
    if r <= 90:  return "18/76-90"
    if r <= 99:  return "18/91-99"
    return "18/00"


@dataclass(frozen=True)
class DexterityMods:
    reaction: int       # surprise/reaction adjustment
    missile: int        # missile attack adjustment
    defensive_ac: int   # defensive AC adjustment (negative = better)


_DEXTERITY = [
    (1, 1, DexterityMods(-6, -6, 5)), (2, 2, DexterityMods(-4, -4, 5)),
    (3, 3, DexterityMods(-3, -3, 4)), (4, 4, DexterityMods(-2, -2, 3)),
    (5, 5, DexterityMods(-1, -1, 2)), (6, 6, DexterityMods(0, 0, 1)),
    (7, 14, DexterityMods(0, 0, 0)),  (15, 15, DexterityMods(0, 0, -1)),
    (16, 16, DexterityMods(1, 1, -2)), (17, 17, DexterityMods(2, 2, -3)),
    (18, 18, DexterityMods(2, 2, -4)), (19, 20, DexterityMods(3, 3, -4)),
    (21, 23, DexterityMods(4, 4, -5)), (24, 25, DexterityMods(5, 5, -6)),
]


def dexterity_mods(score) -> DexterityMods:
    return _band(_DEXTERITY, score)


@dataclass(frozen=True)
class ConstitutionMods:
    hp_adj: int          # per-Hit-Die HP adjustment (non-warrior cap of +2)
    hp_adj_warrior: int  # warriors get the higher bonus at 17+
    system_shock: int    # %
    resurrection: int    # %
    poison_save: int     # bonus to poison saves


_CONSTITUTION = [
    (1, 1, ConstitutionMods(-3, -3, 25, 30, -2)), (2, 2, ConstitutionMods(-2, -2, 30, 35, -1)),
    (3, 3, ConstitutionMods(-2, -2, 35, 40, 0)),  (4, 4, ConstitutionMods(-1, -1, 40, 45, 0)),
    (5, 5, ConstitutionMods(-1, -1, 45, 50, 0)),  (6, 6, ConstitutionMods(-1, -1, 50, 55, 0)),
    (7, 7, ConstitutionMods(0, 0, 55, 60, 0)),    (8, 8, ConstitutionMods(0, 0, 60, 65, 0)),
    (9, 9, ConstitutionMods(0, 0, 65, 70, 0)),    (10, 10, ConstitutionMods(0, 0, 70, 75, 0)),
    (11, 11, ConstitutionMods(0, 0, 75, 80, 0)),  (12, 12, ConstitutionMods(0, 0, 80, 85, 0)),
    (13, 13, ConstitutionMods(0, 0, 85, 90, 0)),  (14, 14, ConstitutionMods(0, 0, 88, 92, 0)),
    (15, 15, ConstitutionMods(1, 1, 90, 94, 0)),  (16, 16, ConstitutionMods(2, 2, 95, 96, 0)),
    (17, 17, ConstitutionMods(2, 3, 97, 98, 0)),  (18, 18, ConstitutionMods(2, 4, 99, 100, 0)),
    (19, 19, ConstitutionMods(2, 5, 99, 100, 1)), (20, 20, ConstitutionMods(2, 5, 99, 100, 1)),
    (21, 21, ConstitutionMods(2, 6, 99, 100, 2)), (22, 22, ConstitutionMods(2, 6, 99, 100, 2)),
    (23, 23, ConstitutionMods(2, 6, 99, 100, 3)), (24, 24, ConstitutionMods(2, 7, 99, 100, 3)),
    (25, 25, ConstitutionMods(2, 7, 100, 100, 4)),
]


def constitution_mods(score) -> ConstitutionMods:
    return _band(_CONSTITUTION, score)


@dataclass(frozen=True)
class IntelligenceMods:
    languages: int          # also bonus nonweapon proficiency slots (optional rule)
    max_spell_level: int    # highest wizard spell level castable (0 = none)
    learn_spell: int        # % chance to learn a spell (0 = n/a)
    max_spells_per_level: int  # 999 = "All"


_INTELLIGENCE = [
    (1, 8, IntelligenceMods(1, 0, 0, 0)),   # 1 => can't speak; treat as 0/1 language
    (9, 9, IntelligenceMods(2, 4, 35, 6)),  (10, 10, IntelligenceMods(2, 5, 40, 7)),
    (11, 11, IntelligenceMods(2, 5, 45, 7)), (12, 12, IntelligenceMods(3, 6, 50, 7)),
    (13, 13, IntelligenceMods(3, 6, 55, 9)), (14, 14, IntelligenceMods(4, 7, 60, 9)),
    (15, 15, IntelligenceMods(4, 7, 65, 11)), (16, 16, IntelligenceMods(5, 8, 70, 11)),
    (17, 17, IntelligenceMods(6, 8, 75, 14)), (18, 18, IntelligenceMods(7, 9, 85, 18)),
    (19, 19, IntelligenceMods(8, 9, 95, 999)), (20, 20, IntelligenceMods(9, 9, 96, 999)),
    (21, 21, IntelligenceMods(10, 9, 97, 999)), (22, 22, IntelligenceMods(11, 9, 98, 999)),
    (23, 23, IntelligenceMods(12, 9, 99, 999)), (24, 24, IntelligenceMods(15, 9, 100, 999)),
    (25, 25, IntelligenceMods(20, 9, 100, 999)),
]


def intelligence_mods(score) -> IntelligenceMods:
    return _band(_INTELLIGENCE, score)


@dataclass(frozen=True)
class WisdomMods:
    magic_defense: int      # saving-throw adjustment vs. mind-affecting magic
    spell_failure: int      # % priest spell failure
    _bonus_spell_increment: tuple = ()  # spell levels added AT this score (cumulative)


# Table 5. The bonus-spell column is cumulative: a priest gets every increment
# from Wis 13 up to their score. We store the per-score increment and sum it.
_WISDOM = [
    (1, 1, WisdomMods(-6, 80)), (2, 2, WisdomMods(-4, 60)), (3, 3, WisdomMods(-3, 50)),
    (4, 4, WisdomMods(-2, 45)), (5, 5, WisdomMods(-1, 40)), (6, 6, WisdomMods(-1, 35)),
    (7, 7, WisdomMods(-1, 30)), (8, 8, WisdomMods(0, 25)),  (9, 9, WisdomMods(0, 20)),
    (10, 10, WisdomMods(0, 15)), (11, 11, WisdomMods(0, 10)), (12, 12, WisdomMods(0, 5)),
    (13, 13, WisdomMods(0, 0, (1,))), (14, 14, WisdomMods(0, 0, (1,))),
    (15, 15, WisdomMods(1, 0, (2,))), (16, 16, WisdomMods(2, 0, (2,))),
    (17, 17, WisdomMods(3, 0, (3,))), (18, 18, WisdomMods(4, 0, (4,))),
    (19, 19, WisdomMods(4, 0, (1, 3))), (20, 20, WisdomMods(4, 0, (2, 4))),
    (21, 21, WisdomMods(4, 0, (3, 5))), (22, 22, WisdomMods(4, 0, (4, 5))),
    (23, 23, WisdomMods(4, 0, (1, 6))), (24, 24, WisdomMods(4, 0, (5, 6))),
    (25, 25, WisdomMods(4, 0, (6, 7))),
]


def wisdom_mods(score) -> WisdomMods:
    return _band(_WISDOM, score)


def priest_bonus_spells(wis) -> dict:
    """Cumulative bonus priest spells by spell level, e.g. Wis 18 -> {1:2,2:2,3:1,4:1}."""
    out: dict = {}
    for lo, hi, mods in _WISDOM:
        if lo > wis:
            break
        for lvl in mods._bonus_spell_increment:
            out[lvl] = out.get(lvl, 0) + 1
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Spell progression (PHB Tables 21, 24, 17, 18, 32)
#
#  Each row lists the spells castable of levels 1..N at that class level; a 0
#  means none. Below a table's first row the class casts nothing; at or above its
#  last row the slots stop improving (the "maximum spell ability" footnote on the
#  paladin and ranger tables).
# ═══════════════════════════════════════════════════════════════════════════

# Table 21 — Wizard (spell levels 1-9).
_WIZARD_SPELL_SLOTS = {
    1:  (1, 0, 0, 0, 0, 0, 0, 0, 0),
    2:  (2, 0, 0, 0, 0, 0, 0, 0, 0),
    3:  (2, 1, 0, 0, 0, 0, 0, 0, 0),
    4:  (3, 2, 0, 0, 0, 0, 0, 0, 0),
    5:  (4, 2, 1, 0, 0, 0, 0, 0, 0),
    6:  (4, 2, 2, 0, 0, 0, 0, 0, 0),
    7:  (4, 3, 2, 1, 0, 0, 0, 0, 0),
    8:  (4, 3, 3, 2, 0, 0, 0, 0, 0),
    9:  (4, 3, 3, 2, 1, 0, 0, 0, 0),
    10: (4, 4, 3, 2, 2, 0, 0, 0, 0),
    11: (4, 4, 4, 3, 3, 0, 0, 0, 0),
    12: (4, 4, 4, 4, 4, 1, 0, 0, 0),
    13: (5, 5, 5, 4, 4, 2, 0, 0, 0),
    14: (5, 5, 5, 4, 4, 2, 1, 0, 0),
    15: (5, 5, 5, 5, 5, 2, 1, 0, 0),
    16: (5, 5, 5, 5, 5, 3, 2, 1, 0),
    17: (5, 5, 5, 5, 5, 3, 3, 2, 0),
    18: (5, 5, 5, 5, 5, 3, 3, 2, 1),
    19: (5, 5, 5, 5, 5, 3, 3, 3, 1),
    20: (5, 5, 5, 5, 5, 4, 3, 3, 2),
}

# Table 24 — Priest (spell levels 1-7). Footnotes: 6th-level spells are usable
# only with Wisdom 17+, 7th-level only with Wisdom 18+ (see priest_spell_slots).
_PRIEST_SPELL_SLOTS = {
    1:  (1, 0, 0, 0, 0, 0, 0),
    2:  (2, 0, 0, 0, 0, 0, 0),
    3:  (2, 1, 0, 0, 0, 0, 0),
    4:  (3, 2, 0, 0, 0, 0, 0),
    5:  (3, 3, 1, 0, 0, 0, 0),
    6:  (3, 3, 2, 0, 0, 0, 0),
    7:  (3, 3, 2, 1, 0, 0, 0),
    8:  (3, 3, 3, 2, 0, 0, 0),
    9:  (4, 4, 3, 2, 1, 0, 0),
    10: (4, 4, 3, 3, 2, 0, 0),
    11: (5, 4, 4, 3, 2, 1, 0),
    12: (6, 5, 5, 3, 2, 2, 0),
    13: (6, 6, 6, 4, 2, 2, 0),
    14: (6, 6, 6, 5, 3, 2, 1),
    15: (6, 6, 6, 6, 4, 2, 1),
    16: (7, 7, 7, 6, 4, 3, 1),
    17: (7, 7, 7, 7, 5, 3, 2),
    18: (8, 8, 8, 8, 6, 4, 2),
    19: (9, 9, 8, 8, 6, 4, 2),
    20: (9, 9, 9, 8, 7, 5, 2),
}

# Table 17 — Paladin: priest spells from 9th level (priest spell levels 1-4).
_PALADIN_SPELL_SLOTS = {
    9:  (1, 0, 0, 0),
    10: (2, 0, 0, 0),
    11: (2, 1, 0, 0),
    12: (2, 2, 0, 0),
    13: (2, 2, 1, 0),
    14: (3, 2, 1, 0),
    15: (3, 2, 1, 1),
    16: (3, 3, 2, 1),
    17: (3, 3, 3, 1),
    18: (3, 3, 3, 1),
    19: (3, 3, 3, 2),
    20: (3, 3, 3, 3),
}

# Table 18 — Ranger: priest spells from 8th level (priest spell levels 1-3).
_RANGER_SPELL_SLOTS = {
    8:  (1, 0, 0),
    9:  (2, 0, 0),
    10: (2, 1, 0),
    11: (2, 2, 0),
    12: (2, 2, 1),
    13: (3, 2, 1),
    14: (3, 2, 2),
    15: (3, 3, 2),
    16: (3, 3, 3),      # "maximum spell ability" — no further gain
}

# Table 32 — Bard: wizard spells from 2nd level (wizard spell levels 1-6).
_BARD_SPELL_SLOTS = {
    2:  (1, 0, 0, 0, 0, 0),
    3:  (2, 0, 0, 0, 0, 0),
    4:  (2, 1, 0, 0, 0, 0),
    5:  (3, 1, 0, 0, 0, 0),
    6:  (3, 2, 0, 0, 0, 0),
    7:  (3, 2, 1, 0, 0, 0),
    8:  (3, 3, 1, 0, 0, 0),
    9:  (3, 3, 2, 0, 0, 0),
    10: (3, 3, 2, 1, 0, 0),
    11: (3, 3, 3, 1, 0, 0),
    12: (3, 3, 3, 2, 0, 0),
    13: (3, 3, 3, 2, 1, 0),
    14: (3, 3, 3, 3, 1, 0),
    15: (3, 3, 3, 3, 2, 0),
    16: (4, 3, 3, 3, 2, 1),
    17: (4, 4, 3, 3, 3, 1),
    18: (4, 4, 4, 3, 3, 2),
    19: (4, 4, 4, 4, 3, 2),
    20: (4, 4, 4, 4, 4, 3),
}

# Specialist wizards gain one extra spell per castable spell level (of their
# school). Illusionist is the only specialist the builder offers.
_SPECIALIST_WIZARDS = frozenset({"Illusionist"})


def _progression_slots(table: dict, level: int) -> dict:
    """{spell_level: count} for a class level, dropping the zero entries. Below the
    table's first row the class casts nothing; past its last row slots are capped."""
    if not table or level < min(table):
        return {}
    row = table[min(level, max(table))]
    return {i + 1: n for i, n in enumerate(row) if n}


def wizard_spell_slots(level: int, int_score=None, specialist: bool = False) -> dict:
    """Wizard spells castable per spell level. Intelligence caps the highest spell
    level a wizard can ever learn (Table 4); a specialist gains one extra spell of
    each castable level."""
    slots = _progression_slots(_WIZARD_SPELL_SLOTS, level)
    if int_score is not None:
        cap = intelligence_mods(int_score).max_spell_level
        slots = {lvl: n for lvl, n in slots.items() if lvl <= cap}
    if specialist:
        slots = {lvl: n + 1 for lvl, n in slots.items()}
    return slots


def priest_spell_slots(level: int, wis) -> dict:
    """Priest spells memorizable per spell level, INCLUDING the Wisdom bonus spells
    (Table 5). The base table decides which spell levels are castable and the bonus
    only augments those, so a low-level priest gets no bonus for spell levels too
    high to cast. Table 24's footnotes also gate the top two levels on Wisdom:
    6th-level spells need Wis 17+, 7th-level need Wis 18+."""
    slots = _progression_slots(_PRIEST_SPELL_SLOTS, level)
    if wis is None or wis < 17:
        slots.pop(6, None)
    if wis is None or wis < 18:
        slots.pop(7, None)
    bonus = priest_bonus_spells(wis) if wis is not None else {}
    for spell_level in list(slots):
        slots[spell_level] += bonus.get(spell_level, 0)
    return slots


def paladin_spell_slots(level: int) -> dict:
    """Priest spells for a paladin (9th level+). PHB: 'Unlike a priest, the paladin
    does not gain extra spells for a high Wisdom score.'"""
    return _progression_slots(_PALADIN_SPELL_SLOTS, level)


def ranger_spell_slots(level: int) -> dict:
    """Priest spells for a ranger (8th level+), plant/animal spheres only. PHB: 'He
    does not gain bonus spells for a high Wisdom score.'"""
    return _progression_slots(_RANGER_SPELL_SLOTS, level)


def bard_spell_slots(level: int, int_score=None) -> dict:
    """Wizard spells for a bard (2nd level+), capped by Intelligence like a wizard."""
    slots = _progression_slots(_BARD_SPELL_SLOTS, level)
    if int_score is not None:
        cap = intelligence_mods(int_score).max_spell_level
        slots = {lvl: n for lvl, n in slots.items() if lvl <= cap}
    return slots


def spell_slots(class_name: str, level: int, wis=None, int_score=None) -> dict:
    """{spell_level: count} a class can cast at a level; {} for non-casters and for
    casters below the level at which their progression starts."""
    if class_name in ("Mage", "Illusionist"):
        return wizard_spell_slots(level, int_score, class_name in _SPECIALIST_WIZARDS)
    if class_name in ("Cleric", "Druid"):
        return priest_spell_slots(level, wis)
    if class_name == "Paladin":
        return paladin_spell_slots(level)
    if class_name == "Ranger":
        return ranger_spell_slots(level)
    if class_name == "Bard":
        return bard_spell_slots(level, int_score)
    return {}


def max_spell_level(class_name: str, level: int, wis=None, int_score=None) -> int:
    """The highest spell level castable, or 0 for a non-caster."""
    slots = spell_slots(class_name, level, wis, int_score)
    return max(slots) if slots else 0


def spell_caster_group(class_name: str):
    """'wizard' | 'priest' | None — which spell list a class ever draws on, ignoring
    level. Bards cast wizard spells; paladins and rangers cast priest spells."""
    if class_name in ("Mage", "Illusionist", "Bard"):
        return "wizard"
    if class_name in ("Cleric", "Druid", "Paladin", "Ranger"):
        return "priest"
    return None


@dataclass(frozen=True)
class CharismaMods:
    max_henchmen: int
    loyalty_base: int
    reaction: int


_CHARISMA = [
    (1, 1, CharismaMods(0, -8, -7)), (2, 2, CharismaMods(1, -7, -6)), (3, 3, CharismaMods(1, -6, -5)),
    (4, 4, CharismaMods(1, -5, -4)), (5, 5, CharismaMods(2, -4, -3)), (6, 6, CharismaMods(2, -3, -2)),
    (7, 7, CharismaMods(3, -2, -1)), (8, 8, CharismaMods(3, -1, 0)),  (9, 9, CharismaMods(4, 0, 0)),
    (10, 10, CharismaMods(4, 0, 0)), (11, 11, CharismaMods(4, 0, 0)), (12, 12, CharismaMods(5, 0, 0)),
    (13, 13, CharismaMods(5, 0, 1)), (14, 14, CharismaMods(6, 1, 2)), (15, 15, CharismaMods(7, 3, 3)),
    (16, 16, CharismaMods(8, 4, 5)), (17, 17, CharismaMods(10, 6, 6)), (18, 18, CharismaMods(15, 8, 7)),
    (19, 19, CharismaMods(20, 10, 8)), (20, 20, CharismaMods(25, 12, 9)), (21, 21, CharismaMods(30, 14, 10)),
    (22, 22, CharismaMods(35, 16, 11)), (23, 23, CharismaMods(40, 18, 12)), (24, 24, CharismaMods(45, 20, 13)),
    (25, 25, CharismaMods(50, 20, 14)),
]


def charisma_mods(score) -> CharismaMods:
    return _band(_CHARISMA, score)


ABILITIES = ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma")


# ── Perception (house-rule 7th ability) ──────────────────────────────────────
# The campaign adds Perception as its own score, which *takes over* two effects
# from the standard abilities: the surprise/reaction adjustment (off Dexterity)
# and illusion immunity (off Intelligence). It uses those same published value
# columns, now indexed by the Perception score instead of Dex/Int. Races don't
# adjust it and no class requires it, so it lives outside ABILITIES and only
# applies when house rules are on.
PERCEPTION = "Perception"

# Illusion immunity by score (from the Intelligence table's immunity column):
# only matters at 19+ (unreachable by a 4d6 roll, but modelled for magic boosts).
_ILLUSION_IMMUNITY = {19: 1, 20: 2, 21: 3, 22: 4, 23: 5, 24: 6, 25: 7}


@dataclass(frozen=True)
class PerceptionMods:
    surprise: int           # surprise / reaction adjustment (house rule: moved off Dexterity)
    illusion_immunity: int  # spell level of illusions ignored (moved off Intelligence); 0 = none


def perception_mods(score) -> PerceptionMods:
    return PerceptionMods(surprise=dexterity_mods(score).reaction,
                          illusion_immunity=_ILLUSION_IMMUNITY.get(score, 0))


def house_abilities(house_rules: bool = True) -> tuple:
    """The ability scores a character rolls: the standard six, plus Perception
    when house rules are active."""
    return ABILITIES + (PERCEPTION,) if house_rules else ABILITIES


_ABILITY_FN = {
    "Strength": strength_mods, "Dexterity": dexterity_mods, "Constitution": constitution_mods,
    "Intelligence": intelligence_mods, "Wisdom": wisdom_mods, "Charisma": charisma_mods,
    "Perception": perception_mods,
}


def ability_mods(ability: str, score):
    """Modifier record for any ability by name (title-case), e.g. ability_mods('Wisdom', 16)."""
    return _ABILITY_FN[ability](score)


# ═══════════════════════════════════════════════════════════════════════════
#  Races (PHB Table 7 requirements, Table 8 adjustments, DMG Table 7 level limits)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Race:
    name: str
    requirements: dict   # ability -> (min, max)
    adjustments: dict    # ability -> +/- delta
    level_limits: dict   # class name -> max level (None = unlimited)
    infravision: int = 0 # feet
    movement: int = 12   # base movement rate (PHB); demihumans are 6
    notes: tuple = ()


# Humans have no ability min/max beyond class minimums, no adjustments, and can
# be any class to unlimited level (handled by name in race_allows / max_level).
RACES = {
    "Human": Race(
        "Human", requirements={}, adjustments={}, level_limits={},
        notes=("Any class, no level limit.", "May be dual-classed."),
    ),
    "Dwarf": Race(
        "Dwarf",
        requirements={"Strength": (8, 18), "Dexterity": (3, 17), "Constitution": (11, 18),
                      "Intelligence": (3, 18), "Wisdom": (3, 18), "Charisma": (3, 17)},
        adjustments={"Constitution": 1, "Charisma": -1},
        level_limits={"Cleric": 10, "Fighter": 15, "Thief": 12},
        infravision=60, movement=6,
        notes=("+1 save/4 Con vs. magic & poison.", "Combat & reaction bonuses vs. giant-class.",
               "+1 to hit orcs, half-orcs, goblins, hobgoblins."),
    ),
    "Elf": Race(
        "Elf",
        requirements={"Strength": (3, 18), "Dexterity": (6, 18), "Constitution": (7, 18),
                      "Intelligence": (8, 18), "Wisdom": (3, 18), "Charisma": (8, 18)},
        adjustments={"Dexterity": 1, "Constitution": -1},
        level_limits={"Cleric": 12, "Fighter": 12, "Mage": 15, "Ranger": 15, "Thief": 12},
        infravision=60,
        notes=("90% resistant to sleep and charm.", "Secret/concealed door detection.",
               "+1 to hit with bows (non-crossbow) and long/short swords."),
    ),
    "Gnome": Race(
        "Gnome",
        requirements={"Strength": (6, 18), "Dexterity": (3, 18), "Constitution": (8, 18),
                      "Intelligence": (6, 18), "Wisdom": (3, 18), "Charisma": (3, 18)},
        adjustments={"Intelligence": 1, "Wisdom": -1},
        level_limits={"Cleric": 9, "Fighter": 11, "Illusionist": 15, "Thief": 13},
        infravision=60, movement=6,
        notes=("+1 save/3.5 Con vs. magic.", "Combat & reaction bonuses vs. kobolds/goblins.",
               "Detect certain stonework/depth."),
    ),
    "Half-Elf": Race(
        "Half-Elf",
        requirements={"Strength": (3, 18), "Dexterity": (6, 18), "Constitution": (6, 18),
                      "Intelligence": (4, 18), "Wisdom": (3, 18), "Charisma": (3, 18)},
        adjustments={},
        level_limits={"Bard": None, "Cleric": 14, "Druid": 9, "Fighter": 14,
                      "Mage": 12, "Ranger": 16, "Thief": 12},
        infravision=60,
        notes=("30% resistant to sleep and charm.", "Secret-door detection.", "May be multi-classed."),
    ),
    "Halfling": Race(
        "Halfling",
        requirements={"Strength": (7, 18), "Dexterity": (7, 18), "Constitution": (10, 18),
                      "Intelligence": (6, 18), "Wisdom": (3, 17), "Charisma": (3, 18)},
        adjustments={"Dexterity": 1, "Strength": -1},
        level_limits={"Cleric": 8, "Fighter": 9, "Thief": 15},
        infravision=30, movement=6,
        notes=("+1 save/3.5 Con vs. magic & poison.", "+1 to hit with slings and thrown weapons.",
               "Fighters do not roll for exceptional Strength."),
    ),
}


def race_allows(race: str, class_name: str) -> bool:
    """Can a member of this race be this class at all?"""
    r = RACES[race]
    if r.name == "Human":
        return True
    return class_name in r.level_limits


def max_level(race: str, class_name: str):
    """Maximum attainable level for race/class; None means unlimited. Raises if disallowed."""
    r = RACES[race]
    if r.name == "Human":
        return None
    if class_name not in r.level_limits:
        raise ValueError(f"{race} cannot be a {class_name}")
    return r.level_limits[class_name]


def apply_racial_adjustments(race: str, abilities: dict) -> dict:
    """Return a new ability dict with the race's Table 8 adjustments applied."""
    out = dict(abilities)
    for ability, delta in RACES[race].adjustments.items():
        if ability in out:
            out[ability] = out[ability] + delta
    return out


def meets_racial_requirements(race: str, abilities: dict) -> list:
    """Return a list of (ability, min, max, value) tuples that fail the race's
    Table 7 range; empty list means the character qualifies for the race."""
    fails = []
    for ability, (lo, hi) in RACES[race].requirements.items():
        val = abilities.get(ability)
        if val is not None and not (lo <= val <= hi):
            fails.append((ability, lo, hi, val))
    return fails


# ═══════════════════════════════════════════════════════════════════════════
#  Classes (PHB Table 13 minimums, XP Tables 14/20/23/25, group data)
# ═══════════════════════════════════════════════════════════════════════════

# Group-level rules shared by every class in the group.
#   hit_die         — HD type (standard rules)
#   name_level      — level after which HD stop; fixed HP is added per level instead
#   hp_after        — flat HP added each level past name level
#   weapon_slots    — (initial, levels_per_extra, nonprof_penalty)
#   nonweapon_slots — (initial, levels_per_extra)
@dataclass(frozen=True)
class ClassGroup:
    name: str
    hit_die: int
    name_level: int
    hp_after: int
    weapon_slots: tuple
    nonweapon_slots: tuple


GROUPS = {
    "Warrior": ClassGroup("Warrior", 10, 9, 3, (4, 3, -2), (3, 3)),
    "Wizard":  ClassGroup("Wizard", 4, 10, 1, (1, 6, -5), (4, 3)),
    "Priest":  ClassGroup("Priest", 8, 9, 2, (2, 4, -3), (4, 3)),
    "Rogue":   ClassGroup("Rogue", 6, 10, 2, (2, 4, -3), (3, 4)),
}


# Experience-point thresholds, index 0 = level 1 (transcribed from the PHB).
_XP = {
    "Fighter":  [0, 2000, 4000, 8000, 16000, 32000, 64000, 125000, 250000, 500000,
                 750000, 1000000, 1250000, 1500000, 1750000, 2000000, 2250000, 2500000, 2750000, 3000000],
    "Ranger":   [0, 2250, 4500, 9000, 18000, 36000, 75000, 150000, 300000, 600000,
                 900000, 1200000, 1500000, 1800000, 2100000, 2400000, 2700000, 3000000, 3300000, 3600000],
    "Mage":     [0, 2500, 5000, 10000, 20000, 40000, 60000, 90000, 135000, 250000,
                 375000, 750000, 1125000, 1500000, 1875000, 2250000, 2625000, 3000000, 3375000, 3750000],
    "Cleric":   [0, 1500, 3000, 6000, 13000, 27500, 55000, 110000, 225000, 450000,
                 675000, 900000, 1125000, 1350000, 1575000, 1800000, 2025000, 2250000, 2475000, 2700000],
    "Druid":    [0, 2000, 4000, 7500, 12500, 20000, 35000, 60000, 90000, 125000,
                 200000, 300000, 750000, 1500000, 3000000],  # 14 is the practical cap (hierophant beyond)
    "Thief":    [0, 1250, 2500, 5000, 10000, 20000, 40000, 70000, 110000, 160000,
                 220000, 440000, 660000, 880000, 1100000, 1320000, 1540000, 1760000, 1980000, 2200000],
}
# Classes that share another class's progression.
_XP["Paladin"] = _XP["Ranger"]
_XP["Bard"] = _XP["Thief"]
_XP["Illusionist"] = _XP["Mage"]
_XP["Specialist"] = _XP["Mage"]


@dataclass(frozen=True)
class CharClass:
    name: str
    group: str
    minimums: dict          # ability -> minimum score (Table 13)
    prime_requisites: tuple # 10%-XP-bonus abilities
    allowed_alignments: tuple = ()  # () = any
    optional: bool = False


CLASSES = {
    "Fighter":     CharClass("Fighter", "Warrior", {"Strength": 9}, ("Strength",)),
    "Paladin":     CharClass("Paladin", "Warrior",
                             {"Strength": 12, "Constitution": 9, "Wisdom": 13, "Charisma": 17},
                             ("Strength", "Charisma"), ("Lawful Good",), optional=True),
    "Ranger":      CharClass("Ranger", "Warrior",
                             {"Strength": 13, "Dexterity": 13, "Constitution": 14, "Wisdom": 14},
                             ("Strength", "Dexterity", "Wisdom"),
                             ("Lawful Good", "Neutral Good", "Chaotic Good"), optional=True),
    "Mage":        CharClass("Mage", "Wizard", {"Intelligence": 9}, ("Intelligence",)),
    "Illusionist": CharClass("Illusionist", "Wizard", {"Intelligence": 9, "Dexterity": 16},
                             ("Intelligence",), optional=True),
    "Cleric":      CharClass("Cleric", "Priest", {"Wisdom": 9}, ("Wisdom",)),
    "Druid":       CharClass("Druid", "Priest", {"Wisdom": 12, "Charisma": 15},
                             ("Wisdom", "Charisma"), ("True Neutral",), optional=True),
    "Thief":       CharClass("Thief", "Rogue", {"Dexterity": 9}, ("Dexterity",)),
    "Bard":        CharClass("Bard", "Rogue", {"Dexterity": 12, "Intelligence": 13, "Charisma": 15},
                             ("Dexterity", "Charisma"), optional=True),
}


def meets_class_minimums(class_name: str, abilities: dict) -> list:
    """(ability, minimum, value) tuples the character fails; empty means qualified."""
    fails = []
    for ability, minimum in CLASSES[class_name].minimums.items():
        val = abilities.get(ability)
        if val is not None and val < minimum:
            fails.append((ability, minimum, val))
    return fails


def xp_for_level(class_name: str, level: int) -> int:
    table = _XP[CLASSES[class_name].name if class_name in CLASSES else class_name]
    if not 1 <= level <= len(table):
        raise ValueError(f"{class_name} has no tabulated level {level}")
    return table[level - 1]


def level_for_xp(class_name: str, xp: int) -> int:
    table = _XP[class_name]
    level = 1
    for i, threshold in enumerate(table, 1):
        if xp >= threshold:
            level = i
    return level


# ── Hit points ────────────────────────────────────────────────────────────

def hit_die(class_name: str, house_rules: bool = True) -> int:
    """The HD size for a class, applying the Wizard-d6 / Rogue-d8 house rules."""
    group = CLASSES[class_name].group
    if house_rules and group in HOUSE_RULES.hit_die_override:
        return HOUSE_RULES.hit_die_override[group]
    return GROUPS[group].hit_die


def con_hp_bonus(class_name: str, con: int) -> int:
    """Per-HD Constitution HP bonus; warriors get the higher 17+/18+ values."""
    mods = constitution_mods(con)
    return mods.hp_adj_warrior if CLASSES[class_name].group == "Warrior" else mods.hp_adj


def max_hp_at_first_level(class_name: str, con: int, house_rules: bool = True) -> int:
    """Best-case level-1 HP: max on the hit die + the Con bonus (min 1)."""
    return max(1, hit_die(class_name, house_rules) + con_hp_bonus(class_name, con))


def hp_die_levels(class_name: str, level: int) -> int:
    """How many hit dice are rolled *after* 1st level, i.e. how many stored rolls
    `hp_at_level` needs. Levels 2..name_level roll a die; levels past the class's
    name level add flat HP instead."""
    name_level = GROUPS[CLASSES[class_name].group].name_level
    return max(0, min(level, name_level) - 1)


def hp_at_level(class_name: str, level: int, con: int, rolls=(),
                house_rules: bool = True) -> int:
    """Total HP at a class level.

    The campaign's model (see docs/leveling-plan.md): 1st level is **best case**
    (max hit die + Con bonus); each level from 2nd up to the class's *name level*
    adds a stored hit-die **roll** plus the per-HD Con bonus (a level always yields
    at least 1 hp); every level beyond the name level adds the group's flat
    `hp_after` with **no die and no Con bonus**.

    Con is applied at call time rather than baked into `rolls`, so a later
    Constitution change recomputes correctly. `rolls` must hold at least
    `hp_die_levels(class_name, level)` entries."""
    group = GROUPS[CLASSES[class_name].group]
    needed = hp_die_levels(class_name, level)
    rolls = list(rolls)
    if len(rolls) < needed:
        raise ValueError(
            f"{class_name} at level {level} needs {needed} hit-die roll(s), got {len(rolls)}")

    total = max_hp_at_first_level(class_name, con, house_rules)
    bonus = con_hp_bonus(class_name, con)
    for roll in rolls[:needed]:
        total += max(1, roll + bonus)          # a level never yields less than 1 hp
    total += max(0, level - group.name_level) * group.hp_after
    return max(1, total)


# ── Attacks per round (PHB Table 58: warriors only) ─────────────────────────
# Returned as (attacks, per_rounds): 1/1 -> 3/2 at 7th -> 2/1 at 13th. Only the
# Warrior group advances; everyone else attacks once per round. (Weapon
# specialisation grants further attacks — that's Combat & Tactics, not here.)

def attacks_per_round(class_name: str, level: int) -> tuple:
    """(attacks, rounds) for a class at a level, e.g. (3, 2) == three per two rounds."""
    if CLASSES[class_name].group != "Warrior":
        return (1, 1)
    if level >= 13:
        return (2, 1)
    if level >= 7:
        return (3, 2)
    return (1, 1)


# ── THAC0 / attack bonus ────────────────────────────────────────────────────

def _thac0_raw(group: str, level: int) -> int:
    """Table-53 THAC0 by group and level (standard rules), verified against the PHB."""
    if group == "Warrior":
        step = level - 1
    elif group == "Priest":
        step = 2 * ((level - 1) // 3)
    elif group == "Rogue":
        step = (level - 1) // 2
    elif group == "Wizard":
        step = (level - 1) // 3
    else:
        raise ValueError(group)
    return 20 - step


def thac0(class_name: str, level: int, house_rules: bool = True) -> int:
    """THAC0 for a class/level. House rule: rogues advance at the priest rate (⅔/level)."""
    group = CLASSES[class_name].group
    if house_rules and group == "Rogue" and HOUSE_RULES.rogue_attack_as_priest:
        group = "Priest"
    return _thac0_raw(group, level)


def attack_bonus(class_name: str, level: int, house_rules: bool = True) -> int:
    """House-rule attack bonus (20 − THAC0). With house_rules=False this is still
    the derived bonus but off the standard THAC0 progression."""
    return thac0_to_bonus(thac0(class_name, level, house_rules))


# ── Saving throws (PHB Table 60) ────────────────────────────────────────────

SAVE_CATEGORIES = ("Paralyzation/Poison/Death", "Rod/Staff/Wand",
                   "Petrification/Polymorph", "Breath Weapon", "Spell")

# Per group: (max_level_in_band, [five save numbers]).
_SAVES = {
    "Warrior": [(0, [16, 18, 17, 20, 19]), (2, [14, 16, 15, 17, 17]), (4, [13, 15, 14, 16, 16]),
                (6, [11, 13, 12, 13, 14]), (8, [10, 12, 11, 12, 13]), (10, [8, 10, 9, 9, 11]),
                (12, [7, 9, 8, 8, 10]), (14, [5, 7, 6, 5, 8]), (16, [4, 6, 5, 4, 7]),
                (999, [3, 5, 4, 4, 6])],
    "Priest":  [(3, [10, 14, 13, 16, 15]), (6, [9, 13, 12, 15, 14]), (9, [7, 11, 10, 13, 12]),
                (12, [6, 10, 9, 12, 11]), (15, [5, 9, 8, 11, 10]), (18, [4, 8, 7, 10, 9]),
                (999, [2, 6, 5, 8, 7])],
    "Rogue":   [(4, [13, 14, 12, 16, 15]), (8, [12, 12, 11, 15, 13]), (12, [11, 10, 10, 14, 11]),
                (16, [10, 8, 9, 13, 9]), (20, [9, 6, 8, 12, 7]), (999, [8, 4, 7, 11, 5])],
    "Wizard":  [(5, [14, 11, 13, 15, 12]), (10, [13, 9, 11, 13, 10]), (15, [11, 7, 9, 11, 8]),
                (20, [10, 5, 7, 9, 6]), (999, [8, 3, 5, 7, 4])],
}


def saving_throws(class_name: str, level: int) -> dict:
    """{category: target number} for a class at a level (roll d20, meet or beat)."""
    for max_lvl, values in _SAVES[CLASSES[class_name].group]:
        if level <= max_lvl:
            return dict(zip(SAVE_CATEGORIES, values))
    raise ValueError(f"no save band for level {level}")


def monster_saving_throws(hit_dice: int) -> dict:
    """{category: target number} for a monster of ``hit_dice`` HD — it saves as a
    Warrior of level = its Hit Dice (2e DMG). The single source of truth the Roll20
    monster export and the sheet read, so they can't disagree.

    A creature of *less than* one Hit Die (a rat at 1-1 HD, a stirge at 1 hp) saves
    as a level-0 warrior — the band _SAVES carries at index 0 — so 0 is a meaningful
    argument here, not a floor to clamp away."""
    hd = max(0, int(hit_dice))
    for max_lvl, values in _SAVES["Warrior"]:
        if hd <= max_lvl:
            return dict(zip(SAVE_CATEGORIES, values))
    return dict(zip(SAVE_CATEGORIES, _SAVES["Warrior"][-1][1]))


# ═══════════════════════════════════════════════════════════════════════════
#  Proficiencies (PHB Table 34 slots + an extensible nonweapon definition table)
# ═══════════════════════════════════════════════════════════════════════════

def weapon_slots(class_name: str, level: int) -> int:
    initial, per, _penalty = GROUPS[CLASSES[class_name].group].weapon_slots
    return initial + (level - 1) // per


def nonproficiency_penalty(class_name: str) -> int:
    return GROUPS[CLASSES[class_name].group].weapon_slots[2]


def nonweapon_slots(class_name: str, level: int, int_score: int = None,
                    house_rules: bool = True) -> int:
    """Initial + per-level nonweapon proficiency slots, plus (optional rule) the
    bonus slots granted by Intelligence."""
    initial, per = GROUPS[CLASSES[class_name].group].nonweapon_slots
    slots = initial + (level - 1) // per
    if int_score is not None:
        slots += intelligence_mods(int_score).languages  # language column = bonus slots
    return slots


@dataclass(frozen=True)
class Proficiency:
    """One nonweapon proficiency, loaded as data from a sourcebook.

    The campaign's full skill list lives in nonweapon_book.py (generated from the
    sheet + rules doc by build_nwp_book.py). Adding or editing a skill is a change
    to those source files and a regenerate — not new code here."""
    name: str
    ability: str            # relevant ability for the check; "" = no check (grants a special)
    modifier: int = 0       # check modifier applied to the ability score
    slots: int = 1          # slots required (may be 0)
    classes: tuple = ()     # class GROUPS that may take it; () = every class
    prereq: tuple = ()      # names of proficiencies that must be known first
    source: str = ""        # the sourcebook this skill is published in
    special: str = ""       # short non-check effect label (for the UI)
    description: str = ""    # full rules text


# The campaign's nonweapon-proficiency sourcebook (name/code) and its skills,
# loaded from the generated data module.
PROFICIENCY_BOOK = _book.BOOK_NAME
PROFICIENCY_BOOK_CODE = _book.BOOK_CODE

NONWEAPON_PROFICIENCIES = {
    e["name"]: Proficiency(
        name=e["name"], ability=e["ability"], modifier=e["modifier"],
        slots=e["slots"], classes=tuple(e["classes"]), prereq=tuple(e["prereq"]),
        source=PROFICIENCY_BOOK, special=e.get("special", ""),
        description=e.get("description", ""),
    )
    for e in _book.ENTRIES
}


def _as_prof(prof):
    return NONWEAPON_PROFICIENCIES[prof] if isinstance(prof, str) else prof


def proficiency_available(prof, class_name: str) -> bool:
    """Whether a class may take a proficiency. An empty `classes` means any class;
    otherwise the class's group (Warrior/Rogue/Wizard/Priest) must be listed."""
    p = _as_prof(prof)
    return not p.classes or CLASSES[class_name].group in p.classes


def proficiencies_for_class(class_name: str) -> list:
    """Every nonweapon proficiency the class may take, in book order."""
    return [p for p in NONWEAPON_PROFICIENCIES.values()
            if proficiency_available(p, class_name)]


def proficiency_prereqs_met(prof, known) -> bool:
    """Whether every prerequisite proficiency of `prof` is present in `known`
    (an iterable of proficiency names the character already has)."""
    return all(req in known for req in _as_prof(prof).prereq)


def proficiency_dependents(name: str, known) -> list:
    """Known proficiencies that list `name` as a prerequisite — the skills that
    would be stranded if `name` were removed."""
    return [n for n in known if n in NONWEAPON_PROFICIENCIES
            and name in NONWEAPON_PROFICIENCIES[n].prereq]


def proficiency_check_target(house_rules: bool = True):
    """Under the house rule the check is d20 + skill, needing 21 (return a target
    int). Standard 2e rolls d20 and must land at or under the score (returns None,
    meaning 'roll-under the ability score')."""
    return HOUSE_RULES.proficiency_check_target if house_rules else None


def proficiency_bonus_per_slot(house_rules: bool = True) -> int:
    """Extra slots spent on one proficiency: +2 each (house) vs. +1 each (standard)."""
    return HOUSE_RULES.proficiency_bonus_per_slot if house_rules else 1


def weapon_slot_cost(weapon: str, house_rules: bool = True) -> int:
    """Slots to become proficient with a weapon. House rules: crossbows are free,
    bows cost 2. Everything else costs 1."""
    if house_rules:
        return HOUSE_RULES.weapon_slot_cost.get(weapon.lower(), 1)
    return 1


# A representative set of common PHB weapons for the weapon-proficiency picker.
# Slot cost comes from weapon_slot_cost (so the house-rule crossbow/bow costs
# apply automatically). More weapons drop in as extra rows.
WEAPONS = (
    "Long Sword", "Short Sword", "Broad Sword", "Bastard Sword", "Two-Handed Sword",
    "Scimitar", "Dagger", "Mace", "Morning Star", "Warhammer", "Club", "Quarterstaff",
    "Flail", "Battle Axe", "Hand Axe", "Spear", "Halberd", "Trident", "Sling", "Dart",
    "Short Bow", "Long Bow", "Light Crossbow", "Heavy Crossbow",
)


# ═══════════════════════════════════════════════════════════════════════════
#  Combat & Tactics — weapon groups and barred-weapon access (CT Chapters 4 & 7)
#
#  Phase 0 of docs/combat-tactics-chargen-plan.md: pure reference data. Nothing
#  consumes it yet; the rung/proficiency engine lands on top of it.
#
#  CT sorts weapons into *tight* groups nested under *broad* groups
#  (CT/DD02744). Only the tight groups are mechanically load-bearing: they drive
#  **familiarity** (proficiency in one weapon of a tight group gives familiarity
#  with the rest) and the 2-slot **weapon group proficiency**. Broad groups are
#  informational.
#
#  Two subtleties that make this NOT a simple weapon->group dict:
#   • A weapon belongs to SEVERAL tight groups — a short sword is Ancient,
#     Middle Eastern *and* Short. Familiarity is the union over your weapons.
#   • CT's "Unrelated:" lines are NOT a group. Those weapons (and any weapon
#     absent from the listing) belong to *no* group: "If a weapon does not appear
#     in the preceding listings, it belongs to no weapon group."
#     For our roster that means Trident (listed Unrelated), plus Quarterstaff and
#     Sling (absent entirely) — no familiarity, no group proficiency.
# ═══════════════════════════════════════════════════════════════════════════

TIGHT_TO_BROAD = {
    "Axes":             "Axes, Picks, and Hammers",
    "Hammers":          "Axes, Picks, and Hammers",
    "Bows":             "Bows",
    "Maces":            "Clubs, Maces, and Flails",
    "Clubs":            "Clubs, Maces, and Flails",
    "Flails":           "Clubs, Maces, and Flails",
    "Crossbows":        "Crossbows",
    "Daggers & Knives": "Daggers & Knives",
    "Poleaxes":         "Polearms",
    "Spears":           "Spears & Javelins",
    "Javelins":         "Spears & Javelins",
    "Ancient":          "Swords",
    "Roman":            "Swords",
    "Middle Eastern":   "Swords",
    "Short":            "Swords",
    "Medium":           "Swords",
    "Large":            "Swords",
}

# Our roster mapped onto CT's tight groups. Transcribed from CT/DD02744; the
# generic entries (Mace, Flail, Club, Spear) stand in for the book's named
# variants (footman's/horseman's mace, etc.). () means "no weapon group".
WEAPON_TIGHT_GROUPS = {
    "Long Sword":       ("Medium",),
    "Short Sword":      ("Ancient", "Middle Eastern", "Short"),
    "Broad Sword":      ("Ancient", "Roman", "Medium"),      # CT spells it "broadsword"
    "Bastard Sword":    ("Large",),
    "Two-Handed Sword": ("Large",),
    "Scimitar":         ("Middle Eastern",),
    "Dagger":           ("Daggers & Knives", "Short"),
    "Mace":             ("Maces",),
    "Morning Star":     ("Clubs",),                          # CT files it under Clubs
    "Warhammer":        ("Hammers",),
    "Club":             ("Clubs",),
    "Quarterstaff":     (),                                  # absent from CT's listing
    "Flail":            ("Flails",),
    "Battle Axe":       ("Axes",),
    "Hand Axe":         ("Axes",),                           # CT: "hand/throwing axe"
    "Spear":            ("Spears",),
    "Halberd":          ("Poleaxes",),
    "Trident":          (),                                  # CT lists it as "Unrelated"
    "Sling":            (),                                  # absent from CT's listing
    "Dart":             ("Javelins",),
    "Short Bow":        ("Bows",),
    "Long Bow":         ("Bows",),
    "Light Crossbow":   ("Crossbows",),
    "Heavy Crossbow":   ("Crossbows",),
}


# What each Combat & Tactics option actually *does* at the table, plus the page to
# read for the full rule. Hand-written summaries rather than the rulebook's prose:
# the book spends most of its words on who may pummel and how ambushes feel, and
# buries the mechanics that decide a character sheet.
#
# `(page, summary)`. Keep summaries to the numbers a player needs mid-fight.
CT_RULES = {
    # ── Fighting styles (the effect of *specialising*) ───────────────────────
    "Weapon and Shield": ("CT/DD02646.htm",
        "Using a shield offensively (rush, punch, block, trap) normally forfeits its "
        "AC bonus for the round. Specialised: make one such attack every round and "
        "keep the shield's AC."),
    "One-Handed Weapon": ("CT/DD02647.htm",
        "Your empty hand always counts as a secondary weapon, at the usual two-weapon "
        "penalties. Specialised: +1 AC while wielding a one-handed weapon with no "
        "shield and no off-hand weapon. A second slot raises that to +2 AC."),
    "Two-Handed Weapon": ("CT/DD02648.htm",
        "You may wield a weapon one size larger than yourself in two hands. "
        "Specialised: your two-handed weapon's speed improves by one category "
        "(slow to average, average to fast) — or its speed factor drops by 3 under "
        "the old initiative rules."),
    "Two-Weapon": ("CT/DD02649.htm",
        "A weapon in each hand normally costs -2 to hit with the primary and -4 with "
        "the off-hand. Specialised: 0 and -2. Ambidextrous and specialised: no "
        "penalty with either. The off-hand weapon must be one size smaller, though "
        "knives and daggers always qualify; a second slot allows two weapons of equal "
        "size."),
    "Missile or Thrown Weapon": ("CT/DD02650.htm",
        "Specialised: move up to half your rate and still shoot at your full rate of "
        "fire, or take a full move and shoot at half rate. You also gain +1 AC against "
        "enemy missile fire while shooting."),

    # ── Unarmed disciplines ─────────────────────────────────────────────────
    "Pummeling": ("CT/DD02672.htm",
        "Punches, elbows and the like. Everyone gets one pummeling attack a round for "
        "free. Proficiency gives a warrior his full melee attack rate when pummeling; "
        "nonwarriors gain nothing from it. Expertise raises the rate further, and only "
        "single-class fighters may specialise or master it."),
    "Wrestling": ("CT/DD02679.htm",
        "Grabs, holds and locks. Everyone gets one wrestling attack a round for free. "
        "Proficiency gives a warrior his full melee attack rate when wrestling; "
        "nonwarriors gain nothing. The nonproficient can neither score critical hits "
        "nor achieve holds or locks."),
    "Overbearing": ("CT/DD02689.htm",
        "Overpowering a foe by brute strength or weight of numbers. Everyone is "
        "familiar with it and it can never be advanced — there is no overbearing "
        "expertise, specialisation or mastery. Multi-legged creatures are hard to "
        "overbear; legless ones nearly impossible."),
    "Martial Arts: Style A": ("CT/DD02701.htm",
        "Hands and fists. Your bare or gloved hands count as small hard objects (1d3) "
        "and can damage a creature of any size. Unarmed and unarmoured, you gain an "
        "extra attack each round with your free hand, without the two-weapon penalties."),
    "Martial Arts: Style B": ("CT/DD02701.htm",
        "Feet. Your bare or shod feet count as large hard objects (1d6) and can kick an "
        "opponent who is standing. Unarmed and unarmoured, you gain an extra attack each "
        "round with a free hand. Does not grant Style A's any-size damage."),
    "Martial Arts: Style C": ("CT/DD02701.htm",
        "Throws and escapes. You may take the pull/trip option on a pummeling attack, "
        "using Strength or Dexterity for the opposed roll, and may make an opposed "
        "roll to escape any hold, grapple, lock or pin — it costs an attack, but on a "
        "success you are free and finish the round normally."),
    "Martial Arts: Style D": ("CT/DD02701.htm",
        "Dodges and blocks. One free block each round on top of your attacks, and "
        "+2 AC while unarmed and unarmoured."),

    # ── Special talents ─────────────────────────────────────────────────────
    "Alertness": ("CT/DD02654.htm",
        "On a successful check, your chance of being surprised drops by 1 in 10. Where "
        "surprise would be automatic, a successful check means you are surprised only "
        "at the normal chance instead."),
    "Ambidexterity": ("CT/DD02655.htm",
        "You have no off-hand. Fighting two-weapon style, both hands count as primary: "
        "-2 to hit with either. Add two-weapon style specialisation and you suffer no "
        "penalty at all."),
    "Ambush": ("CT/DD02656.htm",
        "You can lay an ambush where the terrain would not normally allow one. Useless "
        "once the enemy has already spotted you."),
    "Camouflage": ("CT/DD02657.htm",
        "Conceal yourself in natural surroundings. Unlike hiding in shadows it needs "
        "either good cover nearby or time to prepare — with preparation you can hide on "
        "open ground."),
    "Dirty Fighting": ("CT/DD02658.htm",
        "Once per fight a feint or dirty trick grants +1 on your next attack roll, or +2 "
        "if the enemy has reason to expect you to fight honourably. Any given enemy only "
        "falls for it once."),
    "Endurance": ("CT/DD02659.htm",
        "Sustain strenuous activity twice as long as normal before fatigue sets in. "
        "Under the Chapter One fatigue rules, your fatigue points rise by 50%."),
    "Fine Balance": ("CT/DD02660.htm",
        "On a successful check, +2 on climbing checks, saving throws and ability checks "
        "to avoid slipping or falling, and penalties for fighting off-balance or in "
        "awkward footing are reduced by 2."),
    "Iron Will": ("CT/DD02661.htm",
        "+1 on saving throws against mind-affecting magic — charm, hold, hypnotism, "
        "fascination, suggestion and the like — and you can keep fighting past the point "
        "that would stop another character."),
    "Leadership": ("CT/DD02662.htm",
        "Troops you lead gain +2 on morale checks. Under the Chapter Eight mass-combat "
        "rules you command as though you were three levels higher."),
    "Quickness": ("CT/DD02663.htm",
        "On a successful check, -2 on your initiative roll when you move or attack with a "
        "weapon of average speed or faster. It never applies to slow weapons."),
    "Steady Hand": ("CT/DD02664.htm",
        "With bows and crossbows: take a full round to aim (holding your action until "
        "last) and you suffer no penalty at medium range, and only -2 at long range."),
    "Trouble Sense": ("CT/DD02665.htm",
        "The DM rolls in secret whenever an unnoticed danger threatens you. On a success "
        "a sneak attack surprises you only on a 1, and rear attacks count as flank "
        "attacks instead."),

    # ── Martial arts talents (each needs a martial arts style) ───────────────
    "Flying Kick": ("CT/DD02705.htm",
        "Leap and kick a target up to three squares away, landing adjacent to it. "
        "Without Style B it is your only attack that round and deals 2d4; with Style B it "
        "replaces one kick and deals 2d6. Strength bonuses apply."),
    "Backward Kick": ("CT/DD02705.htm",
        "Attack an opponent standing in one of your rear squares without provoking an "
        "attack of opportunity. Works best with Style B."),
    "Spring": ("CT/DD02705.htm",
        "For the cost of a half move or an attack, leap five feet up and land up to two "
        "squares away in any direction, facing wherever you like. A two-square running "
        "start doubles the distance."),
    "Crushing Blow": ("CT/DD02705.htm",
        "Break hard objects barehanded — or with the feet, using Style B — up to half an "
        "inch of board or a quarter inch of stone per level. Exceptionally strong or "
        "supported objects get a saving throw."),
    "Instant Stand": ("CT/DD02705.htm",
        "On a successful check you regain your feet instantly, ignoring a knockdown or a "
        "failed spring. On a failure you rise on your next action but can do nothing more "
        "that round. Useless while pinned, locked, held or grappled."),
    "Missile Deflection": ("CT/DD02705.htm",
        "Block normal missiles — arrows, bolts, javelins, spears, thrown axes, small "
        "stones — fired at you from the front. You may spend your free facing change to "
        "turn toward a shooter on your flank or rear."),

    # ── Siege proficiencies (nonweapon slots) ───────────────────────────────
    "Artillerist": ("CT/DD02824.htm",
        "Direct the siting and operation of bombardment engines. You can control up to "
        "one third of your Charisma score in engines, so long as they stand no farther "
        "apart than you can sprint in a single round."),
    "Vehicle Handling": ("CT/DD02824.htm",
        "Control a wagon or chariot under difficult circumstances: roll against this "
        "proficiency whenever a driving check is called for."),
}


def ct_summary(name: str) -> str:
    """What this style / discipline / talent does at the table; '' if unknown."""
    entry = CT_RULES.get(name)
    return entry[1] if entry else ""


def ct_page(name: str) -> str:
    """The rulebook page with the full rule; '' if unknown."""
    entry = CT_RULES.get(name)
    return entry[0] if entry else ""


# CT: "Weapon group proficiencies cost two slots, but may include a number of
# weapons." One tight group, every weapon in it.
WEAPON_GROUP_SLOT_COST = 2


def weapon_tight_groups(weapon: str) -> tuple:
    """The tight groups a weapon belongs to; () when it belongs to none."""
    return WEAPON_TIGHT_GROUPS.get(weapon, ())


def tight_groups_with_members() -> tuple:
    """Every tight group that has at least one weapon on our roster, alphabetical."""
    return tuple(sorted(g for g in TIGHT_TO_BROAD if weapon_group_members(g)))


def weapon_broad_groups(weapon: str) -> tuple:
    """The distinct broad groups a weapon's tight groups sit under."""
    seen = []
    for tight in weapon_tight_groups(weapon):
        broad = TIGHT_TO_BROAD.get(tight)
        if broad and broad not in seen:
            seen.append(broad)
    return tuple(seen)


def weapon_group_members(tight_group: str) -> tuple:
    """Every weapon on our roster belonging to a tight group, in WEAPONS order."""
    return tuple(w for w in WEAPONS if tight_group in weapon_tight_groups(w))


def is_familiar(weapon: str, proficient_weapons) -> bool:
    """CT familiarity: the weapon shares a tight group with something you're already
    proficient in (and you aren't already proficient in it). Group-less weapons —
    Trident, Quarterstaff, Sling — can never be familiar."""
    proficient = set(proficient_weapons)
    if weapon in proficient:
        return False
    groups = set(weapon_tight_groups(weapon))
    if not groups:
        return False
    return any(groups & set(weapon_tight_groups(w)) for w in proficient)


# ── Barred weapons (CT/DD02624) ──────────────────────────────────────────────
# CT prices a weapon by the *least restrictive* class group that may wield it,
# then charges extra slots when you reach above your station:
#   rogue/priest taking a warrior-only weapon           -> +1 slot
#   wizard taking a priest/rogue weapon                 -> +1 slot
#   wizard taking a warrior-only weapon                 -> +2 slots
# Validated against CT's own worked example: a wizard pays 2 slots total for a
# long sword (rogue-tier) and 3 for a two-handed sword (warrior-only).
#
# NOTE: this is CT's coarse three-tier model. It deliberately does NOT capture the
# finer per-class PHB restrictions (e.g. clerics being limited to bludgeoning
# weapons) — those stay DM-adjudicated, exactly as CT leaves them.
WEAPON_ACCESS = {
    # wizard-tier: the weapons a mage may natively wield
    "Dagger": "wizard", "Dart": "wizard", "Quarterstaff": "wizard", "Sling": "wizard",
    # priest/rogue-tier
    "Club": "priest_rogue", "Mace": "priest_rogue", "Warhammer": "priest_rogue",
    "Flail": "priest_rogue", "Morning Star": "priest_rogue", "Scimitar": "priest_rogue",
    "Spear": "priest_rogue", "Short Sword": "priest_rogue", "Long Sword": "priest_rogue",
    "Broad Sword": "priest_rogue", "Short Bow": "priest_rogue",
    "Light Crossbow": "priest_rogue",
    # warrior-only
    "Bastard Sword": "warrior", "Two-Handed Sword": "warrior", "Battle Axe": "warrior",
    "Hand Axe": "warrior", "Halberd": "warrior", "Trident": "warrior",
    "Long Bow": "warrior", "Heavy Crossbow": "warrior",
}

_ACCESS_RANK = {"wizard": 0, "priest_rogue": 1, "warrior": 2}
_GROUP_RANK = {"Wizard": 0, "Priest": 1, "Rogue": 1, "Warrior": 2}


def barred_weapon_penalty(weapon: str, class_name: str) -> int:
    """Extra proficiency slots to learn a weapon barred to your class group (0/1/2).
    Zero before a class is chosen — nothing is barred to nobody."""
    if class_name not in CLASSES:
        return 0
    group = CLASSES[class_name].group
    weapon_rank = _ACCESS_RANK[WEAPON_ACCESS.get(weapon, "warrior")]
    return max(0, weapon_rank - _GROUP_RANK[group])


# ── The weapon mastery ladder (CT Ch4, CT/DD02629-DD02644) ───────────────────
#
# The ladder is NOT linear. Expertise and specialisation both cost two slots and
# sit at the same rung: expertise is the non-fighter's version (paladins, rangers
# and multi-classed fighters), specialisation the single-class fighter's. Mastery
# builds on specialisation, so only a single-class fighter ever climbs past it.
#
# `nonproficient` and `familiar` cost nothing and are never *bought* — familiarity
# falls out of the tight weapon groups (see is_familiar), so neither appears in a
# class's ladder.
#
# Level gates come from CT's own worked example: master at 5th, high master at 6th
# ("has spent four slots ... and is at least 6th level"), and the third mastery
# slot — grand mastery — no earlier than 9th.
_RUNG_MIN_LEVEL = {"master": 5, "high_master": 6, "grand_master": 9}

# Slots spent *beyond* the proficiency slot. Proficiency itself costs
# weapon_slot_cost() (house rules apply) plus any barred-weapon penalty.
_RUNG_EXTRA_SLOTS = {
    "proficient": 0, "expert": 1, "specialist": 1,
    "master": 2, "high_master": 3, "grand_master": 4,
}

RUNG_LABELS = {
    "nonproficient": "Nonproficient", "familiar": "Familiar", "proficient": "Proficient",
    "expert": "Expert", "specialist": "Specialist", "master": "Master",
    "high_master": "High Master", "grand_master": "Grand Master",
}

# What each rung of the mastery ladder actually grants in play, as (page, summary):
# a hand-written mechanical précis (the parts that touch a roll) plus the Combat &
# Tactics page for the full rule. Rungs the character doesn't buy (nonproficient,
# familiar) and plain proficiency have no entry. Mirrors CT_RULES for talents/styles.
RUNG_EFFECTS = {
    "expert": ("CT/DD02633.htm",
        "Attacks as often as a specialist would — three attacks every two rounds at "
        "low level, rising with level — and may use any weapon trick reserved for "
        "specialists, but gains no bonus to hit or damage. This is the only mastery "
        "path open to paladins and rangers."),
    "specialist": ("CT/DD02634.htm",
        "With a melee weapon: +1 to attack rolls, +2 to damage, and an extra attack "
        "every two rounds (three attacks per two rounds at 1st level). With a missile "
        "weapon: a faster rate of fire and +1 to attack. A single-class fighter may "
        "specialise in only one weapon at a time."),
    "master": ("CT/DD02641.htm",
        "The melee attack and damage bonuses rise to +3 and +3. With a bow or "
        "crossbow, the point-blank bonus rises to +3/+3 and every other range band "
        "gains +1 to hit (a total of +2 before range penalties)."),
    "high_master": ("CT/DD02642.htm",
        "The weapon's speed factor improves by one category (a slow weapon becomes "
        "average). Critical hits land on a natural 16+ instead of 18+ (when the "
        "optional crit rule is used) that still beats the target's AC by 5 or more. "
        "Missile weapons gain a new 'extreme range' band, one-third past long range."),
    "grand_master": ("CT/DD02643.htm",
        "One extra attack per round on top of the specialist's rate for your level. "
        "The weapon's damage die and knockdown die each step up to the next larger "
        "size — a long sword deals 1d10 — applied to every damage die it rolls."),
}


def rung_summary(rung: str) -> str:
    """The gameplay effects of a mastery rung, or '' for rungs with no write-up."""
    entry = RUNG_EFFECTS.get(rung)
    return entry[1] if entry else ""


def rung_page(rung: str):
    """The Combat & Tactics page for a rung's full rule, or None."""
    entry = RUNG_EFFECTS.get(rung)
    return entry[0] if entry else None


def weapon_rung_ladder(class_name: str, level: int = 1) -> tuple:
    """The rungs this class can climb, in order, at this level.

    Single-class fighters specialise and go on to mastery; paladins and rangers
    take expertise instead and stop there; everyone else stops at proficiency."""
    if class_name == "Fighter":
        ladder = ["proficient", "specialist"]
        for rung in ("master", "high_master", "grand_master"):
            if level >= _RUNG_MIN_LEVEL[rung]:
                ladder.append(rung)
        return tuple(ladder)
    if class_name in ("Paladin", "Ranger"):
        return ("proficient", "expert")
    return ("proficient",)


def max_weapon_rung(class_name: str, level: int = 1) -> str:
    return weapon_rung_ladder(class_name, level)[-1]


def next_weapon_rung(rung: str, class_name: str, level: int = 1):
    """The rung above `rung` on this class's ladder, or None at the top."""
    ladder = weapon_rung_ladder(class_name, level)
    if rung not in ladder:
        return None
    i = ladder.index(rung)
    return ladder[i + 1] if i + 1 < len(ladder) else None


def prev_weapon_rung(rung: str, class_name: str, level: int = 1):
    """The rung below `rung`, or None when `rung` is merely proficient."""
    ladder = weapon_rung_ladder(class_name, level)
    if rung not in ladder:
        return None
    i = ladder.index(rung)
    return ladder[i - 1] if i > 0 else None


def respecialisation_surcharge(changes: int) -> int:
    """Extra slots on top of a normal specialisation, by how many times the fighter
    has already moved it. CT: the first specialisation costs one extra slot, "if she
    wishes to change her specialization to a different weapon, she must spend two
    extra proficiency slots... Any more changes cost three slots each." So the
    surcharge is 0, then 1, then 2 forever."""
    if changes <= 0:
        return 0
    return 1 if changes == 1 else 2


def weapon_prof_cost(weapon: str, rung: str, class_name: str,
                     house_rules: bool = True, respecialisations: int = 0) -> int:
    """Total slots invested in a weapon to sit at `rung`: the proficiency slot
    (house-rule cost + barred-weapon penalty) plus the extra slots the rung needs,
    plus the re-specialisation surcharge once the fighter has moved his
    specialisation off an earlier weapon."""
    base = weapon_slot_cost(weapon, house_rules) + barred_weapon_penalty(weapon, class_name)
    extra = _RUNG_EXTRA_SLOTS[rung]
    if specialises(rung):
        extra += respecialisation_surcharge(respecialisations)
    return base + extra


def specialises(rung: str) -> bool:
    """Rungs that count as 'specialised in this weapon' — a single-class fighter may
    hold only one at a time (CT: 'A fighter may only specialize in one weapon')."""
    return rung in ("specialist", "master", "high_master", "grand_master")


# ── Fighting styles (CT Ch2 list, Ch4 specialisation: DD02645-DD02650) ───────
# "Warriors automatically know every style, while the other character types are
# limited... If a nonwarrior wishes to learn a style he doesn't know, he can do so
# at the cost of a weapon proficiency. In addition to simply knowing a style,
# warriors, priests, and rogues can specialize... by spending a weapon proficiency
# slot." Warriors may specialise in as many styles as they like; priests and rogues
# in only one. Wizards may learn a style but never specialise in it.
FIGHTING_STYLES = (
    "Weapon and Shield",
    "One-Handed Weapon",
    "Two-Handed Weapon",
    "Two-Weapon",
    "Missile or Thrown Weapon",
)
STYLE_LEARN_SLOT_COST = 1
STYLE_SPECIALISE_SLOT_COST = 1
# Two styles take a second slot of specialisation: two-weapon (it then allows two
# weapons of equal size) and one-handed weapon ("By spending an additional
# proficiency slot, the character can increase his AC bonus to +2, but that's the
# maximum benefit"). The rest cap at one.
_MAX_STYLE_SPECIALISATION = {"Two-Weapon": 2, "One-Handed Weapon": 2}


def knows_styles_free(class_name: str) -> bool:
    """Warriors automatically know every fighting style."""
    return class_name in CLASSES and CLASSES[class_name].group == "Warrior"


def can_specialise_styles(class_name: str) -> bool:
    """Warriors, priests and rogues may specialise in a style; wizards may not."""
    return class_name in CLASSES and CLASSES[class_name].group in ("Warrior", "Priest", "Rogue")


def max_style_specialisation(style: str) -> int:
    return _MAX_STYLE_SPECIALISATION.get(style, 1)


def style_free_specialisation(style: str, class_name: str) -> int:
    """Specialisation slots granted free. CT: 'Rangers are considered to have the
    first slot of this style specialization' in two-weapon style."""
    return 1 if (class_name == "Ranger" and style == "Two-Weapon") else 0


def style_slot_cost(style: str, spec_slots: int, class_name: str) -> int:
    """Weapon slots a style costs: learning it (free for warriors) plus each slot of
    specialisation beyond any granted free."""
    cost = 0 if knows_styles_free(class_name) else STYLE_LEARN_SLOT_COST
    paid = max(0, spec_slots - style_free_specialisation(style, class_name))
    return cost + paid * STYLE_SPECIALISE_SLOT_COST


# ── Unarmed disciplines (CT Ch5: DD02674, DD02687, DD02695, DD02700-DD02703) ─
#
# These are bought with weapon proficiency slots and ride the SAME rung ladder, so
# they model as pseudo-weapons. Two things stop them being ordinary weapons:
#   • each has its own rung cap — overbearing cannot be advanced at all
#     ("It is not possible to develop overbearing expertise, specialization, or
#     mastery"), martial arts stop at specialist, pummeling/wrestling reach master;
#   • familiarity doesn't work the same. Everyone is *familiar* with pummeling,
#     wrestling and overbearing for free, while for martial arts "familiarity has no
#     effect" — and CT is explicit that "the four martial arts styles do not
#     constitute a weapon group", so they confer no familiarity on each other.
#
# Brawling is universal and has no skill levels, so there is nothing to model.
# Unlike weapons, *expertise* here is open to any class; only specialisation and
# mastery are the single-class fighter's.

@dataclass(frozen=True)
class UnarmedDiscipline:
    name: str
    rung_cap: str = None        # None: cannot be advanced at all
    free_rung: str = "familiar" # what you get without spending anything
    nonwarrior_benefit: bool = True
    note: str = ""


UNARMED_DISCIPLINES = {d.name: d for d in (
    UnarmedDiscipline("Overbearing", None, "familiar",
                      note="Brute force; no expertise, specialisation or mastery."),
    UnarmedDiscipline("Pummeling", "master", "familiar", nonwarrior_benefit=False,
                      note="Nonwarriors gain no benefit from proficiency."),
    UnarmedDiscipline("Wrestling", "master", "familiar", nonwarrior_benefit=False,
                      note="Nonwarriors gain no benefit from proficiency."),
    UnarmedDiscipline("Martial Arts: Style A", "specialist", "nonproficient",
                      note="Strikes with hands/fists; 1d3, any size opponent."),
    UnarmedDiscipline("Martial Arts: Style B", "specialist", "nonproficient",
                      note="Strikes with the feet; 1d6 kicks."),
    UnarmedDiscipline("Martial Arts: Style C", "specialist", "nonproficient"),
    UnarmedDiscipline("Martial Arts: Style D", "specialist", "nonproficient"),
)}

MARTIAL_ARTS_STYLES = tuple(n for n in UNARMED_DISCIPLINES if n.startswith("Martial Arts"))

# Unarmed skill levels, in order. Expertise is open to everyone here.
_UNARMED_LADDER = ("proficient", "expert", "specialist", "master")


def is_martial_art(discipline: str) -> bool:
    return discipline in MARTIAL_ARTS_STYLES


def unarmed_rung_ladder(discipline: str, class_name: str, level: int = 1) -> tuple:
    """The rungs a class can climb in an unarmed discipline at this level."""
    entry = UNARMED_DISCIPLINES.get(discipline)
    if entry is None or entry.rung_cap is None or class_name not in CLASSES:
        return ()
    ladder = []
    for rung in _UNARMED_LADDER:
        if rung == "specialist" and class_name != "Fighter":
            break
        if rung == "master" and (class_name != "Fighter"
                                 or level < _RUNG_MIN_LEVEL["master"]):
            break
        ladder.append(rung)
        if rung == entry.rung_cap:
            break
    return tuple(ladder)


def unarmed_prof_cost(rung: str) -> int:
    """Slots invested in an unarmed discipline at a rung: proficiency 1, expertise or
    specialisation 2, mastery 3 — the same ladder as weapons, with no house-rule or
    barred-weapon adjustment to the base slot."""
    return 1 + _RUNG_EXTRA_SLOTS[rung]


def unarmed_free_rung(discipline: str) -> str:
    entry = UNARMED_DISCIPLINES.get(discipline)
    return entry.free_rung if entry else "nonproficient"


# ── Special talents (CT/DD02653-DD02665) ────────────────────────────────────
# Bought with weapon proficiency slots. CT marks two of them with an asterisk —
# "originally presented as nonweapon proficiencies ... they can be purchased with
# either type of proficiency slot" — Alertness and Endurance.
# `groups` are the class groups allowed to take it; () means anyone ("All"/"General").

@dataclass(frozen=True)
class SpecialTalent:
    """A Combat & Tactics talent.

    `ability` + `modifier` is the **PHB** proficiency check this campaign uses:
    d20 ≤ ability + modifier (Iron Will is Wis−2, Alertness Wis+1, Leadership Cha−1).

    `initial_rating` is the *same check* written for **Skills & Powers**, where the
    score starts at a flat 3–8 rating and the ability only nudges it via S&P's ±5
    Table 44. CT prints both notations on one line because it supports both systems.
    The campaign plays PHB proficiency slots, not S&P character points, so the rating
    is kept for fidelity and never used — under S&P an Int-15 Ambush would succeed
    35% of the time where the PHB check succeeds 75%.

    Note the campaign's +2-per-extra-slot bonus never applies here: a talent is a
    single purchase, so its check is simply the ability plus the book's modifier.
    """
    name: str
    slots: int
    ability: str = None
    modifier: int = 0
    groups: tuple = ()
    initial_rating: int = None      # Skills & Powers only — see the class docstring
    # Which budget may pay: "weapon", "nonweapon", or "either" (CT's asterisk).
    slot_source: str = "weapon"
    requires_martial_art: bool = False


SPECIAL_TALENTS = {t.name: t for t in (
    SpecialTalent("Alertness", 1, "Wisdom", 1, (), None, slot_source="either"),
    SpecialTalent("Ambidexterity", 1, "Dexterity", 0, ("Warrior", "Rogue")),
    SpecialTalent("Ambush", 1, "Intelligence", 0, ("Warrior", "Rogue"), 5),
    SpecialTalent("Camouflage", 1, "Intelligence", 0, ("Warrior", "Rogue"), 5),
    SpecialTalent("Dirty Fighting", 1, "Intelligence", 0, ("Warrior", "Rogue"), 5),
    SpecialTalent("Endurance", 2, "Constitution", 0, ("Warrior",), 3, slot_source="either"),
    SpecialTalent("Fine Balance", 2, "Dexterity", 0, ("Warrior", "Rogue"), 7),
    SpecialTalent("Iron Will", 2, "Wisdom", -2, ("Warrior", "Priest"), 3),
    SpecialTalent("Leadership", 1, "Charisma", -1, ("Warrior",), 5),
    SpecialTalent("Quickness", 2, "Dexterity", 0, ("Warrior", "Rogue"), 3),
    SpecialTalent("Steady Hand", 1, "Dexterity", 0, ("Warrior", "Rogue")),
    SpecialTalent("Trouble Sense", 1, "Wisdom", 0, (), 3),
)}

# CT/DD02705. "Only a martial artist can learn the skills presented here. They can
# be purchased with either weapon or nonweapon proficiency slots."
_WPR = ("Warrior", "Priest", "Rogue")
MARTIAL_ARTS_TALENTS = {t.name: t for t in (
    SpecialTalent("Flying Kick", 1, "Strength", 0, ("Warrior",), 5,
                  slot_source="either", requires_martial_art=True),
    SpecialTalent("Backward Kick", 1, None, 0, _WPR, None,
                  slot_source="either", requires_martial_art=True),
    SpecialTalent("Spring", 1, "Dexterity", 0, ("Warrior", "Rogue"), 5,
                  slot_source="either", requires_martial_art=True),
    SpecialTalent("Crushing Blow", 1, None, 0, _WPR, None,
                  slot_source="either", requires_martial_art=True),
    SpecialTalent("Instant Stand", 1, "Dexterity", 0, _WPR, None,
                  slot_source="either", requires_martial_art=True),
    SpecialTalent("Missile Deflection", 1, None, 0, _WPR, None,
                  slot_source="either", requires_martial_art=True),
)}

# CT/DD02824 (Chapter Eight). "The following proficiencies are applicable to warfare
# and the operation of war equipment. They are acquired the same way standard PHB
# proficiencies are" — i.e. with nonweapon slots.
SIEGE_PROFICIENCIES = {t.name: t for t in (
    SpecialTalent("Artillerist", 1, "Charisma", 0, ("Warrior",), None,
                  slot_source="nonweapon"),
    SpecialTalent("Vehicle Handling", 1, "Dexterity", 0, ("Warrior",), None,
                  slot_source="nonweapon"),
)}

# Everything buyable through the talent machinery, in one lookup.
TALENTS = {**SPECIAL_TALENTS, **MARTIAL_ARTS_TALENTS, **SIEGE_PROFICIENCIES}


def talent_allowed(name: str, class_name: str) -> bool:
    """Whether a class group may take this talent at all (ignores prerequisites)."""
    talent = TALENTS.get(name)
    if talent is None or class_name not in CLASSES:
        return False
    return not talent.groups or CLASSES[class_name].group in talent.groups


def talents_for_class(class_name: str) -> tuple:
    """The twelve Chapter Four special talents open to a class."""
    return tuple(t for t in SPECIAL_TALENTS.values() if talent_allowed(t.name, class_name))


def martial_arts_talents_for_class(class_name: str) -> tuple:
    return tuple(t for t in MARTIAL_ARTS_TALENTS.values() if talent_allowed(t.name, class_name))


def siege_proficiencies_for_class(class_name: str) -> tuple:
    return tuple(t for t in SIEGE_PROFICIENCIES.values() if talent_allowed(t.name, class_name))


def two_weapon_penalty(specialised: bool, ambidextrous: bool) -> tuple:
    """(primary, off-hand) attack penalties when fighting with a weapon in each hand.

    Normally −2/−4. Specialising in two-weapon style reduces that to 0/−2. An
    ambidextrous character has two 'primary' hands (−2 with either), and one who is
    *both* ambidextrous and specialised suffers no penalty at all."""
    if ambidextrous and specialised:
        return (0, 0)
    if specialised:
        return (0, -2)
    if ambidextrous:
        return (-2, -2)
    return (-2, -4)


# ── Shield proficiency (CT/DD02627) ──────────────────────────────────────────
# 1 weapon slot. `attackers` is how many attacks the shield's bonus may apply to
# in a round. Body shields list (melee, missile) bonuses.
SHIELD_PROFICIENCY = {
    "buckler": {"normal_ac": 1, "proficient_ac": 1, "attackers": 1},
    "small":   {"normal_ac": 1, "proficient_ac": 2, "attackers": 2},
    "medium":  {"normal_ac": 1, "proficient_ac": 3, "attackers": 3},
    "body":    {"normal_ac": (1, 2), "proficient_ac": (3, 4), "attackers": 4},
}

# Our homebrew shields mapped onto CT's four types (DM ruling: the aspis, a large
# round hoplite shield at +2 AC, is a CT "medium" shield).
SHIELD_TYPES = {
    "Shield, Buckler": "buckler",
    "Shield, Aspis":   "medium",
}

# Shield proficiency and armor proficiency each cost one weapon slot (CT/DD02627-8).
SHIELD_PROF_SLOT_COST = 1
ARMOR_PROF_SLOT_COST = 1
# CT: a character proficient in an armor "only has to count half" its weight.
ARMOR_PROF_WEIGHT_FACTOR = 0.5


def is_shield(item_name: str) -> bool:
    return item_name in SHIELD_TYPES


def shield_ac_bonus(item_name: str, proficient: bool = False) -> int:
    """A shield's AC bonus, better when its wielder is proficient.

    The **homebrew item owns the normal bonus** (our Aspis is +2 where CT's medium
    shield is +1); CT's table only supplies the *proficient* upgrade, and never
    lowers a shield below its own value. Body shields list (melee, vs-missile)
    values; we take the melee one — the sheet has no column for the missile bonus."""
    shield_type = SHIELD_TYPES.get(item_name)
    if shield_type is None:
        return 0
    own = (item(item_name) or {}).get("ac_bonus", 0)
    if not proficient:
        return own
    value = SHIELD_PROFICIENCY[shield_type]["proficient_ac"]
    return max(own, value[0] if isinstance(value, tuple) else value)


def shield_attackers_blocked(item_name: str) -> int:
    """How many attacks in a round the shield's bonus may apply to."""
    shield_type = SHIELD_TYPES.get(item_name)
    return SHIELD_PROFICIENCY[shield_type]["attackers"] if shield_type else 0


def armor_items() -> tuple:
    """Armor a character can take an armor proficiency in (shields excluded — those
    take a shield proficiency instead)."""
    return tuple(it["name"] for it in items_in_category("Armor")
                 if not is_shield(it["name"]))


# ═══════════════════════════════════════════════════════════════════════════
#  Equipment — starting money, Armor Class, encumbrance
#  (Item data itself lives in equipment.py; these are the rules that use it.)
# ═══════════════════════════════════════════════════════════════════════════

# Starting money by class group, as (dice, sides, plus) in units of 10 gp — the
# 2e PHB rolls (Warrior 5d4×10 gp, Wizard (1d4+1)×10, Priest 3d6×10, Rogue 2d6×10).
# The campaign economy is copper-based (1 gp = 100 cp), so results convert to cp.
STARTING_MONEY = {
    "Warrior": (5, 4, 0),
    "Wizard":  (1, 4, 1),
    "Priest":  (3, 6, 0),
    "Rogue":   (2, 6, 0),
}
CP_PER_GP = 100


def roll_starting_money(class_name: str, rng=None) -> int:
    """Roll a fresh starting purse for a class, returned in copper pieces (cp)."""
    import random as _random
    rng = rng or _random
    dice, sides, plus = STARTING_MONEY[CLASSES[class_name].group]
    gp = (sum(rng.randint(1, sides) for _ in range(dice)) + plus) * 10
    return gp * CP_PER_GP


def armor_class(worn_ac_bonus: int, dex_score: int = None, house_rules: bool = True) -> int:
    """House-rule ascending AC: 10 (base) + worn armor bonuses + the Dexterity
    defensive adjustment (dexterity_mods().defensive_ac is negative = better, so it
    adds to an ascending score). Unarmored is 10 + Dex. asc_to_desc() converts it
    to the descending equivalent for anything still using the old scale."""
    dex_bonus = -dexterity_mods(dex_score).defensive_ac if dex_score is not None else 0
    return 10 + worn_ac_bonus + dex_bonus


# Encumbrance bands, as a fraction of the Strength weight allowance (PHB Table 47
# style, simplified): at/under the allowance is unencumbered; beyond it up to the
# maximum press is encumbered; past that is overloaded.
def encumbrance_status(weight_lb: float, str_score: int) -> str:
    mods = strength_mods(str_score)
    if weight_lb <= mods.weight_allow:
        return "Unencumbered"
    if weight_lb <= mods.max_press:
        return "Encumbered"
    return "Overloaded"


# The purchasable item catalog (generated in equipment.py), indexed for lookup.
ITEMS = {i["name"]: i for i in _equipment.ITEMS}
ITEM_CATEGORY_ORDER = _equipment.CATEGORY_ORDER


def item(name: str):
    """The catalog record for an item name, or None."""
    return ITEMS.get(name)


def items_in_category(category: str) -> list:
    """Every catalog item in a category, in catalog order."""
    return [i for i in _equipment.ITEMS if i["category"] == category]


# ═══════════════════════════════════════════════════════════════════════════
#  House rules — the computable override layer (campaign chargen rules)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class HouseRuleSet:
    # Hit dice: wizards roll d6 (not d4), rogues roll d8 (not d6).
    hit_die_override: dict
    # Rogues gain attack bonuses at ⅔/level, same as priests.
    rogue_attack_as_priest: bool
    # Each extra proficiency slot adds +2 (not +1).
    proficiency_bonus_per_slot: int
    # Proficiency check: d20 + skill, success on 21+.
    proficiency_check_target: int
    # Weapon-slot costs that differ from the default of 1.
    weapon_slot_cost: dict
    # Rangers are automatically ambidextrous; ambidexterity costs 1 slot otherwise.
    ranger_ambidextrous: bool
    ambidexterity_slot_cost: int
    # Aging: player places the penalties/bonuses; each entry is cumulative-per-level
    # (physical_penalty, mental_bonus). Index 0 = age level 1.
    aging_steps: tuple
    # Perception: a new stat taking the surprise adj (Dex) and illusion immunity (Int).
    perception_stat: bool


HOUSE_RULES = HouseRuleSet(
    hit_die_override={"Wizard": 6, "Rogue": 8},
    rogue_attack_as_priest=True,
    proficiency_bonus_per_slot=2,
    proficiency_check_target=21,
    weapon_slot_cost={"crossbow": 0, "light crossbow": 0, "heavy crossbow": 0,
                      "bow": 2, "long bow": 2, "longbow": 2, "short bow": 2, "shortbow": 2},
    ranger_ambidextrous=True,
    ambidexterity_slot_cost=1,
    aging_steps=((2, 1), (5, 1), (3, 2)),
    perception_stat=True,
)


def aging_totals(age_level: int) -> tuple:
    """Cumulative (physical_penalty, mental_bonus) at a given house-rule age level
    (1–3). The player chooses which specific stats receive them."""
    if not 1 <= age_level <= len(HOUSE_RULES.aging_steps):
        raise ValueError("age_level must be 1–3")
    pen = sum(step[0] for step in HOUSE_RULES.aging_steps[:age_level])
    bonus = sum(step[1] for step in HOUSE_RULES.aging_steps[:age_level])
    return pen, bonus


def is_ambidextrous(race: str, class_name: str, handedness_roll: int = None,
                    house_rules: bool = True) -> bool:
    """Rangers are always ambidextrous; otherwise a d10 handedness roll of 10 grants it."""
    if house_rules and class_name == "Ranger" and HOUSE_RULES.ranger_ambidextrous:
        return True
    return handedness_roll == 10


def xp_bonus_qualifies(class_name: str, abilities: dict) -> bool:
    """A character earns the +10% XP bonus when every prime requisite is 16+."""
    return all(abilities.get(pr, 0) >= 16 for pr in CLASSES[class_name].prime_requisites)


# ═══════════════════════════════════════════════════════════════════════════
#  Character-level convenience
# ═══════════════════════════════════════════════════════════════════════════

def eligible_classes(abilities: dict, race: str = None) -> list:
    """Every class the given abilities (and optionally race) qualify for."""
    out = []
    for name in CLASSES:
        if meets_class_minimums(name, abilities):
            continue
        if race is not None and not race_allows(race, name):
            continue
        out.append(name)
    return out


def eligible_races(abilities: dict) -> list:
    """Every race whose Table 7 requirements the given abilities satisfy."""
    return [name for name in RACES if not meets_racial_requirements(name, abilities)]


# ---------------------------------------------------------------------------
# Thieving skills -- PHB Tables 26 (base), 27 (race), 28 (Dexterity), 29 (armor)
#
# The base scores on Table 26 assume the thief is wearing *leather* armor, so
# Table 29 is a set of adjustments away from that baseline -- "leather" is the
# zero column and does not appear in the book's table at all.
#
# Bards run the same machinery over a four-skill subset with their own base
# scores (Table 33) and their own, smaller, pool of discretionary points.
# ---------------------------------------------------------------------------

THIEF_SKILLS = (
    "Pick Pockets",
    "Open Locks",
    "Find/Remove Traps",
    "Move Silently",
    "Hide in Shadows",
    "Detect Noise",
    "Climb Walls",
    "Read Languages",
)

#: No skill may exceed this, "including all adjustments for Dexterity, race,
#: and armor" (PHB, Thief).
THIEF_SKILL_MAX = 95

_THIEF_BASE = {                                     # Table 26
    "Pick Pockets": 15,
    "Open Locks": 10,
    "Find/Remove Traps": 5,
    "Move Silently": 10,
    "Hide in Shadows": 5,
    "Detect Noise": 15,
    "Climb Walls": 60,
    "Read Languages": 0,
}

_BARD_SKILLS = ("Climb Walls", "Detect Noise", "Pick Pockets", "Read Languages")
_BARD_BASE = {                                      # Table 33
    "Climb Walls": 50,
    "Detect Noise": 20,
    "Pick Pockets": 10,
    "Read Languages": 5,
}

_THIEF_RACIAL = {                                   # Table 27 (Human: all zero)
    "Dwarf":    {"Open Locks": 10, "Find/Remove Traps": 15, "Climb Walls": -10,
                 "Read Languages": -5},
    "Elf":      {"Pick Pockets": 5, "Open Locks": -5, "Move Silently": 5,
                 "Hide in Shadows": 10, "Detect Noise": 5},
    "Gnome":    {"Open Locks": 5, "Find/Remove Traps": 10, "Move Silently": 5,
                 "Hide in Shadows": 5, "Detect Noise": 10, "Climb Walls": -15},
    "Half-Elf": {"Pick Pockets": 10, "Hide in Shadows": 5},
    "Halfling": {"Pick Pockets": 5, "Open Locks": 5, "Find/Remove Traps": 5,
                 "Move Silently": 10, "Hide in Shadows": 15, "Detect Noise": 5,
                 "Climb Walls": -15, "Read Languages": -5},
}

#: Table 28, keyed by Dexterity. Only five skills are affected; scores below 9
#: and above 19 clamp to the ends of the table.
_THIEF_DEX = {
    #      PP,  OL, FRT,  MS,  HS
    9:  (-15, -10, -10, -20, -10),
    10: (-10,  -5, -10, -15,  -5),
    11: (-5,    0,  -5, -10,   0),
    12: (0,     0,   0,  -5,   0),
    13: (0,     0,   0,   0,   0),
    14: (0,     0,   0,   0,   0),
    15: (0,     0,   0,   0,   0),
    16: (0,     5,   0,   0,   0),
    17: (5,    10,   0,   5,   5),
    18: (10,   15,   5,  10,  10),
    19: (15,   20,  10,  15,  15),
}
_THIEF_DEX_SKILLS = ("Pick Pockets", "Open Locks", "Find/Remove Traps",
                     "Move Silently", "Hide in Shadows")

#: Table 29. ``leather`` is the baseline the Table 26 scores already assume.
THIEF_ARMOR_KINDS = ("none", "leather", "elven_chain", "padded_studded", "chain_ring")
_THIEF_ARMOR = {
    #                    none, elven_chain, padded_studded, chain_ring
    "Pick Pockets":      (5,  -20, -30, -25),
    "Open Locks":        (0,   -5, -10, -10),
    "Find/Remove Traps": (0,   -5, -10, -10),
    "Move Silently":     (10, -10, -20, -15),
    "Hide in Shadows":   (5,  -10, -20, -15),
    "Detect Noise":      (0,   -5, -10,  -5),
    "Climb Walls":       (10, -20, -30, -25),
    "Read Languages":    (0,    0,   0,   0),
}
_ARMOR_COLUMN = {"none": 0, "elven_chain": 1, "padded_studded": 2, "chain_ring": 3}

#: Worst armor worn wins, so rank the kinds by how much they hurt.
_ARMOR_SEVERITY = {kind: i for i, kind in enumerate(THIEF_ARMOR_KINDS)}


def thief_skill_class(class_name) -> str:
    """``"Thief"``, ``"Bard"``, or ``None`` -- who has thieving skills at all."""
    return class_name if class_name in ("Thief", "Bard") else None


def thief_skills_for_class(class_name) -> tuple:
    """The skills this class may use. Empty for everyone but Thief and Bard."""
    if class_name == "Thief":
        return THIEF_SKILLS
    if class_name == "Bard":
        return _BARD_SKILLS
    return ()


def thief_skill_base(class_name: str, skill: str) -> int:
    """Table 26 (thief) or Table 33 (bard) base score for one skill."""
    table = _BARD_BASE if class_name == "Bard" else _THIEF_BASE
    return table[skill]


def thief_racial_adjustment(race, skill: str) -> int:
    """Table 27. Bards read off the same table ("as given in the Thief description")."""
    return _THIEF_RACIAL.get(race, {}).get(skill, 0)


def thief_dex_adjustment(dex: int, skill: str) -> int:
    """Table 28, clamped at both ends. Skills the table ignores return 0."""
    if skill not in _THIEF_DEX_SKILLS:
        return 0
    row = _THIEF_DEX[max(9, min(19, int(dex)))]
    return row[_THIEF_DEX_SKILLS.index(skill)]


def thief_armor_kind(item_names) -> str:
    """Classify worn body armor into a Table 29 column.

    Helms and shields are not body armor and are ignored. Plate is not armor a
    thief may legally wear; it lands in the harshest column rather than raising.
    """
    body_armor = set(armor_items())
    worst = "none"
    for name in item_names:
        if name not in body_armor or name.startswith("Helm"):
            continue
        if name.startswith("Gambeson"):
            kind = "padded_studded"
        elif name.startswith("Leather"):
            kind = "leather"
        else:                                       # Chain, Plate
            kind = "chain_ring"
        if _ARMOR_SEVERITY[kind] > _ARMOR_SEVERITY[worst]:
            worst = kind
    return worst


def thief_armor_adjustment(armor_kind: str, skill: str) -> int:
    """Table 29. ``leather`` is the baseline and adjusts nothing."""
    if armor_kind == "leather":
        return 0
    return _THIEF_ARMOR[skill][_ARMOR_COLUMN[armor_kind]]


def thief_discretionary_points(class_name, level: int) -> int:
    """Points to spread across the skills: 60 + 30/level (thief), 20 + 15 (bard)."""
    level = max(1, int(level))
    if class_name == "Thief":
        return 60 + 30 * (level - 1)
    if class_name == "Bard":
        return 20 + 15 * (level - 1)
    return 0


def thief_max_points_in_skill(class_name, level: int) -> int:
    """Cap on points sunk into any *one* skill: 30 at 1st, +15 per level after.

    The book states this cap for thieves only; bards inherit it here so that a
    1st-level bard cannot dump all 20 points into Climb Walls, which the thief
    rule plainly means to forbid.
    """
    if thief_skill_class(class_name) is None:
        return 0
    return 30 + 15 * (max(1, int(level)) - 1)


def thief_skill_score(class_name: str, race, dex: int, armor_kind: str,
                      skill: str, allocated: int = 0) -> int:
    """Final percentage for one skill, capped at :data:`THIEF_SKILL_MAX`."""
    total = (thief_skill_base(class_name, skill)
             + thief_racial_adjustment(race, skill)
             + thief_dex_adjustment(dex, skill)
             + thief_armor_adjustment(armor_kind, skill)
             + int(allocated))
    return max(0, min(THIEF_SKILL_MAX, total))


# ---------------------------------------------------------------------------
# Turning undead -- PHB Table 61
#
# An entry is the d20 roll the priest must meet or beat. "T" turns automatically,
# "D" destroys automatically, "D*" destroys and takes 2d4 extra creatures with
# it, and None means this priest cannot affect that kind of undead at all.
#
# The table is a perfect diagonal: every row is the row above it shifted one
# column right. ``test_char_rules`` asserts that, which is what catches a typo
# in the transcription below.
# ---------------------------------------------------------------------------

TURN_UNDEAD_TYPES = (
    "Skeleton or 1 HD",
    "Zombie",
    "Ghoul or 2 HD",
    "Shadow or 3-4 HD",
    "Wight or 5 HD",
    "Ghast",
    "Wraith or 6 HD",
    "Mummy or 7 HD",
    "Spectre or 8 HD",
    "Vampire or 9 HD",
    "Ghost or 10 HD",
    "Lich or 11+ HD",
    "Special",
)

_T, _D, _DS, _X = "T", "D", "D*", None

#: Columns are priest levels 1..9, then 10-11, 12-13, 14+.
_TURN_UNDEAD = {
    "Skeleton or 1 HD": (10,  7,  4, _T, _T, _D, _D, _DS, _DS, _DS, _DS, _DS),
    "Zombie":           (13, 10,  7,  4, _T, _T, _D, _D, _DS, _DS, _DS, _DS),
    "Ghoul or 2 HD":    (16, 13, 10,  7,  4, _T, _T, _D, _D, _DS, _DS, _DS),
    "Shadow or 3-4 HD": (19, 16, 13, 10,  7,  4, _T, _T, _D, _D, _DS, _DS),
    "Wight or 5 HD":    (20, 19, 16, 13, 10,  7,  4, _T, _T, _D, _D, _DS),
    "Ghast":            (_X, 20, 19, 16, 13, 10,  7,  4, _T, _T, _D, _D),
    "Wraith or 6 HD":   (_X, _X, 20, 19, 16, 13, 10,  7,  4, _T, _T, _D),
    "Mummy or 7 HD":    (_X, _X, _X, 20, 19, 16, 13, 10,  7,  4, _T, _T),
    "Spectre or 8 HD":  (_X, _X, _X, _X, 20, 19, 16, 13, 10,  7,  4, _T),
    "Vampire or 9 HD":  (_X, _X, _X, _X, _X, 20, 19, 16, 13, 10,  7,  4),
    "Ghost or 10 HD":   (_X, _X, _X, _X, _X, _X, 20, 19, 16, 13, 10,  7),
    "Lich or 11+ HD":   (_X, _X, _X, _X, _X, _X, _X, 20, 19, 16, 13, 10),
    "Special":          (_X, _X, _X, _X, _X, _X, _X, _X, 20, 19, 16, 13),
}


def turn_undead_level(class_name, level: int):
    """The level a character *turns as*, or ``None`` if they cannot turn at all.

    Clerics turn from 1st level at their own level. Paladins "turn undead as
    priests who are two levels lower", which is why they start at 3rd. Druids
    and every non-priest class never turn.
    """
    level = int(level)
    if class_name == "Cleric":
        return level
    if class_name == "Paladin":
        effective = level - 2
        return effective if effective >= 1 else None
    return None


def _turn_column(priest_level: int) -> int:
    """Table 61's columns collapse above 9th: 10-11, 12-13, 14+."""
    if priest_level <= 9:
        return priest_level - 1
    if priest_level <= 11:
        return 9
    if priest_level <= 13:
        return 10
    return 11


def turn_undead(class_name, level: int):
    """Map every undead type to this character's Table 61 result, or ``None``.

    Values are an ``int`` (the d20 roll needed), ``"T"``, ``"D"``, ``"D*"``, or
    ``None`` for undead this character cannot turn.
    """
    priest_level = turn_undead_level(class_name, level)
    if priest_level is None:
        return None
    column = _turn_column(priest_level)
    return {kind: row[column] for kind, row in _TURN_UNDEAD.items()}

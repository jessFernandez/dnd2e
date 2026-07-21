"""monster.py — the AD&D 2e monster stat block model.

Pure and Qt-free (like character.py): the ``Monster`` record plus the campaign
house-rule numbers it derives on demand. The rules are applied through char_rules
— never reimplemented here — so the monster sheet, the DM Screen, the calculator
and the builder can't disagree:

  * attack bonus = 20 − THAC0, ascending AC = 20 − descending AC
    (``char_rules.thac0_to_bonus`` / ``desc_to_asc``), applied to the numbers
    inside the stat strings (ranges and "Overall 2, underside 4" convert in place);
  * initiative speed factor comes from the creature's Size via
    ``char_rules.monster_initiative_modifier`` (the DM Screen's own size table).

Parsing MM pages into Monsters lives in **monster_parser.py** (the larger, fiddlier
layer, kept separate so this model stays small and stable — the char_rules/character
split). Persistence lives in monster_library.py; the sheet view in monster_html.py.
"""
import re
from dataclasses import dataclass, asdict, field, fields

import char_rules as cr

_SIZE_ORDER = "TSMLHG"   # Tiny < Small < Medium < Large < Huge < Gargantuan


@dataclass
class Monster:
    """One monster's stat block plus prose. Stat fields hold the MM strings
    verbatim (values are often ranges or notes, not bare numbers); the house-rule
    numbers are derived on demand."""
    name: str = ""
    source_page: str = ""          # e.g. "MM/DD03797.htm" — back-link to the MM page
    variant: str = ""              # e.g. "Black" for a multi-variant page, else ""
    image: str = ""                # the page's illustration filename, e.g. "ANKHEG.gif"

    climate_terrain: str = ""
    frequency: str = ""
    organization: str = ""
    activity_cycle: str = ""
    diet: str = ""
    intelligence: str = ""
    treasure: str = ""
    alignment: str = ""
    no_appearing: str = ""
    armor_class: str = ""
    movement: str = ""
    hit_dice: str = ""
    thac0: str = ""
    no_of_attacks: str = ""
    damage_attack: str = ""
    special_attacks: str = ""
    special_defenses: str = ""
    magic_resistance: str = ""
    size: str = ""
    morale: str = ""
    xp_value: str = ""

    description: str = ""
    combat: str = ""
    habitat_society: str = ""
    ecology: str = ""

    #: Breath-weapon damage for the selected dragon age tier (Phase B) — empty on the
    #: base stat block; set by monster_tiers from the age table's Breath column.
    breath_weapon: str = ""

    #: Editable initiative speed factor; None means "derive from size".
    initiative_override: "int | None" = None

    #: Selected HD/age scaling tier (index into monster_tiers.tiers(self)); None means
    #: "show the base stat block as written". Set by the sheet's tier selector
    #: (Phase B), persisted with the monster.
    selected_tier: "int | None" = None

    #: Creatures the MM page describes in prose only — no stat column of their own
    #: (the Archlich on the Lich page, the Kapoacinth on the Gargoyle page). Each is a
    #: plain {name, text} dict (Phase C), attached to every creature on the page.
    related_creatures: list = field(default_factory=list)

    #: Enrichment tables the MM page carries past the stat block (dragon age
    #: progression, psionics summaries, per-attack damage), classified by
    #: monster_parser (Phase A). Each is a plain {kind, header_rows, rows} dict so it
    #: roundtrips through to_dict/from_dict; Phase B's tier selector reads the
    #: ``age`` ones.
    extra_tables: list = field(default_factory=list)

    # ── house-rule derived values (via char_rules) ────────────────────────────

    def attack_bonus(self) -> str:
        """The house-rule attack bonus (20 − THAC0) as a single base value. Monster
        THAC0 is often a range or an HD-conditional list ('3+3 HD: 17 4+4 HD: 15');
        we take the base THAC0 (the first listed) rather than clutter the sheet with
        every case — the DM can read the raw field for the breakdown."""
        base = _base_thac0(self.thac0)
        return "" if base is None else str(cr.thac0_to_bonus(base))

    def ascending_ac(self) -> str:
        """Descending AC converted to ascending, e.g. '-2' -> '22',
        'Overall 2, underside 4' -> 'Overall 18, underside 16'."""
        return _map_numbers(self.armor_class, cr.desc_to_asc, signed=True)

    def size_category(self) -> str:
        """The single size letter used for rules (the largest of a range)."""
        return _largest_size(self.size)

    def initiative_modifier(self):
        """The initiative speed factor: the manual override if set, else derived
        from Size (None if the size is unrecognized)."""
        if self.initiative_override is not None:
            return self.initiative_override
        return cr.monster_initiative_modifier(self.size_category())

    # ── persistence ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Monster":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


# ── conversions ───────────────────────────────────────────────────────────────

_RANGE = re.compile(r"(\d+)\s*-\s*(\d+)")


def damage_to_dice(text: str, terse: bool = False) -> str:
    """MM damage ranges rewritten as dice: '3-18 (crush)+1-4 (acid)' ->
    '3d6 (crush)+1d4 (acid)'. A range a-b becomes ``a`` dice of d(b/a) when that
    divides evenly (min a, max b); anything that doesn't — '2-5' — is left alone, as is
    text that is already dice.

    ``terse`` writes a single die the way the sheet displays it ('d4'), against the
    canonical form Roll20 needs to roll it ('1d4'). One rule, two renderings: the sheet
    and the Roll20 export must not disagree about what a monster's damage is (the
    char_rules re-export discipline, applied to the MM's own notation)."""
    def repl(m):
        a, b = int(m.group(1)), int(m.group(2))
        if a >= 1 and b > a and b % a == 0 and (b // a) >= 2:
            die = b // a
            return f"d{die}" if (terse and a == 1) else f"{a}d{die}"
        return m.group(0)
    return _RANGE.sub(repl, text or "")


def _map_numbers(text: str, fn, signed: bool = False) -> str:
    """Apply ``fn`` to every integer in ``text``, leaving the rest intact. Unsigned
    by default so a THAC0 range like '17-13' reads the hyphen as a separator; pass
    signed=True for AC, where a value can genuinely be negative ('-2')."""
    if not text:
        return ""
    pattern = r"-?\d+" if signed else r"\d+"
    return re.sub(pattern, lambda m: str(fn(int(m.group()))), text)


#: Monster fields the sheet lets the DM edit (everything textual; not the id-like
#: source_page/variant or the numeric initiative override).
EDITABLE_FIELDS = frozenset(
    {f.name for f in fields(Monster)}
    - {"source_page", "variant", "image", "initiative_override", "extra_tables",
       "selected_tier", "breath_weapon", "related_creatures"})


#: A THAC0 the sheet can safely show (and take back) as an attack bonus: a single
#: number. Anything richer — a range ('17-13'), or an HD/hp-conditional list
#: ('45-49 hp: 11 50-59 hp: 9 …') — collapses to its base value on the way out and
#: would overwrite the whole field on the way back in.
_BARE_NUMBER = re.compile(r"^\s*-?\d+\s*$")


def house_rule_round_trips(field: str, value: str) -> bool:
    """Whether ``field``'s house-rule display can be edited without losing what the
    MM wrote. AC always can — ascending_ac() maps *every* number in place, so it is
    its own inverse. THAC0 only can when it's a bare number: attack_bonus() reports
    the base value alone, so writing that back would replace a range or a conditional
    list ('3+3 HD: 17 4+4 HD: 15') with a single number — silently destroying both the
    source text and the tiers monster_tiers derives from it. Such a field is shown raw
    and read-only instead, with the derived bonus beside it."""
    if field == "thac0":
        return bool(_BARE_NUMBER.match(value or ""))
    return True


def house_rule_to_raw(field: str, value: str) -> str:
    """Convert an edited house-rule value back to the stored MM form. The sheet
    shows ascending AC and attack bonus, so those two invert on the way in (both
    are 20−x involutions, matching ascending_ac()/attack_bonus()); every other
    field is stored verbatim (damage keeps whatever dice/text the DM typed)."""
    if field == "armor_class":
        return _map_numbers(value, cr.desc_to_asc, signed=True)
    if field == "thac0":
        return _map_numbers(value, cr.thac0_to_bonus)
    return value


def _largest_size(size_text: str) -> str:
    """The largest size-category letter in the field, e.g. 'L-H (10' long)' -> 'H'.
    Only the part before any parenthetical is considered."""
    head = (size_text or "").split("(")[0].upper()
    cats = [c for c in head if c in _SIZE_ORDER]
    if not cats:
        return ""
    return max(cats, key=_SIZE_ORDER.index)


def _base_thac0(thac0_text: str):
    """The base THAC0 integer: the value after the first 'HD:'/'hp:' for creatures
    whose THAC0 varies by Hit Dice or hit points ('45-49 hp: 11 …', '3+3 HD: 17 …'),
    else the first number in the field (the low end of a range). None if there are no
    digits ('Nil', 'See below')."""
    if not thac0_text:
        return None
    m = re.search(r"(?:HD|hp):\s*(-?\d+)", thac0_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"-?\d+", thac0_text)
    return int(m.group()) if m else None

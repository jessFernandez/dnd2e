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
from dataclasses import dataclass, asdict, fields

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

    #: Editable initiative speed factor; None means "derive from size".
    initiative_override: "int | None" = None

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
    {f.name for f in fields(Monster)} - {"source_page", "variant", "image", "initiative_override"})


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

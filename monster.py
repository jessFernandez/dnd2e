"""monster.py — the AD&D 2e monster stat block, and a parser for the Monstrous
Manual pages in dnd2e.db.

Pure and Qt-free (like character.py): the model plus ``parse_stat_block``, which
turns a scraped MM page into one or more ``Monster`` records (a page like "Bear"
yields several variants). The campaign house rules are applied through char_rules
— never reimplemented here — so the monster sheet, the DM Screen, the calculator
and the builder can't disagree:

  * attack bonus = 20 − THAC0, ascending AC = 20 − descending AC
    (``char_rules.thac0_to_bonus`` / ``desc_to_asc``), applied to the numbers
    inside the stat strings (ranges and "Overall 2, underside 4" convert in place);
  * initiative speed factor comes from the creature's Size via
    ``char_rules.monster_initiative_modifier`` (the DM Screen's own size table).

The stat block is parsed from ``content_html``, not ``content_text``: the multi-
variant pages (Cat, Snake, …) are laid out as multi-column tables, and the text
scrape flattens those columns together unrecoverably. The HTML keeps them as
``<TD>`` cells, so a stdlib ``html.parser`` (no bs4 at runtime) reads the columns
cleanly. The Qt layer (app.py) picks a page, calls parse_stat_block, and loads the
result into the monster sheet where the DM can edit and save it.
"""
import re
from dataclasses import dataclass, asdict, fields
from html.parser import HTMLParser

import char_rules as cr

# ── The stat-block grammar ────────────────────────────────────────────────────

#: Canonical label -> Monster field. The 21 labels every MM stat block carries.
FIELD_BY_LABEL = {
    "CLIMATE/TERRAIN": "climate_terrain",
    "FREQUENCY": "frequency",
    "ORGANIZATION": "organization",
    "ACTIVITY CYCLE": "activity_cycle",
    "DIET": "diet",
    "INTELLIGENCE": "intelligence",
    "TREASURE": "treasure",
    "ALIGNMENT": "alignment",
    "NO. APPEARING": "no_appearing",
    "ARMOR CLASS": "armor_class",
    "MOVEMENT": "movement",
    "HIT DICE": "hit_dice",
    "THAC0": "thac0",
    "NO. OF ATTACKS": "no_of_attacks",
    "DAMAGE/ATTACK": "damage_attack",
    "SPECIAL ATTACKS": "special_attacks",
    "SPECIAL DEFENSES": "special_defenses",
    "MAGIC RESISTANCE": "magic_resistance",
    "SIZE": "size",
    "MORALE": "morale",
    "XP VALUE": "xp_value",
}
_CANONICAL = set(FIELD_BY_LABEL)

#: OCR / spacing variants seen in the scrape, folded onto their canonical label.
_LABEL_ALIASES = {
    "DAMAGE/ATTACKS": "DAMAGE/ATTACK",
    "DAMAGE/ ATTACK": "DAMAGE/ATTACK",
    "CLIMATE/ TERRAIN": "CLIMATE/TERRAIN",
    "ACTIVE TIME": "ACTIVITY CYCLE",
    "THACO": "THAC0",              # OCR: letter O for zero
    "NO.APPEARING": "NO. APPEARING",
    "SPECIALATTACKS": "SPECIAL ATTACKS",
    "LEVEL/XP VALUE": "XP VALUE",
}

#: Prose section header (matched at line start) -> Monster field.
_SECTIONS = [
    ("Combat:", "combat"),
    ("Habitat/Society:", "habitat_society"),
    ("Ecology:", "ecology"),
]

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


# ── the parser ────────────────────────────────────────────────────────────────

def _norm_label(cell: str):
    """Canonical stat-block label for a first-column cell, or None if it isn't one.
    The trailing colon is optional — the scrape drops it on some pages — and the
    first table column is only ever a label or empty, so this can't match a value."""
    key = " ".join(cell.strip().rstrip(":").split()).upper()   # drop colon, collapse spaces
    key = _LABEL_ALIASES.get(key, key)
    return key if key in _CANONICAL else None


def _clean_prose(text: str) -> str:
    """Reflow scraped prose for a text box. The MM hard-wraps every line with <br>,
    and tables embedded in the prose leave long runs of blank lines — so collapse
    each paragraph's wrapped lines into flowing text, and blank-line runs into a
    single paragraph break."""
    paragraphs = re.split(r"\n[ \t]*\n+", text)
    return "\n\n".join(p for p in (" ".join(para.split()) for para in paragraphs) if p)


def _split_prose(text: str):
    """Split the post-table body into (description, combat, habitat, ecology) on the
    known section headers; text before the first header is the description."""
    buckets = {"description": [], "combat": [], "habitat_society": [], "ecology": []}
    current = "description"
    for line in text.splitlines():
        s = line.strip()
        hit = next(((f, h) for h, f in _SECTIONS if s.lower().startswith(h.lower())), None)
        if hit:
            current, header = hit
            rest = s[len(header):].strip()
            if rest:
                buckets[current].append(rest)
        else:
            buckets[current].append(line.rstrip())
    return tuple(_clean_prose("\n".join(buckets[k]))
                 for k in ("description", "combat", "habitat_society", "ecology"))


class _StatBlockHTML(HTMLParser):
    """Reads every <TABLE> as a grid of cell strings (column 0 = label, columns
    1..N = one per variant) and collects the body text outside the tables as prose.
    All tables are concatenated because a page may split the variant-name header
    into its own table (Crocodile); the group segmentation sorts them out. Wrapped
    values arrive as continuation rows (empty first cell), stitched back per column
    by _group_to_monsters."""

    def __init__(self):
        super().__init__()
        self.rows: list = []
        self._row = None
        self._cell = None
        self._in_table = False
        self._seen_table = False
        self._prose: list = []
        self.image = ""

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "img" and not self.image:
            self.image = dict(attrs).get("src", "") or ""
        if t == "table":
            self._in_table = self._seen_table = True
        elif self._in_table:
            if t == "tr":
                self._row = []
            elif t == "td" and self._row is not None:
                self._cell = []
            elif t == "br" and self._cell is not None:
                self._cell.append(" ")
        elif self._seen_table and t in ("br", "p"):
            self._prose.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "table":
            self._in_table = False
            self._cell = self._row = None
        elif self._in_table:
            if t == "td" and self._cell is not None:
                self._row.append(" ".join("".join(self._cell).split()))
                self._cell = None
            elif t == "tr" and self._row is not None:
                self.rows.append(self._row)
                self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._seen_table and not self._in_table:
            self._prose.append(data)

    def prose(self) -> str:
        return "".join(self._prose)


def _segment_groups(rows):
    """Split the grid into stat-block groups — a page may stack several (Cat, Great
    = nine cats; Spider = seven), each with its own variant header. Groups are keyed
    off each CLIMATE/TERRAIN (the conventional first label); a group's header rows
    are the empty-first rows just before its CLIMATE, walking back only until a
    labelled row or a fully-blank separator. Stopping at a blank keeps a group's
    wrapped XP tail (Spider) out of the next group's header, while *not* splitting on
    every blank keeps a cosmetic blank row inside a block (Beholder) from tearing one
    group in two."""
    climates = [i for i, r in enumerate(rows)
                if _norm_label(r[0].strip()) == "CLIMATE/TERRAIN"]
    if not climates:
        return []
    starts = []
    for k, ci in enumerate(climates):
        if k == 0:
            starts.append(0)                      # first group owns everything above it
            continue
        s, low = ci, starts[-1]
        while s - 1 > low:
            prev = rows[s - 1]
            if prev[0].strip() or not any(c.strip() for c in prev):
                break                              # a labelled row, or a blank separator
            s -= 1                                 # a header row (variant names)
        starts.append(s)
    starts.append(len(rows))
    return [rows[a:b] for a, b in zip(starts, starts[1:])]


def _group_to_monsters(rows, group, source_page, prose):
    ncol = max((len(r) for r in rows), default=0)
    if ncol < 2:
        return []

    variant_cols = [""] * (ncol - 1)
    have_variants = False
    stat_fields: list = []          # [canonical_label, [value per column]]
    seen_label = False
    for row in rows:
        row = row + [""] * (ncol - len(row))
        first, vals = row[0].strip(), row[1:]
        canon = _norm_label(first)
        if canon:
            stat_fields.append([canon, list(vals)])
            seen_label = True
        elif not first:                       # header (before labels) or continuation
            target = variant_cols if not seen_label else (stat_fields[-1][1] if stat_fields else None)
            if target is not None:
                for i, v in enumerate(vals):
                    if v:
                        target[i] = (target[i] + " " + v).strip()
                        if target is variant_cols:
                            have_variants = True

    if not any(c == "ARMOR CLASS" for c, _ in stat_fields):
        return []                              # not a real stat block

    field_map = {FIELD_BY_LABEL[c]: v for c, v in stat_fields}
    # a group's real columns are those with a variant name (multi-variant) — the
    # single lone column otherwise. Unnamed trailing columns are padding.
    cols = [i for i in range(ncol - 1) if variant_cols[i].strip()] if have_variants else [0]

    monsters = []
    for i in cols:
        variant = variant_cols[i].strip() if have_variants else ""
        m = Monster(
            name=_monster_name(variant, group),
            source_page=source_page, variant=variant,
            description=prose[0], combat=prose[1],
            habitat_society=prose[2], ecology=prose[3],
        )
        for field, vals in field_map.items():
            setattr(m, field, vals[i].strip() if i < len(vals) else "")
        monsters.append(m)
    return monsters


def _grid_to_monsters(rows, group, source_page, prose_text):
    prose = _split_prose(prose_text)
    monsters = []
    for seg in _segment_groups(rows):
        monsters.extend(_group_to_monsters(seg, group, source_page, prose))
    return monsters


def _clean_title(title: str) -> str:
    """The monster/group name from a page title: drop the ' (Monstrous Manual)'
    suffix and render the scrape's '--' separator as a comma ('Cat-- Great')."""
    base = (title or "").split(" (Monstrous Manual")[0].strip()
    return re.sub(r"\s*--\s*", ", ", base)


def _monster_name(variant: str, group: str) -> str:
    """A variant's display name. A *category* group — 'Cat, Great', 'Beholder and
    Beholder-kin I', 'Mammal, Herd', 'Ooze/Slime/Jelly' — already lists full creature
    names in its columns ('Cheetah', 'Death Kiss'), so use the variant alone. A
    *plain* group — 'Bear', 'Spider' — lists adjectives, so prefix them onto the base
    ('Black' → 'Black Bear'). Avoid duplicating the base ('Rat' + 'Rat' → 'Rat')."""
    if not variant:
        return group
    if any(mark in group for mark in (",", " and ", "-kin", "/")):
        return variant
    if variant.lower() == group.lower() or group.lower() in variant.lower():
        return variant
    return f"{variant} {group}"


def importable_pages(conn) -> list:
    """(page_url, display_name, creature_count) for every MM page that actually parses
    to a monster. ``creature_count`` is how many creatures the page holds (Bear → 4,
    Mammal → 29). Filters out the generic category pages (Dragon-- General, 'The
    Monsters', …) that mention 'ARMOR CLASS'/'THAC0' but carry no stat block."""
    import db
    out = []
    for url, title in db.list_monster_pages(conn):
        row = db.get_page(conn, url)
        if row:
            monsters = parse_stat_block(row["content_html"], row["title"], url)
            if monsters:
                out.append((url, _clean_title(title), len(monsters)))
    return out


def _split_family(title: str):
    """('Dragon', 'Chromatic: Black Dragon') for a 'Family-- Subtype' MM title, or
    (None, name) for a standalone monster. The MM separates families with '-- '."""
    base = (title or "").split(" (Monstrous Manual")[0].strip()
    if "-- " in base:
        family, _, subtype = base.partition("-- ")
        return family.strip(), subtype.strip()
    return None, base


def _is_general(subtype: str) -> bool:
    """Whether a subtype is a family's lore page (no stat block): 'General' or
    'Generic Information'."""
    return "general" in subtype.lower() or "generic information" in subtype.lower()


def importable_index(conn):
    """Group importable MM monsters by their 'Family-- Subtype' title, for the picker.

    Returns (families, standalone):
      families   = [(family, general_url|None, [(page_url, subtype, count), ...]), ...]
      standalone = [(page_url, name, count), ...]
    ``count`` is the page's creature count (>1 for a multi-variant page). A family
    needs ≥2 members (or a General page) to be a group; otherwise its lone member is
    listed standalone. The '-- General'/'Generic Information' lore pages — which have
    no stat block, so aren't importable — are attached so the picker can link to
    them."""
    import db
    titles = dict(conn.execute(
        "SELECT page_url, title FROM pages WHERE book_code='MM'").fetchall())
    generals = {}
    for url, title in titles.items():
        family, subtype = _split_family(title)
        if family and _is_general(subtype):
            generals[family] = url

    members, standalone = {}, []
    for url, name, count in importable_pages(conn):
        family, subtype = _split_family(titles.get(url, ""))
        if family:
            members.setdefault(family, []).append((url, subtype, count))
        else:
            standalone.append((url, name, count))

    families = []
    for family, mem in members.items():
        if len(mem) >= 2 or family in generals:
            families.append((family, generals.get(family),
                             sorted(mem, key=lambda m: m[1].lower())))
        else:
            url, subtype, count = mem[0]
            standalone.append((url, _clean_title(titles.get(url, subtype)), count))
    families.sort(key=lambda f: f[0].lower())
    standalone.sort(key=lambda s: s[1].lower())
    return families, standalone


# The compact "summary" pages (Mammal, Bird, Fish, Insect) list many minor
# creatures as one row each under abbreviated column headers, rather than the
# standard label-per-row stat block. Header text -> Monster field.
_COMPACT_HEADERS = {
    "#AP": "no_appearing", "NO. APP": "no_appearing", "APP": "no_appearing",
    "NO. APPEARING": "no_appearing", "#APP": "no_appearing",
    "AC": "armor_class", "ARMOR CLASS": "armor_class",
    "MV": "movement", "MOVEMENT": "movement",
    "HD": "hit_dice", "HIT DICE": "hit_dice",
    "THAC0": "thac0", "THACO": "thac0",
    "# OF ATT": "no_of_attacks", "NO. OF ATTACKS": "no_of_attacks",
    "ATTACKS": "no_of_attacks", "# ATT": "no_of_attacks", "NO ATT": "no_of_attacks",
    "DMG/ATT": "damage_attack", "DAMAGE/ATTACK": "damage_attack",
    "DAMAGE": "damage_attack", "DMG": "damage_attack", "ATTACK": "damage_attack",
    "MORALE": "morale", "ML": "morale",
    "XP VALUE": "xp_value", "XP": "xp_value", "VALUE": "xp_value",
    "SIZE": "size", "SZ": "size", "AL": "alignment", "ALIGNMENT": "alignment",
    "INT": "intelligence", "INTELLIGENCE": "intelligence",
    "NOTES": "special_attacks", "SA": "special_attacks",
}


def _parse_compact_table(rows, source_page):
    """Parse a compact summary table (row 0 = abbreviated headers, each later row a
    creature). Returns a Monster per data row, or [] if row 0 isn't such a header."""
    if not rows:
        return []
    header = rows[0]
    field_by_col = {}
    for col, cell in enumerate(header[1:], start=1):       # column 0 is the creature name
        key = " ".join(cell.strip().rstrip(".").upper().split())
        field = _COMPACT_HEADERS.get(key)
        if field:
            field_by_col[col] = field
    fields_present = set(field_by_col.values())
    if not {"armor_class", "hit_dice"} <= fields_present:  # confidence: it's a stat table
        return []

    monsters = []
    for row in rows[1:]:
        if not row or not row[0].strip():                  # skip blank / continuation rows
            continue
        m = Monster(name=row[0].strip(), source_page=source_page)
        for col, field in field_by_col.items():
            if col < len(row):
                setattr(m, field, row[col].strip())
        if not m.armor_class:                              # cross-references ("See Raven"),
            continue                                       # sub-headers, etc. carry no AC
        monsters.append(m)
    return monsters


def parse_stat_block(content_html: str, title: str = "", source_page: str = "") -> list:
    """Parse a Monstrous Manual page into a list of Monsters — one per variant (a
    single-creature page yields one). Falls back to the compact summary-table format
    (Mammal, Bird, …). Returns [] for pages without a real stat block (front matter,
    generic category pages, the blank form)."""
    parser = _StatBlockHTML()
    try:
        parser.feed(content_html or "")
    except Exception:
        return []
    monsters = (_grid_to_monsters(parser.rows, _clean_title(title), source_page, parser.prose())
                or _parse_compact_table(parser.rows, source_page))
    for m in monsters:
        m.image = parser.image
    return monsters

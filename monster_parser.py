"""monster_parser.py — parse Monstrous Manual pages in dnd2e.db into Monsters.

Split out of monster.py so the model (``Monster`` + its house-rule derivations)
stays small and stable while this — the larger, fiddlier layer — absorbs the churn
of new source formats. Pure and Qt-free: ``parse_stat_block`` turns a scraped MM
page into one or more ``Monster`` records (a page like "Bear" yields several
variants); ``importable_pages`` / ``importable_index`` enumerate what the picker can
offer. Mirrors the ``char_rules`` (rules) vs ``character`` (model) split.

The stat block is parsed from ``content_html``, not ``content_text``: the multi-
variant pages (Cat, Snake, …) are laid out as multi-column tables, and the text
scrape flattens those columns together unrecoverably. The HTML keeps them as
``<TD>`` cells, so a stdlib ``html.parser`` (no bs4 at runtime) reads the columns
cleanly. The Qt layer (app.py) picks a page, calls parse_stat_block, and loads the
result into the monster sheet where the DM can edit and save it.
"""
import re
from html.parser import HTMLParser
from itertools import permutations

from monster import Monster

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

#: Prose section header (matched at line start) -> Monster field. The extra
#: Habitat/Society spellings are OCR/typo variants in the scrape ("Habit/Society"
#: on the Blue Dragon page, "Society/Habitat", "Habitat Society"); without them the
#: section is misread as a continuation of Combat and habitat_society comes out empty.
_SECTIONS = [
    ("Combat:", "combat"),
    ("Habitat/Society:", "habitat_society"),
    ("Habit/Society:", "habitat_society"),
    ("Society/Habitat:", "habitat_society"),
    ("Habitat Society:", "habitat_society"),
    ("Ecology:", "ecology"),
]


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
    single paragraph break. Also drop the 'Index' link the MM footer appends to
    every page's last section."""
    paragraphs = re.split(r"\n[ \t]*\n+", text)
    result = "\n\n".join(p for p in (" ".join(para.split()) for para in paragraphs) if p)
    return re.sub(r"\s*\bIndex\s*$", "", result)


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


def _norm_header(s: str) -> str:
    """Fold a header/name for comparison: lowercase, punctuation (colon, comma,
    hyphen, parens, apostrophe) to spaces, whitespace collapsed."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


#: Words that carry no identity in a creature name, dropped before comparing.
_FILLER_WORDS = frozenset({"the", "a", "an", "of", "and"})


def _name_tokens(text: str):
    """The identity-bearing words of a name: normalized, filler dropped, de-pluralized
    ('Giant Rats' -> ('giant', 'rat')). Order is preserved for the caller to permute."""
    out = []
    for w in _norm_header(text).split():
        if w in _FILLER_WORDS:
            continue
        if len(w) >= 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return tuple(out)


def _same_words(run: str, name: str) -> bool:
    """Whether two names are **the same words, reordered and/or run together**. The MM
    and its stat columns disagree about both constantly — the column is an index entry
    ('Jelly, Stun-', 'Rat (Giant)', 'Sea Horse, Giant') while the prose sub-header reads
    naturally ('Stunjelly', 'Giant Rats', 'Seahorse, Giant'), and a wrapped column name
    closes up ('Megalo- centipede' -> 'Megalocentipede'). Comparing the tokens' possible
    concatenations catches all of those without loosening the matcher for names that
    merely *share* a word. Bounded: beyond 4 words, compare the words themselves."""
    a, b = _name_tokens(run), _name_tokens(name)
    if not a or not b:
        return False
    if max(len(a), len(b)) > 4:
        return sorted(a) == sorted(b)
    joins = {"".join(p) for p in permutations(a)}
    return any("".join(p) in joins for p in permutations(b))


def _header_score(run: str, name: str) -> int:
    """How well a bold prose sub-header ``run`` names variant ``name`` (0 = not at all).
    Higher is more specific, so a header is claimed by its best match:

      3  exact                       "Owl" -> Owl (beats the prefix match "Owl, Giant")
      2  plural/singular             "War Dogs" -> War Dog, "Efreet"/"Janni" -> Efreeti/Jann
      2  the same words, reordered / run together (_same_words): "Giant Rats" -> "Rat
         (Giant)", "Stunjelly" -> "Jelly, Stun-", "Greenhag" -> "Green Hag"
      1  the header and variant name one creature at different specificity. When the
         **header is the shorter** (a family/base word) it appears as a whole-word
         prefix or suffix of the fuller variant name ("Abishai" -> "Black Abishai",
         "Merrow" -> "Merrow Ogre"). When the **header is the longer** (a specific
         name) the variant must be its leading word ("Undead Beholder" -> "Undead") —
         a *trailing* family word is the base creature, so "Undead Beholder" does NOT
         claim the base "Beholder"."""
    r, v = _norm_header(run), _norm_header(name)
    if not r or not v:
        return 0
    if r == v:
        return 3
    short, long = sorted((r, v), key=len)
    plurals = {short + "s", short + "es", short + "i", short + "e"}
    if len(short) > 1:                      # irregular: dwarf->dwarves, seawolf->seawolves
        plurals |= {short[:-1] + "ves", short[:-1] + "ies"}
    if long in plurals:
        return 2
    if _same_words(r, v):
        return 2
    if len(r) <= len(v):                          # header is the family/base word
        if v.startswith(r + " ") or v.endswith(" " + r):
            return 1
    elif r.startswith(v + " "):                   # longer header, variant is its lead word
        return 1
    return 0


def _match_score(run: str, m) -> int:
    """How well a bold sub-header names monster ``m`` — scored against both its display
    name *and* the raw stat column it came from, best wins. The two can differ: the
    display name is built by _resolve_name (which prefixes a group noun, or applies a
    curated override), so a header that reads exactly like the column ("The Gorgimera"
    vs the column "Gorgimera") would otherwise miss once the name became "Gorgimera
    Chimera"."""
    return max(_header_score(run, m.name),
               _header_score(run, m.variant) if m.variant else 0)


#: The page's own prose section headers, normalized (see _SECTIONS).
_SECTION_HEADER_KEYS = frozenset({"combat", "habitat society", "habit society",
                                  "society habitat", "ecology"})

#: Bold prose sub-headers that are *not* a creature name — the page's own section
#: headers, dragon age categories, and psionic-discipline / table captions. Anything
#: else short enough to be a name is treated as a creature described only in prose
#: (Phase C: the Archlich on the Lich page, the Kapoacinth on the Gargoyle page).
_NON_CREATURE_HEADERS = frozenset({
    "combat", "habitat society", "habit society", "society habitat", "ecology",
    "general", "description", "psionics summary", "saving throws", "notes",
    "hatchling", "very young", "young", "juvenile", "adult", "mature adult",
    "old", "very old", "venerable", "wyrm", "great wyrm", "ancient",
    # stat-block labels and table legends bolded in the prose (the Mummy age table)
    "ac", "hd", "thac0", "to hit", "xp", "treasure", "alignment", "wisdom", "magic",
    "disease", "defense", "defenses", "languages", "fear", "intelligence", "morale",
    "movement", "size", "frequency", "organization", "diet", "armor class",
    "hit dice", "activity cycle", "magic resistance", "no appearing", "note",
    "psionics", "magical items", "leap", "venom", "related species",
    # bare rank words heading a taxonomy list (Tanar'ri: Least / Lesser / Greater)
    "least", "lesser", "greater", "true",
})
#: Substrings that mark a header as a caption/discipline rather than a creature.
_NON_CREATURE_WORDS = (
    "telepath", "clairsent", "clarsent", "psychokin", "psychometab", "psychoport",
    "metapsion", "metabolism", "science", "devotion", "common power", "attack mode",
    "defense mode", "table", "level", "breath weapon", "special bonus", "legend of",
    "saving throw",
)
#: A header opening with one of these reads as a spell/ability name, not a creature
#: ("Create Crypt Thing", "Call Phoenix").
_NON_CREATURE_VERBS = frozenset({"create", "call", "summon", "control", "cast",
                                 "detect", "cause", "animate"})


def _starts_a_line(prose_text: str, off: int) -> bool:
    """Whether the bold run at ``off`` opens a line — a real block sub-header. Bold
    used mid-sentence for emphasis ("...the **mummies** of...") is not a header, and
    must not be allowed to cut the creature's prose in half."""
    i = off - 1
    while i >= 0 and prose_text[i] in " \t":
        i -= 1
    return i < 0 or prose_text[i] == "\n"


def _is_titlecase_name(run: str) -> bool:
    """Whether every significant word is capitalized, as a creature name is in this
    book ('Black Cloud of Vengeance', 'Half-orcs'). A trailing lowercase word marks a
    sentence fragment the author merely bolded — 'Dodge missiles', 'Rrakkma bands',
    'Giant marine spiders' — which is a caption, not a creature."""
    words = [w for w in run.rstrip(":").split() if w.strip("(),")]
    return bool(words) and all(w[0].isupper() or not w[0].isalpha()
                               or _norm_header(w) in _FILLER_WORDS for w in words)


def _is_creature_header(run: str) -> bool:
    """Whether a bold prose sub-header that matched no stat column reads like a
    *creature* name (so its block is a prose-only variant) rather than one of the
    page's structural captions, stat labels, or a spell name."""
    k = _norm_header(run)
    if not k or len(k.split()) > 4 or k[0].isdigit():
        return False
    if k in _NON_CREATURE_HEADERS or k.split()[0] in _NON_CREATURE_VERBS:
        return False
    if not _is_titlecase_name(run):
        return False
    return not any(w in k for w in _NON_CREATURE_WORDS)


def _resolve_block(block, shared):
    """(description, combat, habitat, ecology) for one variant's prose block. A block
    written as one flowing paragraph (no Combat:/Habitat:/Ecology: sub-headers — the
    Gauth, a bird) stays in **Description**, its natural home; the spell parse (find_in)
    and ability parse read description too, so its mechanics still surface. ``shared``
    is the page's general sections to layer under the block's own (Naga-style pages),
    or None when the block stands alone (Beholder kin)."""
    d, c, h, e = _split_prose(block)
    if shared is not None:                       # inherit the page's shared sections
        sd, sc, sh, se = shared
        d = "\n\n".join(x for x in (sd, d) if x)
        c, h, e = c or sc, h or sh, e or se
    return d, c, h, e


def _attribute_variant_prose(monsters, prose_text, bold_runs):
    """Give each variant on a multi-creature page *its own* slice of the prose.

    The MM writes a shared page which v1 handed to every variant identically (so a
    variant's ecology was every kin's text concatenated). Where bold sub-headers name
    the variants, split at them. Two page shapes, told apart by whether any column is
    left without a header of its own:

    * **a base creature** (Beholder, Bear): its Combat/Habitat/Ecology sit before the
      first sub-header and belong to it; each kin's block stands alone.
    * **all-variant** (Naga, Cat): the leading Combat/Habitat/Ecology are *general* and
      shared by every variant, each of which then adds its own block.

    Each block takes its most-specific header ("Lamia Noble" heads the Noble, not the
    base "Lamia"). A no-op when nothing matches (single creatures, shared-description
    pages), so those stay untouched."""
    if not monsters or not bold_runs:
        return
    # Each header goes to the variant(s) it matches best (an exact match wins the header
    # outright; otherwise every equally-good family member shares it — "Abishai" heads
    # all three abishai). Each variant then keeps its highest-scoring header. A header
    # that names no column but reads like a creature is a **prose-only variant**: it
    # still bounds the blocks (so it can't bleed into the creature above it) and is
    # captured as a related creature.
    assigned, orphans = {}, []         # index -> (offset, run, score); [(offset, run)]
    for off, run in bold_runs:
        if run.lstrip().startswith("("):        # a "(beholder-kin)" annotation, not a header
            continue
        scored = [(i, _match_score(run, m)) for i, m in enumerate(monsters)]
        best = max((s for _, s in scored), default=0)
        if best == 0:
            if _is_creature_header(run) and _starts_a_line(prose_text, off):
                orphans.append((off, run))
            continue
        for i, s in scored:
            if s == best and (i not in assigned or best > assigned[i][2]):
                assigned[i] = (off, run, best)
    if not assigned and not orphans:
        return

    boundaries = sorted({off for off, _, _ in assigned.values()} | {off for off, _ in orphans})
    section_offs = sorted(off for off, run in bold_runs
                          if _norm_header(run) in _SECTION_HEADER_KEYS)

    # A prose-only creature is a short blurb — it never owns Combat:/Habitat:/Ecology:
    # sections. So its block stops at the next section header, and that text goes back
    # to the page level (the Slaad's shared Habitat/Ecology sit *after* the Green/Gray/
    # Death Slaad blurbs and belong to every slaad, not to the Death Slaad).
    page_level = []

    def block_at(off, run, is_orphan=False):
        end = next((b for b in boundaries if b > off), len(prose_text))
        if is_orphan:
            cut = next((s for s in section_offs if s > off), None)
            if cut is not None and cut < end:
                page_level.append((cut, end))
                end = cut
        block = prose_text[off:end]
        if block.lower().lstrip().startswith(run.lower()):            # drop the header line
            block = block.lstrip()[len(run):]
        return re.sub(r"^\s*\([^)]*\)", "", block).lstrip(" :\n")      # and a "(kin)" tag

    related = [{"name": run.rstrip(":").strip(),
                "text": _clean_prose(block_at(off, run, is_orphan=True))}
               for off, run in orphans]
    related = [r for r in related if r["text"]]

    base_text = prose_text[:boundaries[0]] + "".join(
        "\n" + prose_text[a:b] for a, b in sorted(page_level))
    base_split = _split_prose(base_text)
    # a base creature exists iff some column has no header; then the leading sections
    # are its own, not shared. Otherwise they're general and every variant inherits them.
    shared = None if any(i not in assigned for i in range(len(monsters))) else base_split

    for i, m in enumerate(monsters):
        if i in assigned:
            off, run, _ = assigned[i]
            fields = _resolve_block(block_at(off, run), shared)
        else:
            fields = base_split        # the base creature (no header of its own)
        if any(f.strip() for f in fields):     # never blank out a variant we can't place
            m.description, m.combat, m.habitat_society, m.ecology = fields
        m.related_creatures = related


class _StatBlockHTML(HTMLParser):
    """Reads each <TABLE> as its own grid of cell strings (column 0 = label,
    columns 1..N = one per variant) and collects the body text outside the tables
    as prose. ``self.tables`` keeps the tables *separate* — so parse_stat_block can
    route the leading stat-block table(s) to the grid parser and hand the trailing
    enrichment tables (dragon age charts, psionics summaries, per-attack damage) to
    the classifier — while ``self.rows`` still exposes them concatenated for the
    stat-block path. A page may split the variant-name header into its own table
    (Crocodile) or spread the stat block across several (Dinosaur, Tabaxi); those
    stay together because the stat-block region is every table up to the last one
    bearing a canonical label. Wrapped values arrive as continuation rows (empty
    first cell), stitched back per column by _group_to_monsters."""

    def __init__(self):
        super().__init__()
        self.tables: list = []
        self._table = None
        self._row = None
        self._cell = None
        self._in_table = False
        self._seen_table = False
        self._prose: list = []
        self.image = ""
        #: (char offset in prose(), text) for each <B>/<I> run in the prose region —
        #: the per-variant sub-headers ("Death Kiss", "Gauth") that let a page's prose
        #: be split per creature (see _attribute_variant_prose).
        self.bold_runs: list = []
        self._bold = False
        self._bold_buf: list = []
        self._bold_at = 0
        self._plen = 0                 # running length of prose(), for the offsets

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "img" and not self.image:
            self.image = dict(attrs).get("src", "") or ""
        if t == "table":
            self._in_table = self._seen_table = True
            self._table = []
        elif self._in_table:
            if t == "tr":
                self._row = []
            elif t == "td" and self._row is not None:
                self._cell = []
            elif t == "br" and self._cell is not None:
                self._cell.append(" ")
        elif self._seen_table:                       # prose region (outside any table)
            if t in ("br", "p"):
                self._prose.append("\n")
                self._plen += 1
            elif t in ("b", "strong"):
                self._bold, self._bold_buf, self._bold_at = True, [], self._plen

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        t = tag.lower()
        if t == "table":
            if self._table:
                self.tables.append(self._table)
            self._in_table = False
            self._table = self._cell = self._row = None
        elif self._in_table:
            if t == "td" and self._cell is not None:
                self._row.append(" ".join("".join(self._cell).split()))
                self._cell = None
            elif t == "tr" and self._row is not None:
                self._table.append(self._row)
                self._row = None
        elif self._bold and t in ("b", "strong"):
            run = " ".join("".join(self._bold_buf).split())
            if run:
                self.bold_runs.append((self._bold_at, run))
            self._bold = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._seen_table and not self._in_table:
            self._prose.append(data)
            self._plen += len(data)
            if self._bold:
                self._bold_buf.append(data)

    @property
    def rows(self) -> list:
        """Every table's rows concatenated — the flat grid the stat-block and
        compact-table parsers consume."""
        return [r for t in self.tables for r in t]

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
    body_width = 0                  # value columns the labelled stat rows actually use
    in_block = True                 # still inside the stat block (vs a trailing sub-table)
    for row in rows:
        row = row + [""] * (ncol - len(row))
        first, vals = row[0].strip(), row[1:]
        canon = _norm_label(first)
        if canon:
            stat_fields.append([canon, list(vals)])
            seen_label = in_block = True
            last = max((i for i, v in enumerate(vals) if v.strip()), default=-1)
            body_width = max(body_width, last + 1)
        elif not first:                       # header (before labels) or continuation
            if not seen_label:
                target = variant_cols          # variant-name header, above the labels
            elif in_block and not any(v.strip() for v in vals[max(body_width, 1):]):
                target = stat_fields[-1][1] if stat_fields else None  # a wrapped value
            else:
                target, in_block = None, False  # a trailing sub-table (dragon age chart)
            if target is not None:
                for i, v in enumerate(vals):
                    if v:
                        target[i] = (target[i] + " " + v).strip()
                        if target is variant_cols:
                            have_variants = True
        elif seen_label:
            in_block = False                   # a non-label data row ends the stat block

    if not any(c == "ARMOR CLASS" for c, _ in stat_fields):
        return []                              # not a real stat block

    field_map = {FIELD_BY_LABEL[c]: v for c, v in stat_fields}
    # a group's real columns are those with a variant name (multi-variant) — the
    # single lone column otherwise. Unnamed trailing columns are padding.
    cols = [i for i in range(ncol - 1) if variant_cols[i].strip()] if have_variants else [0]

    monsters = []
    for i in cols:
        variant = _dehyphenate(variant_cols[i].strip()) if have_variants else ""
        m = Monster(
            name=_resolve_name(source_page, variant, group),
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


def _dehyphenate(name: str) -> str:
    """Rejoin a soft line-break hyphen in a scraped name: the MM wraps long variant
    names with a hyphen + <br>, which arrives as 'letter- space letter' ('Ankylo-
    saurus', 'Amphis- baena'). A *real* hyphenated name ('Beholder-kin') has no space
    after the hyphen, so only the spaced form is a wrap to close up."""
    return re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", name)


def _clean_title(title: str) -> str:
    """The monster/group name from a page title: drop the ' (Monstrous Manual)'
    suffix and render the scrape's '--' separator as a comma ('Cat-- Great')."""
    base = re.split(r"\s*\(Monstrous Manual", title or "")[0].strip()
    return re.sub(r"\s*--\s*", ", ", base)


#: Public alias — app.py names a page's group from its title (the picker headings).
clean_title = _clean_title


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


#: Curated naming for multi-variant pages the automatic rule gets wrong (its
#: adjective-vs-full-name guess, keyed off the '--' title separator, misfires when a
#: page mixes the two — 'Basilisk' lists the adjectives Lesser/Greater *and* the name
#: Dracolisk). Keyed by source page. A value is one of:
#:   _ALONE       — every variant is already a full creature name; use it verbatim.
#:   "<Noun>"     — every variant is an adjective; prefix this base noun ('Fire' →
#:                  'Fire Beetle'). Skipped for a variant that already contains it.
#:   {variant: name} — explicit names for the listed variants (a mixed page); any
#:                  variant not listed falls back to the automatic rule.
_ALONE = object()
NAME_OVERRIDES = {
    # full-name variants the rule wrongly prefixes with the base noun
    "MM/DD03801.htm": _ALONE,   # Baatezu:  Pit Fiend, Black Abishai, …
    "MM/DD03835.htm": _ALONE,   # Dinosaur: Ankylosaurus, Deinonychus, …
    "MM/DD03883.htm": _ALONE,   # Elephant: Elephant (African), Mammoth, Mastodon, …
    "MM/DD03896.htm": _ALONE,   # Genie:    Djinni, Dao, Efreeti, Marid, Jann
    "MM/DD03936.htm": _ALONE,   # Gremlin:  Gremlin, Fremlin, Galltrit, Mite, Snyad
    "MM/DD03959.htm": _ALONE,   # Insect Swarm: Velvet Ants, Grasshoppers and Locusts
    "MM/DD04069.htm": _ALONE,   # Tanar'ri: Balor, Marilith
    # adjective variants the rule wrongly leaves bare (its title has a comma / "kin")
    "MM/DD03806.htm": "Beetle",   # Beetle, Giant:  Fire → Fire Beetle
    "MM/DD03819.htm": "Cat",      # Cat, Small:     Domestic → Domestic Cat
    "MM/DD03873.htm": "Dwarf",    # Dwarf, Hill and Mountain: Hill → Hill Dwarf
    "MM/DD03876.htm": "Elemental",  # Elemental, Air/Earth
    "MM/DD03877.htm": "Elemental",  # Elemental, Fire/Water
    "MM/DD03928.htm": "Golem",    # Golem, Greater:  Stone → Stone Golem
    "MM/DD03929.htm": "Golem",    # Golem, Lesser:   Flesh → Flesh Golem
    "MM/DD03930.htm": "Golem",    # Golem, Bone, Doll
    "MM/DD03931.htm": "Golem",    # Golem, Gargoyle, Glass
    "MM/DD03957.htm": "Mephit",   # Imp, Mephit:     Fire → Fire Mephit
    "MM/DD03981.htm": "Seawolf",  # Lycanthrope, Seawolf: Lesser → Lesser Seawolf
    "MM/DD04034.htm": "Pudding",  # Pudding, Deadly: Black → Black Pudding
    "MM/DD04097.htm": "Guardian",  # Yugoloth, Guardian: Least → Least Guardian
    # mixed pages: name the outliers, leave the rest to the automatic rule
    "MM/DD03803.htm": {"Dracolisk": "Dracolisk"},                       # Basilisk
    "MM/DD03813.htm": {"Killmoulis": "Killmoulis"},                     # Brownie
    "MM/DD03823.htm": {"Megalo-": "Megalocentipede"},                   # Centipede
    "MM/DD03824.htm": {"Gorgimera": "Gorgimera"},                       # Chimera
    "MM/DD03826.htm": {"Pyrolisk": "Pyrolisk"},                         # Cockatrice
    "MM/DD03892.htm": {"Shrieker": "Shrieker", "Phycomid": "Phycomid",  # Fungus
                       "Ascomoid": "Ascomoid", "Gas spore": "Gas Spore"},
    "MM/DD03895.htm": {"Margoyle": "Margoyle"},                         # Gargoyle
    "MM/DD03898.htm": {"Lacedon": "Lacedon", "Ghast": "Ghast"},         # Ghoul
    "MM/DD03922.htm": {"Moth": "Gloomwing", "Tenebrous Worm": "Tenebrous Worm"},  # Gloomwing
    "MM/DD03923.htm": {"Flind": "Flind"},                               # Gnoll
    "MM/DD03924.htm": {"Svirfneblin": "Svirfneblin"},                   # Gnome
    "MM/DD03953.htm": {"Draft": "Draft Horse", "Heavy": "Heavy Horse",  # Horses
                       "Medium": "Medium Horse", "Light": "Light Horse",
                       "Riding": "Riding Horse", "Wild": "Wild Horse",
                       "Pony": "Pony", "Mule": "Mule"},
    "MM/DD03956.htm": {"Quasit": "Quasit"},                            # Imp
    "MM/DD03967.htm": {"Urd": "Urd"},                                  # Kobold
    "MM/DD03977.htm": {"Lizard King": "Lizard King"},                  # Lizard Man
    "MM/DD03979.htm": {"Trapper": "Trapper", "Trapper, Forest": "Forest Trapper"},  # Lurker
    "MM/DD04014.htm": {"Great Old Master": "Great Old Master"},        # Neogi
    "MM/DD04018.htm": {"Merrow": "Merrow"},                            # Ogre
    "MM/DD04023.htm": {"Orog": "Orog"},                                # Orc
    "MM/DD04031.htm": {"Thorn- Slinger": "Thornslinger"},             # Plant, Dangerous
    "MM/DD04037.htm": {"Osquip": "Osquip"},                            # Rat
    "MM/DD04044.htm": {"Korred": "Korred"},                            # Satyr
    "MM/DD04056.htm": {"Amphisbaena": "Amphisbaena", "Boalisk": "Boalisk",  # Snake
                       "Constrictor (Normal)": "Constrictor Snake (Normal)",
                       "Constrictor (Giant)": "Constrictor Snake (Giant)",
                       "Heway": "Heway", "Spitting": "Spitting Snake",
                       "Poison (Normal)": "Poison Snake (Normal)",
                       "Poison (Giant)": "Poison Snake (Giant)",
                       "Sea, Giant": "Giant Sea Snake"},
    "MM/DD04061.htm": {"Pixie": "Pixie", "Nixie": "Nixie",             # Sprite
                       "Atomie": "Atomie", "Grig": "Grig"},
    "MM/DD04066.htm": {"Bird Maidens": "Bird Maidens"},               # Swanmay
    "MM/DD04080.htm": {"Vodyanoi": "Vodyanoi"},                       # Umber Hulk
    "MM/DD04085.htm": {"Narwhal": "Narwhal", "Leviathan": "Leviathan"},  # Whale
    "MM/DD04088.htm": {"Worg": "Worg"},                              # Wolf
    "MM/DD04090.htm": {"Rot Grub": "Rot Grub"},                      # Worm
    "MM/DD04093.htm": {"Xaren": "Xaren"},                            # Xorn
}


def _resolve_name(source_page: str, variant: str, group: str) -> str:
    """A variant's display name, consulting NAME_OVERRIDES before the automatic rule."""
    ov = NAME_OVERRIDES.get(source_page)
    if isinstance(ov, dict):
        if variant in ov:
            return ov[variant]
    elif ov is _ALONE:
        return variant or group
    elif isinstance(ov, str) and variant:
        return variant if ov.lower() in variant.lower() else f"{variant} {ov}"
    return _monster_name(variant, group)


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
    ac_col = next(c for c, f in field_by_col.items() if f == "armor_class")
    hd_col = next(c for c, f in field_by_col.items() if f == "hit_dice")

    def cell(row, col):
        return row[col].strip() if col < len(row) else ""

    monsters = []
    current = None
    just_started = False           # did the previous row begin (or continue naming) a creature?
    for row in rows[1:]:
        name, has_ac, has_hd = (row[0].strip() if row else ""), cell(row, ac_col), cell(row, hd_col)
        if not name:                                       # an HD-conditional tail row
            just_started = False
            continue
        if not has_ac and not has_hd:                      # a bare name with no stats of its own
            if just_started and current:                   # a name that wrapped ("Catfish,"+"Giant")
                current.name = (current.name + " " + name).strip()
            continue                                        # else a sub-category header (termite castes)
        if not (has_ac and has_hd
                and re.search(r"\d", has_hd) and re.search(r"[A-Za-z]", name)):
            just_started = False
            continue                                        # cross-refs, spell / psionics sub-tables
        current = Monster(name=name, source_page=source_page)
        for col, field in field_by_col.items():
            if col < len(row):
                setattr(current, field, row[col].strip())
        monsters.append(current)
        just_started = True
    return monsters


def _split_stat_and_trailing(tables):
    """Partition the page's parsed tables into (stat_block_rows, trailing_tables).

    The stat block spans every table up to and including the last one bearing a
    canonical stat label — leading variant-name headers (Crocodile) and cosmetically
    split stat tables (Dinosaur, Shedu, Tabaxi) come along, so the grid parser sees
    exactly the flat grid it saw before. Everything after the last label-bearing
    table is an enrichment table for the classifier (dragon age charts, psionics,
    per-attack damage). If no table carries a canonical label the page is a compact
    summary (Mammal, Bird, …), handled on the whole flattened grid instead."""
    last_label = -1
    for i, t in enumerate(tables):
        if any(r and _norm_label(r[0].strip()) for r in t):
            last_label = i
    if last_label < 0:
        return [], []
    stat_rows = [r for t in tables[:last_label + 1] for r in t]
    return stat_rows, tables[last_label + 1:]


def parse_stat_block(content_html: str, title: str = "", source_page: str = "") -> list:
    """Parse a Monstrous Manual page into a list of Monsters — one per variant (a
    single-creature page yields one). Falls back to the compact summary-table format
    (Mammal, Bird, …). Returns [] for pages without a real stat block (front matter,
    generic category pages, the blank form).

    Enrichment tables the page carries past the stat block (dragon age progression,
    psionics summaries, per-attack damage) are classified and attached to every
    monster on the page as ``extra_tables`` (Phase A of the monster v2 plan)."""
    parser = _StatBlockHTML()
    try:
        parser.feed(content_html or "")
    except Exception:
        return []
    stat_rows, trailing = _split_stat_and_trailing(parser.tables)
    monsters = _grid_to_monsters(stat_rows, _clean_title(title), source_page, parser.prose())
    if not monsters:
        # compact summary tables filter their own junk rows, so feed them the whole
        # flattened grid (the trailing-table split doesn't apply to them).
        monsters = _parse_compact_table(parser.rows, source_page)
        trailing = []
    _attribute_variant_prose(monsters, parser.prose(), parser.bold_runs)
    extras = classify_tables(trailing)
    for m in monsters:
        m.image = parser.image
        m.extra_tables = extras
    return monsters


# ── enrichment-table classifier (Phase A) ─────────────────────────────────────
#
# Past the stat block, ~73 MM pages carry extra <table>s the v1 parser dropped. Each
# is classified off its header row(s) into a structured extra attached to the
# Monster (rendered as its own sheet section, consumed by Phase B's tier selector):
#   age           dragon age progression (Age -> HD/size, AC, breath, spells, XP)
#   psionics      psionics summary (Level | Dis/Sci/Dev | Attack/Defense | Score | PSPs)
#   attack_damage per-attack damage breakdown (Baatezu/Tanar'ri: Attack | Damage rows)
#   other         anything else the page carries (kept so nothing is silently lost)
# Each extra is a plain JSON-friendly dict — {kind, title, header_rows, rows} — so it
# roundtrips through Monster.to_dict/from_dict without bespoke (de)serialization.

#: Header cells that mark an Age-keyed table as a *combat* progression (Phase B feed)
#: rather than an age→lore note table ("Age | Ability").
_AGE_COMBAT_COLS = ("ac", "hd", "thac0", "breath", "xp", "weapon", "lgt", "spells")


def _normalize_grid(rows):
    """Drop blank rows and any leading columns that are empty in every row, padding
    ragged rows to a common width. Leaves a rectangular grid the classifier and the
    view can read by column (folds away the stray leading spacer column some tables
    carry — Crystal Dragon's psionics, the Beholder hit-location charts)."""
    rows = [list(r) for r in rows if any(c.strip() for c in r)]
    if not rows:
        return rows
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    while width > 1 and all(not r[0].strip() for r in rows):
        rows = [r[1:] for r in rows]
        width -= 1
    return rows


def _age_header_rows(rows):
    """How many leading rows form an Age-progression header (0 if it isn't one): the
    dragon charts wrap it across two rows ('' / 'Age'), the White-Dragon/Mummy form
    keeps it on one ('Age')."""
    if rows and rows[0] and rows[0][0].strip().lower() == "age":
        return 1
    if len(rows) > 1 and rows[1] and rows[1][0].strip().lower() == "age":
        return 2
    return 0


def _is_age_table(rows):
    hr = _age_header_rows(rows)
    if not hr:
        return False
    header = " ".join(c.lower() for r in rows[:hr] for c in r)
    return any(col in header for col in _AGE_COMBAT_COLS)


def _is_psionics_table(rows):
    cells = [c.strip().lower() for r in rows[:2] for c in r]
    has_level = any(c == "level" for c in cells)
    has_psp = any("psp" in c or "dis/sci" in c for c in cells)
    return has_level and has_psp


def _psionics_header_rows(rows):
    """Psionics headers usually sit on one row; a few wrap the column names onto a
    second ('Level | Dis/Sci | Attack/ | Power | PSPs' then '' | Dev | Defense |
    Score | ''). A following row with no digits and no '=' (i.e. not a data row,
    whose Power Score reads '= Int' or a level number) is that continuation."""
    if len(rows) > 1:
        r1 = [c.strip() for c in rows[1]]
        if (any(c for c in r1[1:]) and not any(re.search(r"\d", c) for c in r1)
                and not any("=" in c for c in r1)):
            return 2
    return 1


def _is_attack_damage_table(rows):
    header = {c.strip().lower() for c in rows[0] if c.strip()}
    return bool(header) and header <= {"attack", "damage"} and "damage" in header


def _classify_table(table):
    """Classify one trailing <table> into a structured extra ({kind, title,
    header_rows, rows}), or None if it holds nothing. Recognizes the three shapes
    the MM repeats and keeps everything else as ``other`` so the page's content
    isn't lost."""
    rows = _normalize_grid(table)
    if not rows:
        return None
    if _is_attack_damage_table(rows):
        kind, header_rows = "attack_damage", 1
    elif _is_psionics_table(rows):
        kind, header_rows = "psionics", _psionics_header_rows(rows)
    elif _is_age_table(rows):
        kind, header_rows = "age", _age_header_rows(rows)
    else:
        kind, header_rows = "other", 1
    return {"kind": kind, "header_rows": header_rows, "rows": rows}


def classify_tables(tables):
    """Classify each trailing table, dropping the empties. The order the page lists
    them in is preserved."""
    return [c for c in (_classify_table(t) for t in tables) if c]

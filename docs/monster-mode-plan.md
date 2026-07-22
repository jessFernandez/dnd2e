# Monster mode — plan

**Status:** v1 complete and merged (PR #11) — phases 1 (pure core), 2 (persistence),
3 (view) and 4 (UI wiring), then a creature-by-creature data audit + a pre-v2
code-health pass (model/parser split). **v2 complete**: phases A (enrichment tables),
B (HD/age tiers), C (prose mining) and D (spell cross-linking), plus the Roll20
monster export — then a **post-v2 correctness audit** (below) that fixed four defects
and moved the `mon/` link grammar into `navigation.py`. No in-app encounter tracker —
Roll20 runs the encounter. **v3** (a dedicated Roll20 monster sheet) is not started.

## Goal

A **monster** sheet mode alongside the PC character sheet: a full AD&D 2e stat
block a DM can use at the table, importable from the Monstrous Manual already in
`dnd2e.db`. Campaign house rules apply — the sheet shows the converted attack
bonus and ascending AC (via `char_rules`), and a size-derived initiative speed
factor.

## The data (verified against `dnd2e.db`)

The MM lives as scraped pages in the `pages` table (`book_code='MM'`, ~330 pages,
~295 with a real stat block; the rest are front-matter / generic category pages).
Each monster's `content_text` is highly regular:

- A **fixed 21-label stat block** (`CLIMATE/TERRAIN` … `XP VALUE`) as `LABEL:` /
  value lines, in order — with a few OCR/spacing variants to normalize
  (`DAMAGE/ATTACKS`, `CLIMATE/ TERRAIN`, `ACTIVE TIME`→ activity cycle, `THACO`→
  `THAC0`, …).
- **Multi-variant pages** (Bear → Black/Brown/Cave/Polar) list the variant names
  after the title, then give *N* values per label (one per variant).
- **Prose** after the block, split by `Combat:` / `Habitat/Society:` / `Ecology:`
  (dragon age-tiers etc. fold into the description).

So import is a **parse job** (plain-Python, no `bs4` at runtime), like
`build_items.py` — not manual entry.

## House rules baked in

- **THAC0 → attack bonus** and **descending → ascending AC** reuse
  `char_rules` (`thac0_to_bonus`, `desc_to_asc`) — never reimplemented. Applied
  to the numeric parts of the stat strings (ranges like `THAC0 17-13` and
  `AC "Overall 2, underside 4"` convert each number in place).
- **Initiative speed factor** is **size-based**, per the campaign's own DM Screen
  table (`Tiny 0 · Small/Medium +3 · Large +6 · Huge +9 · Gargantuan +12`). That
  table moves into `char_rules` as the single source of truth; the DM Screen and
  the monster sheet both read it. Derived from the parsed Size, shown as an
  **editable** field (override for weapon-wielders).

## Architecture (parallel to the PC stack, same layering)

| Concern | Module | Qt-free? |
|---|---|---|
| Stat-block model + house-rule derivations | `monster.py` | ✅ |
| MM page parser + naming (`parse_stat_block`, `importable_index`) | `monster_parser.py` | ✅ |
| Persistence (save/load to user DB) | `monster_library.py` | ✅ |
| Sheet view (render + edit) | `monster_html.py` | ✅ |
| Monster mode + MM import picker | `app.py` (thin) | Qt |

The model (`monster.py`) and the parser (`monster_parser.py`) were split apart in
the pre-v2 audit — the parser is the larger, fiddlier layer and absorbs the churn
of new source formats, so keeping the model small and stable mirrors the
`char_rules`/`character` split. `monster_parser` imports `Monster`, not the reverse.

## Phases (each ships green, logic-first)

1. **Pure core. ✅ done.** `char_rules` size→initiative table + helper (DM Screen
   repointed at it); `monster.py` `Monster` model + `parse_stat_block()`; `db.py`
   `list_monster_pages`. The parser reads the **content_html table** (not the text,
   which flattens multi-column variants) with a stdlib `html.parser`; it handles
   single monsters, multi-variant columns, wrapped values (continuation rows),
   variant headers in a separate table, and **multiple stat-block groups per page**
   (Cat, Great = 9 cats; Spider = 7). All 293 real MM monsters parse cleanly
   (`test_monster.py`, incl. a corpus smoke test); the 7 generic category pages
   correctly yield nothing.

   *Known limitation:* HD-conditional THAC0/XP strings (`"3+3 HD: 17 4+4 HD: 15"`)
   make the derived attack-bonus imperfect — the verbatim value is always stored;
   refine in the view phase.
2. **Persistence. ✅ done.** `monster_library.MonsterLibrary` (save/load/delete
   monsters as JSON blobs in the user DB, mirroring `character_library`) over new
   `db.py` `saved_monsters` CRUD. The row id is held by the caller, keeping the
   `Monster` model persistence-free. Tested against a temp DB (`test_monster_library`).
3. **View. ✅ done.** `monster_html.generate(m, saved_id)` renders the sheet in the
   app's dark-navy/gold system: a house-rule combat strip (attack bonus, ascending
   AC, initiative, HD, attacks, damage), the editable 21-field stat block with
   derived house-rule badges beside AC/THAC0/Size, and the prose with **Combat as a
   first-class feature panel**. Edits/actions use the `dnd:///mon/…` convention
   (mirroring `cm`/`cmText`), wired in phase 4. Render tests in `test_monster_html`;
   flex-gap guard kept green (grid gap + child margins, per the QtWebEngine bug).
4. **UI wiring. ✅ done.** A `monster` full-width screen + a 🐉 rail button; the
   `dnd:///mon/…` route (`navigation.MonAction`) dispatched to `_mon_action`
   (set/import/new/save/pick/pickvar/load/delete); the import picker (client-side
   filtered) with a variant sub-picker for multi-creature pages, and a saved-monster
   list. Field edits store in place (AC/THAC0 invert back via `house_rule_to_raw`)
   without a re-render, so focus/scroll survive; derived tiles refresh on the next
   full render. Covered by SimpleNamespace wiring tests plus a real-DB end-to-end
   (pick → variant → sheet → save → load). `monster*` modules registered in
   `dnd2e.spec`.

## Special attacks & abilities — v1 handling

Captured in two layers, **no structured/rollable data**:

- the terse `special_attacks` / `special_defenses` stat fields (verbatim), and
- the `Combat:` prose, which holds the actual mechanics (range, damage, save,
  frequency).

This matters because **~30% of `special_attacks` values are just "See below"** —
the stat field is a pointer, and the Combat prose is the real content. So the
sheet (phase 3) must render **Combat as first-class functional text beside the
stat block**, not as flavor. That gives a fully runnable monster without a brittle
parse of the prose.

## v2 — deeper monster data

v1 gives a **complete, accurate, editable** stat block (audited creature-by-creature:
634 creatures, curated naming, house-rule numbers). v2 pulls in everything the MM
page carries that v1 leaves behind — the **embedded tables the parser discards**, the
**mechanics and extra creatures buried in prose** — and makes **HD/age-scaling
monsters interactive**. There is no live encounter tracker: **Roll20 runs the
encounter**; v2's job is to make each imported monster as complete as its MM page and
export-ready. Phases are sequenced by dependency (A feeds B); each ships green, logic
in a pure module, parser churn in `monster_parser.py`, new structured data on the
`Monster` model.

### Phase A — Parse & categorize every embedded table. ✅ done.

**73 importable pages carry tables beyond the stat block** that the parser used to
drop (it stopped at the first trailing sub-table — the "Variable Body" fix). Phase A
classifies each `<table>` and attaches the useful ones to the Monster as structured
data:

*Shipped:* `_StatBlockHTML` now keeps tables separate (`self.tables`, with a `.rows`
concatenation kept for the stat-block/compact paths). `parse_stat_block` splits the
page at the **last table bearing a canonical stat label** — everything before is the
stat block (leading variant headers and cosmetically split blocks come along, so the
grid parser sees the same flat grid as v1), everything after is a trailing enrichment
table. A `classify_tables` classifier keys off each trailing table's header row(s)
into `age` / `psionics` / `attack_damage` / `other` (nothing dropped), each stored as
a plain `{kind, header_rows, rows}` dict on `Monster.extra_tables` (JSON-roundtrips via
`to_dict`/`from_dict`; multi-variant pages attach the page's tables to every variant).
`monster_html` renders them as an **Additional Tables** section. Across the corpus: 60
pages carry trailing tables (88 total — 24 age, 22 psionics, 2 attack_damage, 40
other); the other 13 of the 73 are cosmetic multi-`<table>` stat blocks that stay in
the stat-block region. Covered by classifier unit tests + real-DB captures (Black
Dragon age, Aboleth psionics, Baatezu per-attack) in `test_monster*.py`.

*Deferred to Phase B/C:* deep parsing of the captured grids (age → tiers; psionics →
fields); a few known-shape gaps left as `other` for now (Thri-kreen life-stage
advancement, the Baatezu taxonomy list). The parse-cache code-health item (below) is
still worth doing before the parse gets heavier.

Original categories:

- **Age-progression** (every dragon: Age → HD/size, AC, breath weapon,
  Wizard/Priest spells, MR, treasure, XP) — the scaling data Phase B consumes.
- **Psionics summary** (Level · Disciplines/Sciences/Devotions · Attack/Defense
  modes · Power Score · PSPs) — Githyanki, Githzerai, Shedu, gem dragons, …
- **Per-attack damage breakdown** (Baatezu: Attack | Damage rows).
- **Random / advancement tables** (encounter or class-level rolls) — capture or
  skip per category; lowest value.

A table classifier in `monster_parser` (keyed off each table's header row), optional
structured fields on `Monster`, rendered as their own sheet sections.

#### Phase A — implementation notes (start here)

Tacit knowledge from the pre-v2 audit, so this doesn't get re-derived:

- **The parser has no table boundaries today.** `_StatBlockHTML` concatenates *every*
  `<table>` on the page into one flat `self.rows` list — there is no marker for where
  one table ends and the next begins. So **step 1 of Phase A is structural**: make
  `_StatBlockHTML` keep tables separate (e.g. `self.tables: list[list[row]]`, or push
  a boundary sentinel), then classify each table. Everything downstream
  (`_segment_groups`, `_group_to_monsters`, `_parse_compact_table`) currently assumes
  the merged list — keep the stat-block path working off the *first* table(s) while
  the classifier routes the trailing ones.
- **Two regression tests will change on purpose.**
  `test_trailing_wide_subtable_does_not_bleed_into_last_stat` and
  `test_trailing_two_column_subtable_after_a_data_row_is_ignored` currently assert the
  age/ability sub-tables are *ignored*. Phase A **retains** them — so update those to
  assert the table is now *captured* (as `age_tiers`/etc.) **and still doesn't
  contaminate XP** (`xp_value == "Variable"`). Don't just delete them; the
  no-contamination half is the important invariant.
- **Table shapes seen in the DB** (for the classifier's header match):
  - *Age-progression* has a **two-row header** — row 1: `Body | Tail | | Breath |
    Spells | | Treas. | XP`; row 2: `Age | Lgt. (') | Lgt. (') | AC | Weapon |
    Wizard/Priest | MR | Type | Value`. Data rows have a non-empty first cell (`1`,
    `2`, … or `1 Hatchling`, `2 Very Young`, …).
  - *Psionics summary*: header `Level | Dis/Sci/Dev | Attack/Defense | Score | PSPs`,
    one data row (the creature's psionic profile).
  - *Per-attack damage* (Baatezu): header `Attack | Damage | Attack | Damage`.
- **`parse_stat_block` runs 3× per pick** (see the parse-cache code-health item) — if
  Phase A makes parsing heavier, do that cache first.
- **Recon**: 73 importable pages have >1 table; enumerate them with a small
  `HTMLParser` that counts `<table>` (see the audit script pattern), then dump each
  extra table's first row to bucket the categories before coding the classifier.

### Phase B — Selectable HD / age scaling (flagship). 🚧 core shipped.

Many monsters scale by Hit Dice or age; make that **interactive** instead of a static
low-end value. Model a monster's **tiers** — each HD value or named age category
carrying its own AC, attack bonus, HD/HP, damage, breath, XP — and put a **selector**
(HD or age dropdown) on the sheet that recomputes the house-rule combat strip and
stat block live for the chosen tier. Sources:

- dragon age tables (Phase A);
- HD-conditional strings already in the data — compact tables ("8 HD: 13 / 9-10 HD:
  11") and standard blocks ("3+3 HD: 17 4+4 HD: 15"), parsed into tiers.

This subsumes the old "refine HD-conditional derivations": with tiers, the attack
bonus is right per HD/age rather than the base-only approximation v1 shows.

**Shipped (the core vertical slice):** a pure, Qt-free **`monster_tiers.py`** (`Tier`,
`tiers(m)`, `apply_tier`, `active_monster`) — imports `Monster` like the parser does,
keeping the model small. It derives tiers from both sources: the captured `age`
extra_tables (columns mapped to fields by header — AC/MR/Treasure/XP for dragons,
AC/HD/THAC0 for the Mummy's age chart) and HD-/hp-conditional THAC0/XP strings (parsed
by the `<unit>: <value>` grammar; ≥2 steps or it's just the base value). `Monster`
gains a persisted `selected_tier` index; `monster_html` renders a **Scaling** dropdown
(Base + each tier) that navigates `dnd:///mon/tier/<i>`, wired through `app.py`'s
`_mon_set_tier`. The combat strip and stat block render scaled to the chosen tier;
a tiered view is **read-only** (editing lands on the base, so the DM picks "Base" to
change values). 66 creatures get tiers (24 age, 42 HD-conditional). Covered by
`test_monster_tiers.py`, view tests, wiring tests, and real-DB end-to-ends (Black
Dragon AC/XP, Mummy attack-bonus 9→13, Argos HD-conditional).

**Phase B polish:**

- ✅ **Breath-weapon scaling.** `Monster.breath_weapon` field; the age table's Breath
  column maps into each tier (monster_tiers), so selecting a dragon age shows a
  **Breath** tile in the combat strip and exports a breath weapon row to Roll20 (Black
  Dragon: Age 1 → 2d4+1, Age 12 → 24d4+12).
- ✅ **Editable initiative override.** An `init-ov` control on the Size row sets
  `Monster.initiative_override` (blank falls back to the size-derived factor); the
  combat-strip Initiative tile follows.
- **Still open — Dragon HD/THAC0 don't scale by age.** The per-type age chart omits
  them (they live in the general dragon rules), so dragon tiers move AC/breath/MR/
  Treasure/XP but not HD/THAC0. Would need the general-dragon HD-by-age table (a
  `Dragon-- General` page currently skipped as a category page).
- **Still open — a tiered stat block is preview-only.** While a tier is selected the
  stat block is read-only (edits would clobber the base); per-tier editing isn't
  modeled.

### Phase C — Close prose examination → variants & abilities

A page-by-page read of the prose (like the v1 data audit) to surface what the stat
block omits — some of this is manual triage, some parser work:

- **Prose-only variants** — creatures described only in text, with no stat column
  (the Baatezu page's stat block has 4, but its prose names gelugon, lemure,
  nupperibo, spinagon). Promote them to importable variants where the prose carries
  enough stats; link-note them where it doesn't.
- **Special attacks/defenses buried in Combat prose** — tag saves ("save vs.
  poison", "-2 penalty"), damage dice, and a fixed vocabulary of ability *types*
  (breath, gaze, poison, level drain, regeneration, paralysis) as chips on the Combat
  panel; promote to structured fields (name · save · damage · range · frequency)
  where the pattern is clean. The verbatim prose stays the source of truth.

#### Phase C — findings from the prose recon (measured against `dnd2e.db`)

A corpus read (634 creatures / 297 pages) before coding, to size each sub-goal:

- **The "See below" pointer problem is real and prose-backed.** 182/634
  `special_attacks` are pointers ("See below" / "Special"), 189 empty/nil, 263
  substantive; `special_defenses`: 161 pointers, 287 empty/nil, 186 substantive. **89%
  of the pointers have non-empty Combat prose** (162/182 and 142/161) — the mechanics
  are there to tag, not missing.
- **A fixed ability vocabulary tags broadly** (creatures whose Combat/ability text
  matches): save vs. 149 · surprise 137 · poison 133 · charm 82 · spell-like/casts 81 ·
  fear 76 · invisibility 67 · paralysis 64 · breath 64 · constrict/crush 63 ·
  regeneration 44 · disease 35 · petrify/turn-to-stone 30 · level/energy drain 30 ·
  gaze 13 · swallow 10 · blood drain 8. 113 mention a "-N to save" penalty; **331 carry
  dice / point-damage in their Combat prose** the stat block's `damage_attack` doesn't.
  → highest-yield, fully automatable Phase C work: **ability chips + save/damage
  highlighting on the Combat panel**.
- **Prose is page-level, not variant-level.** 111 multi-variant pages hold 448
  creatures; on **96 of them every variant shares one identical Combat blob** (Balor and
  Marilith get the merged text of both). The prose *is* split into per-creature **bold
  sub-headers** (`Pit Fiend:`, `Balor (True Tanar'ri):`), but only **~6 pages** (Baatezu,
  Tanar'ri, Elephant, Frog, Grell, Mammal) have sub-headers that cleanly match the stat
  variants — so per-variant prose splitting is low-yield and fuzzy (manual triage).
- **Prose-only variants are rare.** Genuine cases are a handful — Elephant names
  Mammoths/Mastodons/Oliphants, Githyanki names its castes (G'lathk, Mlar, Hr'a'cknir),
  Frog its Giant/Killer/Poisonous types — most needing manual promotion. Detection is
  noisy (dragon age tiers and psionic-discipline sub-headers are false positives).
- **Ties back to Phase B's open breath item:** every dragon page carries a bold
  **"Breath weapon/special abilities:"** prose section keyed by age category (Young,
  Juvenile, …) — the natural source for breath-by-age the tier selector still lacks.

**Recommended Phase C order:** ability chips + save/damage highlighting first (broad,
automatable, directly relieves the 343 pointer fields); prose-only variants and
per-variant prose splitting second (narrow, manual, ~6–10 pages each).

**Shipped — ability & save chips.** Pure, Qt-free **`monster_abilities.py`**
(`ability_types`, `saving_throws`, `chips`) reads a Monster's Combat + terse
attack/defense text and tags it against a fixed ability vocabulary (breath, gaze,
poison, paralysis, level drain, petrification, regeneration, disease, charm, fear,
blood drain, swallow, constriction, invisibility, surprise, spell-like) and the
saving throws it calls for (canonical categories folded from ragged "save vs. …"
phrasing by earliest-keyword, plus signed save modifiers). `monster_html` renders
them as chips over the Combat panel (abilities neutral, saves accented); the verbatim
prose stays the source of truth beneath. **59% of creatures (379/634) get ≥1 chip.**
Covered by `test_monster_abilities.py` + view tests + a real-Medusa spot-check.
*Known limitation:* keyword tagging can't tell an offensive ability from an immunity
mention ("immune to charm" still shows a Charm chip) — the chip is an index into the
prose, not a claim.

**Shipped — Special Abilities card.** The chips index *which* abilities exist; a DM at
the table also needs the mechanics. `monster_abilities.abilities(m)` extracts, per
ability whose Combat prose pins it down, the **source sentence** plus the save,
damage, range and frequency highlighted out of it (reading into the following sentence
when the naming one carries no numbers). Rows with no extractable fact are dropped
(the immunity-mention noise stays in the chips), so the card is mechanics only. The
view renders a full-width **Special Abilities** card under the combat strip — ability
name, fact chips (damage/range/frequency neutral, save accented), and the source
sentence beneath, so the parse always sits next to the author's words. **223/634
creatures get ≥1 detailed row** (398 rows: 206 with a save, 165 with damage, 118 with
range). Covered by extraction unit tests + a card render test.

**Shipped — per-variant prose splitting.** v1 handed the whole page prose to every
variant (a Beholder kin's sheet showed the base beholder's Combat, its ecology was all
six kin concatenated). `_StatBlockHTML` now records the prose's bold sub-headers with
offsets, and `_attribute_variant_prose` splits the prose at the ones that name a
variant (fuzzy-matched for plural/singular — "War Dogs"→"War Dog", "Efreet"→"Efreeti";
most-specific header wins so "Lamia Noble" doesn't grab the base "Lamia"). Two page
shapes, told apart by whether a column is left header-less: a **base creature**
(Beholder, Bear — the leading Combat/Habitat/Ecology are its own, kin blocks stand
alone) vs **all-variant/shared** (Naga, Cat — the leading sections are general and
every variant inherits them, then adds its block). A kin block written as one flowing
paragraph (the Gauth) is routed into **Combat** so the ability/spell parse sees its eye
rays. **96 multi-variant pages now carry differentiated per-variant prose (was 0); 0
lost prose.** Covered by base-creature / shared / prefix-collision unit tests, and the
habitat guard relaxed to per-page (a single-paragraph kin legitimately has no habitat
section of its own).

The matcher scores each bold header against each variant — exact > plural/singular
("War Dogs"→"War Dog", "Efreet"→"Efreeti") > a directional family match (a short
header is a whole-word prefix/suffix of a fuller variant name, "Abishai"→"Black
Abishai"; a longer header's variant is its *leading* word, "Undead Beholder"→"Undead",
so the base "Beholder" stays header-less). One header can feed several variants (the
shared "Abishai" block → all three abishai); parenthetical annotations ("(beholder-
kin)") are ignored. A one-paragraph block with no sub-headers stays in **Description**
(its natural home — the spell/ability parse reads description too, so a caster's
mechanics still surface there). To finish the job the view **hides empty prose panels**
on imported monsters (a one-paragraph creature shows just Description + its ability/
spell cards, no empty boxes), while custom monsters keep every panel to fill in.

**Shipped — prose-only variants (the triage).** ~46 MM pages describe extra creatures
in prose with **no stat column** — the Archlich on the Lich page, the Kapoacinth
(Gargoyle), Koalinth (Hobgoblin), Malenti (Aquatic Elf), Reaver (Neogi), Storoper
(Roper), Stunjelly, Greenhag, Noble Djinn, the Green/Gray/Death Slaadi, and eight
beholder-kin (Elder Orb, Doomsphere, Orbus, Kasharin, Beholder Mage, Crawler …).
Their bold sub-headers matched no column, so their blocks were silently **bleeding
into the creature above them**. Now `_is_creature_header` separates a creature name
from the page's structural captions (section headers, dragon age tiers, psionic
disciplines, stat-block/table legends, spell names by their leading verb), and
`_starts_a_line` rejects mid-sentence bold emphasis (the "…the **mummies** of…" that
used to cut a page's prose in half). Those blocks now **bound** the prose (so nothing
bleeds) and are captured on `Monster.related_creatures` as `{name, text}`, rendered as
an **Also Described on This Page** section. Because a prose-only creature is a blurb —
it never owns Combat:/Habitat:/Ecology: — its block stops at the next section header
and that text returns to page level, so a page whose shared sections sit *after* the
blurbs (the Slaad) keeps them for every variant. Kept **verbatim** rather than promoted
to importable variants: the prose rarely carries a full stat line, so the plan's
"link-note them" path is the honest one — the parser never invents stats. Also fixed
irregular plurals in the header matcher (dwarf→dwarves, seawolf→seawolves) that had
been misreading real variants as orphans.

**Phase C is complete** — with a correction from the post-v2 audit below: 11 of the
blurbs it first surfaced (including the Stunjelly and the Greenhag named above) were
**not** prose-only creatures but real stat variants the matcher failed to recognize.
After the fix: **66 blurbs across 46 pages**, and no blurb duplicates a stat column.

### Phase D — Spell cross-linking. ✅ done.

Reuse the **`spells` table (875 rows, name·save·damage·range·level·caster)** and the
`dnd://` nav. Monsters name spell-like abilities as bare spell names — in the ability
fields and the Combat prose. A pure `monster_spells.py` longest-matches those against
the compendium and the view renders hits as links (add per-spell anchors to
`spellsscreen_html`). Reliable — a spell is in the compendium or it isn't — and high
value for casters like the Baatezu (animate dead, charm person, suggestion, teleport
without error, …).

*Shipped:* `spellsscreen_html` now emits one `id="spell-<slug>"` anchor per distinct
spell name (owns `spell_slug`). Pure, Qt-free **`monster_spells.py`** (`build_index`,
`find`) matches a monster's Combat + ability text against the compendium with two
rules that keep it clean: **multi-word names always match** ("dispel magic", "charm
person" — naive single-word scanning is unusable, "armor"/"addition"/"light" swamp the
hits), and **single-word names match only beside a casting cue** ("entangle once a
day", "casts suggestion", the beholder's "Fear (as wand)" / "(as spell)" eye-ray tags
— which carry to adjacent items in a numbered list) and never if they're on a small
**stoplist** of trait-words whose innate description reads like a cast (regenerate,
heal, armor, strength, addition, …). Longest-match wins ("improved
invisibility" over "invisibility"), and hits render with the compendium's **canonical
capitalization** ("Entangle", not the prose's casing). `monster_html` renders them as a
**Spell-like Abilities** block at the foot of the stat block (alongside the Special
Abilities block, both moved in there); chips link `dnd:///spell/<slug>`, navigation
maps that to `spells#spell-<slug>`, and `app.py._render_spells(fragment)` opens the
compendium — with a `jumpToHash` script + `scroll-margin-top` on the cards so the jump
lands reliably below the sticky header (QtWebEngine's native anchor scroll fires before
layout settles). The index is built once from the Spells-screen rows and threaded into
`generate`. Matching scans **all** of a monster's prose (`find_in` over combat, the
terse attack/defense fields, *and* description/habitat/ecology) — a caster's spell list
is often written into the flavor rather than Combat (Lich, Green Hag, the Giants), and
the cue-gate keeps that safe (0 garbage across the corpus). **~226/634 creatures get ≥1
spell link (~810 total); every linked slug resolves to a real anchor (0 broken).** Covered by `test_monster_spells.py`,
navigation-grammar tests, an anchor test, and view render tests. *Notes:* the dragon
Wizard/Priest age columns hold spell *levels* (numbers), not names, so they aren't a
link source (the plan's mention of them was mistaken); and a handful of spells a
monster names simply aren't in the scraped `spells` table (e.g. **Flesh to Stone** —
the DB has *Stone to Flesh* but not its inverse), so they can't link until
`build_spells.py`'s source is filled in.

*Note:* `monster_spells` imports `spell_slug` from `spellsscreen_html` (the screen owns
the `id=` targets), so links can't drift from the anchors they point at.

### Deliverable — Roll20 monster export. ✅ done.

Extend `roll20_export` to emit a monster stat block (with the selected tier's
numbers), so an imported, enriched monster drops straight into Roll20, which handles
initiative, HP and status at the table.

*Shipped:* **`roll20_export.monster_to_roll20(m, spell_details, spell_index)`** emits the
same import JSON the community 2e sheet's bulk importer (`act_importall` in
`roll20_sheet/sheet.html`) already reads — v2 reuses the PC layout. It applies the
**selected HD/age tier** (`monster_tiers.active_monster`) first, then maps: name, average
HP from Hit Dice, the house-rule **attack bonus** (20−THAC0) and **ascending AC**
(`armor_base` = the AC, since no armor rows are sent), movement, XP, and **warrior-by-HD
saves** via new `char_rules.monster_saving_throws(hd)`. The attack/damage line becomes
weapon rows — one per `/`-separated attack (claw/claw/bite), damage ranges converted to
dice, each rolling at the **size-derived initiative speed factor** — and the spell-like
abilities `monster_spells.find_in` matches become enriched spell rows. Wired to a
`dnd:///mon/roll20` action + an **⤴ Export to Roll20** button on the sheet
(`app.py._mon_export_roll20` copies the JSON to the clipboard, like the character
export). Pure and unit-tested (`test_roll20_export.py`), reusing the same char_rules
conversions so it can't disagree with the sheet.

## v3 — a dedicated Roll20 monster sheet

v2's export reuses the full PC character sheet, which carries a lot a monster never
needs (proficiencies, spell slots, encumbrance, wealth). v3 gives monsters their own
lean layout:

- **A "monster" toggle on the Roll20 sheet.** Add a setting to the campaign's
  community 2e sheet (`roll20_sheet/`) that switches it into a **monster layout** —
  showing only what a DM runs a monster from: name, AC (ascending), attack bonus,
  HD/HP, attacks & damage, saves, special attacks/defenses, movement, morale, XP, and
  the size-derived initiative — and hiding the PC-only sections.
- **`monster_to_roll20(m)` in `roll20_export`.** The monster counterpart to
  `character_to_roll20`: emit the clean intermediate JSON the import worker
  (`import_addon.html`) maps onto the monster layout, with the setting flag set so an
  import lands as a monster, not a half-empty PC. Pure and unit-tested, reusing the
  same house-rule conversions (attack bonus, ascending AC) so it can't disagree with
  the sheet. Carries the Phase B tier data (the selected HD/age) and the Phase A/C/D
  enrichment (structured abilities, spell links) where the sheet has a home for it.

## Code-health cleanups (deferred from the pre-v2 audit)

Low-risk tid-ups noted while auditing the feature; none block v2, do them when the
surrounding code is next touched:

- **Extract image caching to a pure `monster_images.py`.** `app.py`'s
  `_mon_image_url` / `_cache_image` are ~35 lines of *pure* logic (remote-URL and
  cache-path building, data-URI encoding) with only the thread spawn needing Qt/IO.
  Pull the pure part into a tested module, per the "extract Qt-light clusters"
  direction in CLAUDE.md.
- ✅ **Cache the last-parsed page.** `app.py._parse_mm_page` is a one-entry cache keyed
  by page_url, so a pick (`_mon_pick` → `_render_variant_picker` → `_mon_pick_variant`)
  parses once, not thrice; `_fresh_monster` hands the sheet a detached copy so edits
  don't mutate the cached parse.
- ✅ **Publish `clean_title`.** `monster_parser.clean_title` is now the public alias;
  `app.py` uses it (via `_parse_mm_page`) instead of the private `_clean_title`.
- ✅ **Wire `Monster.initiative_override`.** The Size row's `init-ov` control sets it
  (blank clears back to the size-derived factor); carried into the Roll20 export's
  weapon speeds.
- ✅ **One range→dice rule.** `monster_html._to_dice` and `roll20_export._range_to_dice`
  had each implemented the MM's damage-range conversion, with different semantics (a
  substitution over the whole string vs. a `fullmatch`), so `"2-8 per leg"` rendered as
  dice on the sheet but exported as a raw range. Both now call
  **`monster.damage_to_dice`**, whose `terse` flag is the only difference between them
  (the sheet's `d6` against Roll20's rollable `1d6`) — the char_rules re-export
  discipline applied to the MM's own notation. Verified corpus-wide: 0 conversions
  differ beyond that display form.
- ✅ **The `mon/` link grammar moved to `navigation.py`.** `app.py._mon_action` was a
  30-line `startswith` ladder doing its own decoding, index coercion and `try/except`
  in the Qt layer, while every other link is classified by `navigation.route_link` into
  a tagged `Route` and matched. **`route_mon(payload)`** now owns that grammar and
  returns a tagged `MonAct` (`MonSet`, `MonTier`, `MonPickVariant`, …), so `_mon_action`
  is a `match` of side effects and the coercion is unit-tested without Qt
  (`test_navigation`). Policy stays where it belongs: navigation decides what a link
  *says*, `monster`/`monster_tiers` decide what may be edited.

## Post-v2 audit — correctness pass. ✅ done.

A full read of the feature (plan, architecture, code) once v2 had landed, measured
against `dnd2e.db` rather than argued from the code. Four defects fixed:

- ✅ **Editing "Attack Bonus" destroyed conditional THAC0 — and its tiers.** The row
  showed `attack_bonus()` (one number, the base) but stored the edit over the *whole*
  field, so re-typing the shown value turned the Beholder's
  `"45-49 hp: 11 50-59 hp: 9 …"` into `"11"` — losing the source text and all four
  scaling tiers, silently. `monster.house_rule_round_trips` now gates the conversion:
  a bare THAC0 stays editable as an attack bonus (517 of 634 creatures), anything
  richer shows **the MM's own text, read-only, with the derived bonus as a badge**
  (117). AC is unaffected — `ascending_ac()` maps every number in place, so it is its
  own inverse.
- ✅ **Per-variant prose was diverted away from renamed variants.** `_header_score`
  compared a bold sub-header only against the *resolved display* name, so a header
  spelling the creature differently from its stat column scored 0, was filed as a
  prose-only creature, and left the real variant with the page's generic text. Two
  fixes: `_same_words` matches **the same words reordered and/or run together**
  ("Giant Rats" → the column "Rat (Giant)", "Stunjelly" → "Jelly, Stun-", "Greenhag" →
  "Green Hag", "Megalo- centipede" → "Megalocentipede"), and `_match_score` scores
  against **both** the display name and the raw column. **11 diverted variants
  recovered, 7 more headers matched, 0 newly orphaned**; blurbs 88 → 66,
  differentiated-prose pages 98 → 101.
- ✅ **Bolded sentence fragments read as creatures.** `_is_titlecase_name` rejects a
  header with a trailing lowercase word ("Dodge missiles", "Rrakkma bands", "Giant
  marine spiders") — captions, which were bounding (and so truncating) the prose of
  the creature above them.
- ✅ **Roll20 HP / saves.** `_hp_from_hd` rounds half *up* (a 1 HD monster was
  exporting 4 hp) and reads the hit-point forms the MM uses ("1 hp", "1-4 hp",
  "9 (40 hp)") instead of treating the number as dice; `_hd_level` sends a creature of
  less than one die to the **level-0** Warrior save band that `char_rules._SAVES`
  already carried but `monster_saving_throws` clamped away.

- ✅ **A tiered edit could overwrite the base stat block.** The read-only-ness of a
  scaled sheet was enforced only by HTML attributes; `_mon_set` accepted anything.
  `monster_tiers.tiered_fields(m)` now names the fields the *active* tier is scaling
  and `_mon_set` refuses exactly those — so the view and the handler derive the rule
  from the same place, and prose (never tiered) stays editable at any tier.

Guarded by a new corpus invariant — *no "Also Described on This Page" blurb may name a
creature the page has a stat column for* — which is what caught the second defect and
is deliberately written independently of the matcher's own rules.

## Known limitations / loose ends (from the audit)

Small, recorded so they're not forgotten; none block v2:

- **Two pages don't parse:** `Human` and `Mammal-- Small` (messier source formats
  than the compact tables we handle). Currently omitted from the picker.
- **Termite castes** import as bare `King`/`Queen`/`Soldier`/`Worker` — the
  "Termite, Giant Harvester" caste header is dropped rather than prefixed onto them
  (dropping was the safe fix vs. mis-merging). Cosmetic.
- **The compact summary pages carry no Size.** 92 of the 634 creatures (Insect,
  Mammal, Fish, Bird — the abbreviated one-row-per-creature tables) have no `SIZE`
  column, so the sheet's Initiative tile reads "—" and the Roll20 export sends speed 0.
  The `init-ov` override lets the DM set it per creature; deriving it from the prose
  isn't worth the guesswork.
- **Stem-different variant names still miss.** The matcher handles reordering and
  run-together spellings but not stemming, so the Snake page's "Poisonous Snake" still
  doesn't reach its column "Poison Snake (Normal)". A handful of pages; the blurb is
  shown verbatim rather than lost.
- **Damage/Attack is displayed as dice but stored as typed**, so the first edit of that
  row replaces the MM's range ("1-3/1-3 or 2-8") with its dice form. Harmless in play,
  but it breaks the model's "stat fields hold the MM strings verbatim" invariant — the
  same defect class as the THAC0 one above, without the data loss.

## Out of scope

- Re-parsing the generic category pages (Dragon-- General, "The Monsters", the blank
  form, etc.) — they carry no stat block; the picker just omits them.

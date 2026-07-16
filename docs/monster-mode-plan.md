# Monster mode — plan

**Status:** v1 complete and merged (PR #11). Phases 1 (pure core), 2 (persistence),
3 (view) and 4 (UI wiring) all done, then a creature-by-creature data audit + a
pre-v2 code-health pass (model/parser split). v2 is **deeper monster data** (below):
parse the discarded tables, mine the prose, and make HD/age scaling interactive.
No in-app encounter tracker — Roll20 runs the encounter.

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

### Phase A — Parse & categorize every embedded table

**73 importable pages carry tables beyond the stat block** that the parser currently
drops (it stops at the first trailing sub-table — the "Variable Body" fix). Classify
each `<table>` and attach the useful ones to the Monster as structured data:

- **Age-progression** (every dragon: Age → HD/size, AC, breath weapon,
  Wizard/Priest spells, MR, treasure, XP) — the scaling data Phase B consumes.
- **Psionics summary** (Level · Disciplines/Sciences/Devotions · Attack/Defense
  modes · Power Score · PSPs) — Githyanki, Githzerai, Shedu, gem dragons, …
- **Per-attack damage breakdown** (Baatezu: Attack | Damage rows).
- **Random / advancement tables** (encounter or class-level rolls) — capture or
  skip per category; lowest value.

A table classifier in `monster_parser` (keyed off each table's header row), optional
structured fields on `Monster`, rendered as their own sheet sections.

### Phase B — Selectable HD / age scaling (flagship)

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

### Phase D — Spell cross-linking

Reuse the **`spells` table (875 rows, name·save·damage·range·level·caster)** and the
`dnd://` nav. Monsters name spell-like abilities as bare spell names — in the ability
fields, the Combat prose, and the dragon **Wizard/Priest** columns (Phase A). A pure
`monster_spells.py` longest-matches those against the compendium and the view renders
hits as `dnd://spells#<anchor>` links (add per-spell anchors to `spellsscreen_html`).
Reliable — a spell is in the compendium or it isn't — and high value for casters like
the Baatezu (animate dead, charm person, suggestion, teleport without error, …).

### Deliverable — Roll20 monster export

Extend `roll20_export` to emit a monster stat block (with the selected tier's
numbers), so an imported, enriched monster drops straight into Roll20, which handles
initiative, HP and status at the table.

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
- **Cache the last-parsed page.** Picking a multi-variant page parses it three times
  (`_mon_pick` → `_render_variant_picker` → `_mon_pick_variant`). Harmless (pages are
  small) but a one-entry parse cache keyed by page_url would remove the waste.
- **Publish `clean_title`.** `app.py` reaches into `monster_parser._clean_title`
  (private); expose it as a public helper if the boundary is worth firming up.
- **Wire `Monster.initiative_override`.** The field is plumbed through the model and
  persistence but nothing sets it yet — add a sheet control if a DM wants to override
  the size-derived initiative speed factor (e.g. for the Roll20 export).

## Known limitations / loose ends (from the audit)

Small, recorded so they're not forgotten; none block v2:

- **Two pages don't parse:** `Human` and `Mammal-- Small` (messier source formats
  than the compact tables we handle). Currently omitted from the picker.
- **Termite castes** import as bare `King`/`Queen`/`Soldier`/`Worker` — the
  "Termite, Giant Harvester" caste header is dropped rather than prefixed onto them
  (dropping was the safe fix vs. mis-merging). Cosmetic.

## Out of scope

- Re-parsing the generic category pages (Dragon-- General, "The Monsters", the blank
  form, etc.) — they carry no stat block; the picker just omits them.

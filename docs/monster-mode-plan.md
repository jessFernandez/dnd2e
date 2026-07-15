# Monster mode — plan

**Status:** complete. Phases 1 (pure core), 2 (persistence), 3 (view) and 4 (UI
wiring) all done. v2 enhancements (below) remain as future work.

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
| Stat-block model + MM parser | `monster.py` | ✅ |
| Persistence (save/load to user DB) | `monster_library.py` | ✅ |
| Sheet view (render + edit) | `monster_html.py` | ✅ |
| Monster mode + MM import picker | `app.py` (thin) | Qt |

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

## v2 — later enhancements

Deliberately deferred; revisit once v1 is in use:

- **Structured special abilities.** Parse each special attack/defense into
  machine-usable fields (name · save · damage · range · frequency) so an encounter
  tracker can auto-roll saves and apply effects. Hard NLP over inconsistent prose;
  only pays off with automation, not for reading.
- **Spell cross-linking.** Many monsters list spell-like abilities as bare spell
  names (Baatezu: "animate dead, charm person, …"). Detect those and link them to
  the existing spell compendium (`dnd://` links).
- **Recognize the extra prose sub-sections.** Dragon age-tiers ("Juvenile:",
  "Adult:", …) and "Psionics Summary:" currently fold into the nearest captured
  section; promote them to first-class fields so those abilities aren't buried.
- **Refine HD-conditional conversions.** THAC0/XP strings like "3+3 HD: 17 4+4 HD:
  15" garble the derived attack bonus (see phase 1 limitation) — convert only the
  true THAC0 numbers, not the HD notation.
- **Numeric HD/HP + a live encounter tracker** that consumes this model (initiative
  order, HP/AC/status tracking, inline attack/save rolls).
- **Roll20 export for monsters.**

## Out of scope

- Re-parsing the ~7 generic category pages (Dragon-- General, etc.) — the picker
  just omits them.

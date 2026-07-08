# UX feedback — remediation plan

Status: **7 of 8 done; C3 reverted** · Created 2026-07-08 · Last updated 2026-07-08

Progress: A1 ✓ · B1 ✓ · B2 ✓ · B3 ✓ · B4 ✓ · C1 ✓ · C2 ✓ · **C3 reverted** (a full
dark re-theme didn't fit the sheet's design; backed out — sheet stays on its
original light theme). All app-side changes are covered by the test suite (264
passing). The Roll20 armor fix (C1) can't be unit-tested — verify by re-importing
a character into a Roll20 game with **Legacy Sanitization ON**.

C3 attempt & why it was dropped: the white "not filling" was structural — white is
set only on the fixed-size `.sheet-tab` panels, so Roll20's dark page shows through
below/right. A dark re-theme (root painted dark + tabs transparent + re-skinned
surfaces) fixed the fill but clashed with the sheet's light design, so it was
reverted at the user's request. Lesson logged for any future attempt: keep sheet
CSS **ASCII-only** — a single non-ASCII byte (em dash, middle dot, ellipsis) in a
comment makes Roll20's legacy sanitizer reject the *entire* stylesheet.

A round of playtest feedback, grouped by the surface each item touches. Nothing
here breaks the architecture rule (logic stays in the pure `char_rules` /
`character` / `charactermancer_html` layers; only `app.py` imports Qt). Items are
independent — they can land as separate commits in any order. Rough effort in
each heading: **S** ≈ <1h, **M** ≈ a few hours, **L** ≈ a day+.

---

## Surface A — scraped rulebook pages (content view)

### A1. Float the table header on the Economics weapons page — **S**

**What:** long price tables (esp. *Economics of the Realm* weapons) scroll their
header off-screen. Pin `<thead>` so the column labels stay visible.

**Where:** scraped pages get their theme from CSS injected in
[`app.py`](../app.py) `PageView.load` (`_BASE_INJECT` + `_READING_INJECT`, ~L505).

**Fix:** add a sticky-header rule to the injected CSS:
```css
thead th { position: sticky; top: 0; background: #1e202c !important;
           box-shadow: inset 0 -1px 0 #3a3e50; z-index: 2; }
```
Applies to every rules table (weapons benefits most). Caveat: the existing
`table{border-collapse:collapse}` (L508) drops sticky cell borders in Chromium 87
— that's why the fix uses `background` + an inset `box-shadow` for the divider
instead of a border. Verify on the ECO weapons page (`toc/ECO` → weapons) and one
plain PHB table so we don't regress non-tabular pages.

**Files:** `app.py`. No new tests (pure CSS); eyeball in-app.

---

## Surface B — the in-app character builder (`charactermancer_html.py`)

### B1. Pin the References + character summary as a side rail on every step — **M**
*(feedback items "references on the side pinned" + "character sheet")*

**What:** the per-step **References** row currently sits at the bottom of the step
body (`_step_refs`), and the **character overview** (`_summary_panel`, the "Your
Character" box) only appears on race/class/alignment/details. Playtest ask: pin
the References in the side panel, with the character-sheet overview alongside, so
both stay visible while scrolling.

**Where:** [`charactermancer_html.py`](../charactermancer_html.py) — the `generate()`
shell (L1028), each `_*_body` that renders its own `<aside class="col-side">`, and
`_step_refs` (L974).

**Fix:** lift the side column out of the individual bodies into the `generate()`
shell so **every** step has a persistent right rail = `_summary_panel(cm)` +
`_step_refs(cm.step)`, made sticky (`.col-side { position: sticky; top: 16px; }`).
Bodies keep only their main column. Two wrinkles:
- The Abilities step shows the **eligibility** panel, not the summary — keep that
  special case (show eligibility there, summary elsewhere), or show both stacked.
- Proficiencies/Equipment/Spells currently have no side column and use full width;
  moving to the shared two-col rail means re-checking their grids at narrow widths
  (the `@media (max-width:720px)` collapse already exists).

**Files:** `charactermancer_html.py` (shell + CSS + strip per-body asides).
Update `tests/test_screens.py` / any snapshot asserting the old layout.

### B2. Tooltip on hover over owned equipment — **S**

**What:** in the Equipment step, the *buy* chips have hover tooltips
(`title="{notes}"`) but the **Owned** rows don't — hovering a bought item shows
nothing.

**Where:** `charactermancer_html.py` `_equipment_body`, the owned-row loop (~L824).

**Fix:** add `title=` to each owned `prof-row` with the item's notes + stat line
(reuse `_eq_item_detail(it)` and `it.get("notes")`). One-line change per row.

**Files:** `charactermancer_html.py`.

### B3. Move the ambidextrous (handedness) roll to the Proficiencies step — **S/M**

**What:** the house-rule handedness roll (d10, 10 = ambidextrous) lives in the
**Details** step, but it gates weapon-proficiency choices (`can_buy_ambidexterity`
and the Ambidexterity weapon-prof in `_weapon_section`). It should be on the
Proficiencies tab, before you spend weapon slots.

**Where:** `_details_body` (L410, the handedness block) → `_proficiencies_body` /
`_weapon_section` (L649). Dispatch verb `cm/handedness` stays the same.

**Fix:** relocate the roll UI to the top of the weapon section (keep the Ranger
auto-ambidextrous note). Remove it from Details. Check
[`charactermancer.py`](../charactermancer.py) `is_complete("details")` doesn't
depend on the roll (it shouldn't — the roll is optional); if it does, move that
gate too.

**Files:** `charactermancer_html.py`, maybe `charactermancer.py`.
`tests/test_charactermancer.py` routing is unaffected (same verb).

### B4. Spells step: collapsible info + enforce level-1 limits — **L**

Two parts.

**(a) Collapsible spell descriptions** — reuse the proficiency pattern. The NWP
list already renders `<details class="pr-desc">…</details>` via
`_prof_description_html` (L622). Spell dicts carry `description`, so render the
same expandable "What it does" block per spell in `_spells_body` (L870) instead of
only a truncated `title=` tooltip.

**(b) Actual spell limits (enforce full 2e rules)** — today `_spells_body` lets you
pick unlimited spells. Add a real budget, like the proficiency slot bars:
- **Wizard:** cap the 1st-level spellbook at Intelligence's `max_spells_per_level`
  (already in `char_rules` `Intelligence` mods; `999 = All`). Read Magic is
  free/auto per 2e — include it automatically and don't count it against the cap.
- **Priest:** memorizable count = base 1st-level priest slots at level 1 **+**
  `cr.priest_bonus_spells(wis)[1]` (Wisdom bonus, already in `char_rules`). All
  priest spells stay available; the limit is how many you memorize.

Engine gaps to fill:
- a base **priest spell-slots-by-level** table in `char_rules.py` (level 1 = 1
  1st-level slot) — this is one of the tables flagged missing in
  [`leveling-plan.md`](leveling-plan.md), so doing it here also advances leveling;
- `character.py`: `spell_limit()` / `spells_left()` / `can_add_spell()` (mirrors
  the weapon-slot helpers);
- `charactermancer.py`: guard the `addspell` dispatch so it refuses past the limit
  (like `addweapon` respects slots);
- `charactermancer_html.py`: a `_budget_bar` for spells + disable (`.opt.dis`)
  available spells when the budget is spent.

**Files:** `char_rules.py`, `character.py`, `charactermancer.py`,
`charactermancer_html.py`. Tests: `tests/test_char_rules.py` (priest slot table),
`tests/test_character.py` (limit math), `tests/test_charactermancer.py` (addspell
refusal at cap). This is the biggest item — land it last / on its own.

---

## Surface C — Roll20 custom sheet + JSON import (`roll20_sheet/`, `roll20_export.py`)

### C1. Armor import must feed the Armor section, not set AC directly — **S/M**

**What:** the import sets `acarmor` (total armor AC) as a scalar
([`sheet.html`](../roll20_sheet/sheet.html) import worker L3566,
`acarmor: num(data.armor_bonus,0)`) **and** builds the `repeating_armor` rows
(L3605). But the sheet's own `change:repeating_armor` worker (L2322) recomputes
`acarmor` by summing equipped rows — so the direct scalar is redundant and can
fight the worker (double-count or stale value). AC should come **only** from the
Armor section.

**Fix:**
- `roll20_export.py`: stop exporting `armor_bonus` as an AC driver (L81); the
  `armor[]` list (L131) already carries each worn piece's `aac`.
- `sheet.html` import worker: drop `acarmor` from the scalar block; keep
  `acbase: 10`. Rely on the `armor` rows + the section worker to compute AC.
- **Verify the section worker actually fires on import-created rows.** If
  `setAttrs` row creation doesn't trigger `change:repeating_armor`, add an explicit
  recompute after the rows land (or nudge one armor field) so AC isn't left at 10.

**Files:** `roll20_sheet/sheet.html`, `roll20_export.py`,
`tests/test_roll20_export.py` (assert no direct AC field; armor rows present).

### C2. Import a race-appropriate movement speed — **S**

**What:** `roll20_export.py` hardcodes `"move": 12` (L81); every character imports
at speed 12. Dwarves/gnomes/halflings move 6, most others 12.

**Fix:** add a race→base-movement table to `char_rules.py` (Dwarf 6, Gnome 6,
Halfling 6, Elf/Half-elf/Human 12, Half-orc 12…), a `character.movement()` helper,
and export that value. ("Different speed for the general options" = the race's
base move.) Encumbrance-adjusted move can come later; base-by-race covers the ask.

**Files:** `char_rules.py`, `character.py`, `roll20_export.py`, tests.

### C3. Fix the white-background CSS on the sheet — **S/M**

**What:** the custom sheet shows a jarring white background.
[`sheet.css`](../roll20_sheet/sheet.css) uses `background: white` (`.sheet-tab`
L133) and other light defaults, and the sheet root doesn't set its own themed
background, so Roll20's default white shows through.

**Fix:** give the sheet root a themed background and replace the stray
`white`/near-white fills with the sheet's palette. **A screenshot pinpoints the
exact offending panel** — worth grabbing one before touching it, since this can't
be verified outside Roll20. Change CSS only (no worker/HTML logic), test by
re-importing the sheet into a Roll20 game.

**Files:** `roll20_sheet/sheet.css`.

---

## Suggested landing order

1. Quick wins first: **A1, B2, C2** (all S, isolated).
2. **C1** and **C3** (Roll20 sheet) — batch, since both need a Roll20 re-import to
   verify; grab a screenshot for C3 first.
3. **B3** (ambidextrous move) — small builder change.
4. **B1** (side rail) — touches the builder shell; do it before B4 so the spells
   step is already in the new layout.
5. **B4** (spell limits) last — largest, and it also advances the leveling engine.

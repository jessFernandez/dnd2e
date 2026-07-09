# Feature plan: character leveling / advancement

Status: **Phase 1 done** (engine + state); phases 2–3 planned · Last updated: 2026-07-09

Turn the character builder from a level-1 generator into a real character manager
that can set a character's level (or track XP and level up) and recompute every
level-dependent stat.

## Why this is the top feature

`char_rules.py` is already **fully parameterized by level** — the expensive part
of any D&D feature (transcribing the 2e progression tables) is done and currently
unused above level 1. See the readiness table below. This is the highest
value-to-effort item in the codebase.

## Step zero: character state — ✅ **DONE (Phase 1)**

`Character` now carries `level`, `xp` and `hp_rolls`, and the level-1 hardcoding is
gone:

- `weapon_slots_total()` / `nonweapon_slots_total()` use `self.level`
- `max_hp()` / `thac0()` / `attack_bonus()` / `saving_throws()` default to the
  character's own level (an explicit `level=` argument still overrides)
- `set_level(level, rng)` clamps to the racial cap and keeps `hp_rolls` in sync
  (levelling up rolls new hit dice, down truncates); `reroll_hp()` rerolls them
- `to_dict()` / `from_dict()` persist all three, and **legacy saves without them
  load as a level-1 character** (dataclass defaults) — covered by a test
- `roll20_export.py` sends the real `player_level` (and now `xp`, which the sheet's
  import worker writes into its previously-unpopulated `attr_xp` field)
- `charactermancer._resync_level()` re-applies the level after a race or class
  change (both move the racial cap **and** the hit-dice count), *after*
  `_revalidate()` clears an illegal class

## What the engine already provides (ready — just pass `level`)

| Mechanic | Engine function | Notes |
|---|---|---|
| XP thresholds | `xp_for_level`, `level_for_xp` | all 9 classes; tables to ~20 (Druid ~15) |
| THAC0 / attack bonus | `thac0(cls, level)`, `attack_bonus` | spot-checked vs PHB Table 53 |
| Saving throws | `saving_throws(cls, level)` | Table 60 bands, all four groups |
| Weapon prof slots | `weapon_slots(cls, level)` | Table 34 intervals |
| Nonweapon prof slots | `nonweapon_slots(cls, level, int)` | incl. Int bonus |
| HD size + Con bonus | `hit_die`, `con_hp_bonus` | incl. warrior-only high-Con bonus |
| Racial level limits | `max_level(race, cls)` | **must be enforced as the level cap** |
| Post-name-level flat HP | `ClassGroup.name_level` / `hp_after` | data present (W 9/+3, Wiz 10/+1, Pr 9/+2, Rog 10/+2), verified vs RAW |

## Rules gaps — apply on level-up, NOT yet in the engine

### 🔴 Required for a correct level-up

1. ✅ **HP accumulation across levels — DONE.** `cr.hp_at_level(class, level, con,
   rolls)` + `cr.hp_die_levels(class, level)`. 1st level is best-case; levels
   2..`name_level` add a stored roll **+ Con bonus per HD** (a level never yields
   less than 1 hp); levels past `name_level` add `hp_after` flat with **no die and
   no Con bonus**. Con is applied at call time, not baked into the rolls, so a
   later Constitution change recomputes correctly.
2. **Spellcaster spell-slot tables** — the biggest transcription gap:
   - Wizard **Table 21** (spells of each level by class level 1–20) — absent
   - Priest **Table 24** (base priest spells by class level) — **partially added**:
     `char_rules.priest_spell_slots(level, wis)` + `_PRIEST_SPELL_SLOTS` now exist
     but only **class level 1** is tabulated (added for the builder's level-1 spell
     limit). Fill in levels 2–20 here. It already combines the base with
     `priest_bonus_spells(wis)`, capping the bonus to castable spell levels.
   - Wizard highest castable level is currently gated only by Intelligence
     (`max_spell_level`), not by class level
   - The builder filters spells to `level == 1` today (`_set_spell_catalog`)
3. ✅ **Multiple attacks per round (warriors) — DONE.** `cr.attacks_per_round(class,
   level)` returns `(attacks, rounds)`: 1/1 → 3/2 at 7th → 2/1 at 13th, Warrior
   group only. (Weapon specialisation grants further attacks — that's Combat &
   Tactics, see [`combat-tactics-chargen-plan.md`](combat-tactics-chargen-plan.md).)

### 🟡 Substantial subsystems (in-scope classes, real work)

4. **Thief skills (Table 29)** — Thief/Bard get 30%/level across 8 skills, with
   Dex (Table 27), race (Table 28), and armor adjustments. **Completely
   unmodeled today.** A Thief level-up without this is a major omission.
5. **Turn Undead (Table 61)** — Cleric from 1st, Paladin from 3rd (as cleric −2).
6. **Sub-caster progressions** — Ranger priest spells @8th, Paladin priest spells
   @9th, Bard wizard spells (Table 25). Tie into #2 with their own capped tables.

### ⚪ Out of scope (narrative / DM-adjudicated / optional — the rulebook browser already covers these)

Paladin lay-on-hands & auras, Ranger species enemy / tracking / followers, Bard
lore & influence, Druid shapechange, weapon specialization, strongholds/henchmen
at name level.

## Design decision: HP per level — **DECIDED 2026-07-09**

**Max at 1st level, rolled & stored for 2nd+.** (Was the blocker on Phase 1; the
recommendation below was accepted.)

- 1st level keeps today's best-case behaviour (`max_hp()` unchanged at level 1).
- Each level from 2nd up **rolls its hit die and stores the result**, with a reroll
  button in the UI.
- Levels past `name_level` add the flat `hp_after` with **no die and no Con bonus**.
- Because the per-level rolls are persisted, a later Constitution change (aging,
  a magic item) recomputes total HP correctly — the Con bonus is applied *per hit
  die* at display time rather than baked into the stored roll.

**Schema impact (Phase 1):** `Character` gains `level`, `xp`, and `hp_rolls: list[int]`
(one entry per level ≥ 2). `to_dict`/`from_dict` must persist them and **migrate
legacy saves** that have none (treat as level 1, empty rolls).

Alternatives considered and rejected: *average* (deterministic but unfaithful —
the table rolls), *max at every level* (too generous), *manual entry* (no rules
modelling; still worth offering as an override later).

## Suggested phasing

- ✅ **Phase 1 — advance the core stats (all classes): DONE.** `level`/`xp`/`hp_rolls`
  state, HP accumulation, un-hardcoded slot budgets, Roll20 `player_level` + `xp`,
  racial caps enforced in `set_level`, warrior multiple-attacks.
- ✅ **Phase 1b — builder level control: DONE.** A level stepper (`cm/level/<n>`,
  `cm/rerollhp`) on the **Class step** — deliberately *not* Details, because the
  level sets the proficiency-slot budgets that the later Proficiencies step spends
  — and again on the finished **Review** sheet so a saved character can level up in
  place. The `+` disables at the racial cap; the stored hit dice are listed with a
  reroll link; the side rail and sheet now read "At *N*th level" and show
  attacks/round. The Spells step **warns explicitly** when level > 1 that spell
  progression above 1st isn't modelled yet (see Phase 2) rather than quietly
  showing 1st-level slots.
- **Phase 2 — casters:** Wizard Table 21 + Priest Table 24 (+ specialist / Ranger
  @8 / Paladin @9 / Bard hooks); extend the Spells step beyond level 1.
- **Phase 3 — Thief skills** subsystem and Turn Undead.

## Conventions to follow (per CLAUDE.md)

- New rules/tables go in `char_rules.py` (pure, single source of truth); the
  builder and Roll20 export delegate — never duplicate a rule.
- Each new pure function gets a `tests/test_char_rules.py` (or new) test.
- Keep it Qt-free; the UI wiring lives in `charactermancer.py` / `_html.py` / `app.py`.

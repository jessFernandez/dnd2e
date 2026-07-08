# Feature plan: character leveling / advancement

Status: **planned, not started** · Owner: TBD · Last updated: 2026-07-07

Turn the character builder from a level-1 generator into a real character manager
that can set a character's level (or track XP and level up) and recompute every
level-dependent stat.

## Why this is the top feature

`char_rules.py` is already **fully parameterized by level** — the expensive part
of any D&D feature (transcribing the 2e progression tables) is done and currently
unused above level 1. See the readiness table below. This is the highest
value-to-effort item in the codebase.

## Step zero: character state

`Character` (character.py) has **no `level` or `xp` field**. Every derived method
already takes `level: int = 1` and just defaults to 1, but three things hardcode
level 1 and must be threaded:

- `weapon_slots_total()` / `nonweapon_slots_total()` — call `cr.*_slots(cls, 1)`
- `max_hp()` — only best-case level-1 HP
- `to_dict()` / `from_dict()` — don't persist level/xp
- `roll20_export.py` — hardcodes `"player_level": 1`

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

1. **HP accumulation across levels.** Only `max_hp_at_first_level` exists. The
   data to compute HP at level N is all there (HD, Con bonus, `name_level`,
   `hp_after`), but no function sums it. Rules: levels 1..`name_level` each add a
   hit-die roll **+ Con bonus per HD**; levels past `name_level` add `hp_after`
   flat with **no die and no Con bonus**. Needs a **design decision** (see below)
   because 2e HP is rolled per level.
2. **Spellcaster spell-slot tables** — the biggest transcription gap:
   - Wizard **Table 21** (spells of each level by class level 1–20) — absent
   - Priest **Table 24** (base priest spells by class level) — absent;
     `priest_bonus_spells(wis)` only adds the Wisdom bonus *on top of* this
     missing base
   - Wizard highest castable level is currently gated only by Intelligence
     (`max_spell_level`), not by class level
   - The builder filters spells to `level == 1` today (`_set_spell_catalog`)
3. **Multiple attacks per round (warriors)** — 1/round → 3/2 at 7th → 2/1 at
   13th. Small table, but numeric and level-based (Fighter/Paladin/Ranger).

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

## Open design decision (blocks Phase 1)

**How is HP determined per level?** This drives the `Character` schema and the UI:
- **Rolled & stored** — store each level's HD roll (a list); reroll button. Most
  faithful; requires new persisted state.
- **Average** — deterministic (e.g. HD/2+1 per level); simplest, no stored rolls.
- **Max** — matches the existing level-1 best-case behaviour.
- **Manual entry** — player types their real rolled total.

Recommendation: keep **max at 1st level** (matches today) and offer rolled/average
for 2nd+, storing per-level values so Con changes recompute correctly. Confirm the
campaign's house rule before building.

## Suggested phasing

- **Phase 1 — advance the core stats (all classes):** add `level`/`xp` state; HP
  accumulation (after the decision above); un-hardcode the slot budgets and Roll20
  `player_level`; enforce racial caps; add warrior multiple-attacks. Mostly wiring
  + one small table — makes every character levelable for the numbers that matter.
- **Phase 2 — casters:** Wizard Table 21 + Priest Table 24 (+ specialist / Ranger
  @8 / Paladin @9 / Bard hooks); extend the Spells step beyond level 1.
- **Phase 3 — Thief skills** subsystem and Turn Undead.

## Conventions to follow (per CLAUDE.md)

- New rules/tables go in `char_rules.py` (pure, single source of truth); the
  builder and Roll20 export delegate — never duplicate a rule.
- Each new pure function gets a `tests/test_char_rules.py` (or new) test.
- Keep it Qt-free; the UI wiring lives in `charactermancer.py` / `_html.py` / `app.py`.

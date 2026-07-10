# Feature plan: Combat & Tactics character-building rules

Status: **complete** (phases 0–7) · Created 2026-07-09 · Updated 2026-07-09

> **Sequencing.** Leveling Phase 1 lands *before* CT phases 1+: CT's top four rungs
> (mastery / high / grand mastery) are gated on 5th–6th level, and `Character` has no
> `level` field yet. See [`leveling-plan.md`](leveling-plan.md). CT **Phase 0 is pure
> data** and shipped ahead of it.

Adopt the *Player's Option: Combat & Tactics* (CT) character-building rules —
**Chapter Four** (weapon specialization & mastery) and the character-building
slice of **Chapter Five** (unarmed & martial arts) — while keeping the campaign's
homebrew weapon list and spells.

## Scope

**In** (CT Ch4, the chargen slice of Ch5, plus the style *list* from Ch2 that Ch4
depends on):

| Feature | CT pages |
|---|---|
| Weapon mastery ladder (nonproficiency → grand mastery) | `CT/DD02629`–`DD02644` |
| Weapon groups (tight/broad): familiarity + 2-slot group proficiency | `CT/DD02622`, `DD02623` |
| Intelligence bonus slots for warriors | `CT/DD02620` |
| Barred weapons (+1/+2 slot penalty) | `CT/DD02624` |
| Shield proficiency · Armor proficiency | `CT/DD02627`, `DD02628` |
| Fighting style specializations | `CT/DD02645`–`DD02652`, styles at `CT/DD02495` |
| Special talents (12) | `CT/DD02653`–`DD02665` |
| **Pummeling / Wrestling skill levels** (same ladder, weapon slots) | `CT/DD02674`, `DD02687` |
| **Martial arts styles A–D** (1 weapon slot each) | `CT/DD02700`–`DD02703` |
| **Martial arts talents (6)** | `CT/DD02705` |
| **The tight/broad group taxonomy itself** | `CT/DD02744` |
| **Siege proficiencies (2)**: Artillerist, Vehicle Handling | `CT/DD02824` |

**Out, deliberately:**
- **Ch7 Master Weapon List / Weapons Tables / weapon stats.** We keep the homebrew
  weapons in `equipment.py` / `char_rules.WEAPONS`. Note the **group taxonomy lives
  on its own page** (`CT/DD02744`), *separate* from the weapon list — so we can take
  the classification without taking a single weapon stat.
- **Spells.** (Non-issue: CT has no spell chapter. Confirmed against `toc_tree`.)
- **Combat resolution:** Ch1 combat system, Ch2 attack options/dueling, Ch3
  battlefield, Ch6 critical hits, Ch8 siege *warfare*, Ch9 monsters — and the
  *procedural* half of Ch5 (brawling, pummeling/wrestling procedures, holds, locks,
  pins, subdual, attacks of opportunity). We buy the **skill levels**, not the maths.

### Chapter sweep (done 2026-07-09 — don't redo this)

Every CT page was mapped to its chapter and scanned for chargen signals (slot-cost
headers, "proficiency slot", "Groups:", "Initial rating"). Result:

| Chapter | Chargen content? |
|---|---|
| One — Combat System | **No.** Only *Cover* (`DD02428`) *references* bow/crossbow proficiency as a prerequisite for a combat action. |
| Two — Combat Options | The **fighting-style list** (`DD02495`) that Ch4 specializes; *Unarmed Style* (`DD02503`) just points at Ch5. |
| Three — The Battlefield | **None.** |
| Four — Specialization & Mastery | **Everything.** 32 pages. |
| Five — Unarmed Combat | Skill levels + martial arts + MA talents (see below). |
| Six — Critical Hits | **None.** |
| Seven — Weapons & Armor | **`DD02744` weapon-group taxonomy** (in scope). `DD02730` notes tools may be taken as weapon proficiencies at DM discretion (ignored). Weapon list/stats out. |
| Eight — Siege Warfare | **`DD02824`**: two proficiencies — Artillerist (1 slot, Cha/Leadership, Warrior) and Vehicle Handling (1 slot, Dex/Dodge, Warrior). "Acquired the same way standard PHB proficiencies are." |
| Nine — Monsters | **None.** |

> **Consequence.** Several mastery *effects* reference CT combat subsystems we're
> not importing (crit on 16+, speed-factor categories, extreme range, knockdown
> dice). The engine will **record the rung** and surface its effects as text; it
> won't compute them. That's the right boundary — the same way the app already
> stores a proficiency without simulating a skill check.

## The rules being encoded

### Mastery ladder — cumulative slots on *one* weapon

| Rung | Slots | Who | Level | Effect |
|---|---|---|---|---|
| Nonproficiency | 0 | all | — | full nonproficiency penalty |
| Familiarity | 0 | all | — | half penalty; any weapon in a tight group you're proficient in |
| Proficiency | 1 | all | — | normal use |
| Expertise | 2 | paladin, ranger, multi-class fighter | — | specialist's *attack rate*; **no** to-hit/damage bonus |
| Specialization | 2 | single-class fighter only | — | attacks + to-hit/damage, varying by weapon category |
| Mastery | 3 | single-class fighter | 5th | must specialize first |
| High Mastery | 4 | single-class fighter | 6th | speed factor +1 category; crit on 16+; extreme range |
| Grand Mastery | 5 | single-class fighter | — | +1 attack/round; damage & knockdown die up one size |

Constraints:
- A fighter may specialize in **one weapon at a time**. Re-specializing costs 2
  extra slots, then **3 each** thereafter; the old weapon stays merely proficient and
  the slots it consumed are gone (see `sunk_slots`).
- Mastery slots can't be gained faster than weapon-proficiency slots (master at
  5th → 2nd mastery slot at 6th, 3rd at 9th).
- Specialization benefits differ by category: **melee / missile / bows /
  crossbows** (firearms: skip, not in our setting).

### Other things weapon slots can buy
- **Weapon group proficiency** — 2 slots, grants proficiency in every weapon of one tight group.
- **Shield proficiency** — 1 slot:

  | Shield | Normal AC | Proficient AC | Attackers blocked |
  |---|---|---|---|
  | Buckler | +1 | +1 | 1 |
  | Small | +1 | +2 | 2 |
  | Medium | +1 | +3 | 3 |
  | Body | +1 / +2 vs missiles | +3 / +4 vs missiles | 4 |

- **Armor proficiency** — 1 slot: count only **half** that armor's weight toward encumbrance.
- **Fighting styles** — warriors know every style free; nonwarriors pay 1 slot to
  *learn* one. *Specializing* costs 1 slot. Warriors may specialize in any number
  of styles; priests and rogues in only one. Rangers get the first slot of
  two-weapon style specialization free.
- **Barred weapons** — rogue/priest learning a warrior weapon: **+1 slot**; wizard
  learning a priest/rogue weapon: **+1**; wizard learning a warrior-only weapon: **+2**.
- **Intelligence** — fighters/paladins/rangers may spend their bonus *language*
  slots on weapon proficiencies; everyone else only on nonweapon proficiencies.

### Fighting styles
Weapon & Shield · One-Handed Weapon · Two-Handed Weapon · Two-Weapon ·
Missile or Thrown Weapon (+ Horse Archers, Local, Weapon-Specific).

Two-Weapon is the interesting one: normally −2 primary / −4 off-hand; specialized
→ 0 / −2; **ambidextrous + specialized → 0 / 0**. A second slot allows two
equal-sized weapons. Rangers have the first slot free.

### Special talents (bought with weapon slots; starred ones also with NWP slots)

| Talent | Slots | Ability | Groups | Rating |
|---|---|---|---|---|
| Alertness | 1 | Wis/Intuition +1 | All | — |
| **Ambidexterity** | 1 | Dex | Warrior, Rogue | — |
| Ambush | 1 | Int/Reason | Warrior, Rogue | 5 |
| Camouflage | 1 | Int/Knowledge | Warrior, Rogue | 5 |
| Dirty Fighting | 1 | Int/Knowledge | Warrior, Rogue | 5 |
| Endurance | 2 | Con/Fitness | Warrior | 3 |
| Fine Balance | 2 | Dex/Balance | Warrior, Rogue | 7 |
| Iron Will | 2 | Wis/Willpower −2 | Warrior, Priest | 3 |
| Leadership | 1 | Cha −1 | Warrior | 5 |
| Quickness | 2 | Dex | Warrior, Rogue | 3 |
| Steady Hand | 1 | Dex | Warrior, Rogue | — |
| Trouble Sense | 1 | Wis/Int | General | 3 |

### Chapter Five — unarmed combat (the chargen slice)

The unarmed disciplines are bought with **weapon proficiency slots** and reuse the
very same rung ladder, so they model cleanly as *pseudo-weapons*:

| Discipline | Free rung | Can advance to | Notes |
|---|---|---|---|
| **Brawling** | universal | — | No slots, no levels. Nothing to model. |
| **Overbearing** | familiar | **nothing** | CT: "not possible to develop overbearing expertise, specialization, or mastery." |
| **Pummeling** | familiar | proficient → expert → specialist → master | **Nonwarriors gain no benefit** from proficiency. |
| **Wrestling** | familiar | proficient → expert → specialist → master | Same nonwarrior caveat. |
| **Martial arts** (4 styles) | *none* | proficient → expert → specialist | Familiarity has **no effect** here. |

**Martial arts** (`CT/DD02700`–`DD02703`) — four styles, each costing **1 weapon
proficiency** and **learned separately** (CT is explicit: *"the four martial arts
styles do not constitute a weapon group"*, so no familiarity and no group
proficiency). A character may be **proficient in several styles and the benefits
are cumulative**, but may be **expert in only one** and **specialist in only one**
(specialization generally single-class fighters only). Style A strikes with hands
(1d3), Style B with feet (1d6); C and D per the book. Proficiency requires a
cultural background — a **DM gate**, not a mechanical one.

**Martial arts talents** (`CT/DD02705`) — all **1 slot**, purchasable with **either
weapon or nonweapon slots**, and all require **proficiency in at least one martial
arts style** (plus DM approval):

| Talent | Ability | Groups | Rating |
|---|---|---|---|
| Flying Kick | Str/Muscle | Warrior | 5 |
| Backward Kick | — | Warrior, Priest, Rogue | — |
| Spring | Dex/Balance | Warrior, Rogue | 5 |
| Crushing Blow | — | Warrior, Priest, Rogue | — |
| Instant Stand | Dex/Balance | Warrior, Priest, Rogue | — |
| Missile Deflection | — | Warrior, Priest, Rogue | — |

> Two structural consequences. (1) The ladder needs a **per-entry rung cap**
> (Overbearing: none; martial arts: specialist; weapons: grand mastery) and a
> per-entry **familiarity flag** (off for martial arts). (2) Talents need a
> `slot_type` of *weapon* / *nonweapon* / *either* and a **prerequisite** — both of
> which the existing nonweapon-proficiency machinery already models
> (`proficiency_prereqs_met`), so reuse it rather than inventing a parallel system.

## Reconciling with the campaign's house rules

Decision: **house rules layer on top of CT.**

- `HOUSE_RULES.weapon_slot_cost` (crossbows free, bows 2 slots) applies to the
  **first/proficiency** slot; CT's ladder costs stack above it.
- **Ambidexterity is already implemented.** `HOUSE_RULES.ambidexterity_slot_cost=1`
  + `Character.can_buy_ambidexterity()` (warrior/rogue) is *exactly* the CT talent.
  Do **not** add a duplicate — fold the existing `bought_ambidexterity` flag into
  the new talent system as its canonical entry.
- `HOUSE_RULES.ranger_ambidextrous` and CT's "ranger gets the first two-weapon
  style slot free" are compatible; keep both. The campaign's d10 handedness roll
  layers on top (already moved to the Proficiencies step).

## Data we must author (the real work, and the main risk)

Most of this is *transcription*, not invention — the sweep found CT's group taxonomy
on its own page. What's left for our homebrew weapons / armor:

1. ✅ **Tight & broad groups** — *imported* from `CT/DD02744` into
   `char_rules.WEAPON_TIGHT_GROUPS` / `TIGHT_TO_BROAD`.
   - ⚠ **Many-to-many.** A weapon belongs to *several* tight groups (`Short Sword` is
     *Ancient*, *Middle Eastern* **and** *Short*). The model is
     `weapon → tuple[tight_group, …]`. Familiarity is the **union** of the tight
     groups of every weapon you're proficient in (`cr.is_familiar`).
   - ⚠ **"Unrelated:" is not a group.** CT's fallback: *"If a weapon does not appear in
     the preceding listings, it belongs to no weapon group."* On our roster that's
     **Trident** (listed as Unrelated), **Quarterstaff** and **Sling** (absent) → no
     familiarity, no group proficiency.
   - ⚠ Don't substring-match CT's lists: our generic `Mace`/`Club`/`Flail`/`Spear`
     match *footman's mace*, *great club*, *horseman's flail*, *long spear*. The
     roster was hand-mapped, not auto-matched.
   - Firearms / Lances / Chain & Rope / Martial Arts Weapons groups: not on our roster.
2. ✅ **Class permission** per weapon → `char_rules.WEAPON_ACCESS` +
   `barred_weapon_penalty()`. Modelled as CT's coarse three tiers
   (`wizard` < `priest_rogue` < `warrior`), which reproduces CT's own worked example
   (a wizard pays **2** slots for a long sword, **3** for a two-handed sword).
   Deliberately does **not** model finer PHB per-class limits (clerics being
   bludgeoning-only) — CT leaves those to the DM, and so do we.
3. ✅ **Shield type** mapping → `char_rules.SHIELD_TYPES` + `SHIELD_PROFICIENCY`.
   `Shield, Buckler` → buckler; `Shield, Aspis` → **medium** (DM ruling 2026-07-09:
   a large round hoplite shield at +2 AC).
4. **Armor proficiency** over the piecemeal armor set (Gambeson/Leather/Chain/Plate
   × Full/Body/Limbs/Cuirass, plus Helms).
5. **Specialization benefit tables** by category (melee / missile / bow / crossbow).
6. **Unarmed pseudo-weapons** — Pummeling, Wrestling, Overbearing, Martial Arts
   Styles A–D — each with its rung cap, familiarity flag, and whether nonwarriors
   benefit. (Transcribed from Ch5; no homebrew judgement needed.)

Items 1–2 are one-off classification of 24 rows — cheap, but they are *judgement
calls* and should be reviewed by the DM before code depends on them.

## Architecture

Respects the layering rule in [CLAUDE.md](../CLAUDE.md) — all logic Qt-free:

```
char_rules.py         all new tables + pure functions (single source of truth)
character.py          new state + derivations
charactermancer.py    dispatch verbs + validation
charactermancer_html.py   the Proficiencies step UI
roll20_export.py      carry invested slots into the sheet's WP section
```

### The data-model change (the biggest single risk)

`Character.weapon_profs: list[str]` → **`dict[str, int]`** (weapon → slots
invested), mirroring the existing `nonweapon_profs: dict[str, int]`. The *rung* is
then derived, never stored:

```python
cr.weapon_rung(slots, char_class, level)  # -> 'proficient' | 'expert' | 'specialist' | 'master' | ...
```

New character state: `weapon_groups`, `shield_profs`, `armor_profs`,
`fighting_styles` (style → slots), `special_talents` (talent → slots).
`bought_ambidexterity` migrates into `special_talents["Ambidexterity"]`.

> **Backward compatibility.** Saved characters persist `weapon_profs` as a *list*
> and `bought_ambidexterity` as a bool. `Character.from_dict` must migrate
> (`[w, …]` → `{w: 1}`) and `CharacterLibrary` / the Roll20 payload must keep
> working. This is where regressions will happen — cover it with tests first.

### New `char_rules` surface (sketch)

- `WEAPON_TIGHT_GROUPS: dict[str, tuple[str, ...]]` (many-to-many; `()` = no group),
  `TIGHT_TO_BROAD`, `weapon_group_members()`, `is_familiar(weapon, profs)` = "shares a
  tight group with any weapon you're proficient in"
- `MASTERY_RUNGS`, `weapon_rung()`, `max_rung(entry, char_class, level)`
- `weapon_prof_cost(weapon, target_rung, char_class, house_rules)` (incl. barred penalty)
- `SHIELD_PROFICIENCY`, `ARMOR_PROFICIENCY`
- `FIGHTING_STYLES`, `styles_known_free(char_class)`
- `SPECIAL_TALENTS` (name, slots, ability, modifier, groups, initial_rating, slot_type, prereq, description)
- `UNARMED_DISCIPLINES` — Pummeling/Wrestling/Overbearing/Martial Arts A–D, each with
  `rung_cap`, `allows_familiarity`, `nonwarrior_benefit`; martial arts also carry the
  "expert/specialist in only one style" constraint
- `weapon_slots(char_class, level, int_score)` — **add** the warrior Int-bonus slots

### Encumbrance hook
`Character.total_weight()` must count **half** the weight of armor the character
has armor proficiency in, which flows into `encumbrance()` and the Roll20 gear
export.

## Phasing

Each phase ships independently with tests. **Phases 1–6 are all reachable at level
1**, so they land in the current builder; phase 7 needs leveling.

| Phase | Work |
|---|---|
| ~~**0**~~ | ✅ **Done.** `WEAPON_TIGHT_GROUPS`, `TIGHT_TO_BROAD`, `weapon_tight_groups/broad_groups/group_members`, `is_familiar`, `WEAPON_ACCESS`, `barred_weapon_penalty`, `SHIELD_PROFICIENCY`, `SHIELD_TYPES` — all in `char_rules.py`, tested, **nothing consumes them yet**. Armor-proficiency mapping deferred to phase 3 (each armor item is its own type). |
| ~~**1**~~ | ✅ **Done.** The rung ladder in `char_rules` (`weapon_rung_ladder`, `next/prev_weapon_rung`, `weapon_prof_cost`, `specialises`), `Character.weapon_profs` as `{weapon: rung}`, and mastery steppers on the Proficiencies step. **Deviation from this plan:** the state is the *rung*, not slots-invested — with the house-rule costs, "2 slots on a Long Bow" is indistinguishable from "expert with a dagger", so slots are derived from the rung instead. Level gates work (mastery 5th, high 6th, grand 9th) now that leveling Phase 1 landed. |
| ~~**2**~~ | ✅ **Done.** `Character.weapon_groups`: 2 slots buys proficiency in every weapon of one tight group. Buying a group **refunds** the now-redundant per-weapon proficiencies it grants; a group-covered weapon can still be specialised for the *extra* rung slot only (its proficiency slot was paid by the group), and stepping back down drops the entry entirely. Familiarity is computed over the union of explicit and group-granted proficiencies. |
| ~~**3**~~ | ✅ **Done.** `shield_profs` / `armor_profs`, one weapon slot each. Armor proficiency halves that armor's encumbering weight, which flows through `total_weight()` → `encumbrance()` → the Roll20 gear export, so the sheet's encumbrance matches the builder's. **Important:** the *homebrew item* owns a shield's normal AC bonus (our Aspis is +2 where CT's medium shield is +1); CT's table only supplies the **proficient upgrade**, and `max()` guarantees it never lowers a shield. Routing the normal case through CT's table silently cost every non-proficient character 1 AC — caught by driving it, not by the tests. |
| ~~**4**~~ | ✅ **Done.** `fighting_styles: {style: specialisation slots}`. Warriors know every style free and may specialise in as many as they can afford; priests and rogues pay a slot to learn one and may specialise in **only one**; wizards may learn but never specialise. Rangers hold the first two-weapon specialisation slot free. `two_weapon_penalty()` is the payoff: −2/−4 normally, 0/−2 specialised, −2/−2 ambidextrous, and **0/0 for both**. |
| ~~**5**~~ | ✅ **Done.** All 12 talents in `char_rules.SPECIAL_TALENTS`, gated by class group. `Character.bought_ambidexterity` is now a **property** backed by `special_talents["Ambidexterity"]` — the campaign house rule *is* the CT talent, so there is one implementation, and legacy saves holding the old bool migrate into it. CT's asterisk turns out to mark exactly **Alertness and Endurance**; those two may be paid for from the *nonweapon* budget, which the talent state records per-talent. |
| ~~**6**~~ | ✅ **Done (fell out of phase 1).** `weapon_prof_cost` already adds `barred_weapon_penalty`, so a mage's long sword costs 2 slots and a two-handed sword 3. The buy list badges the penalty. Pleasingly, this reproduces CT's own remark that "the limited number of weapon proficiencies available for nonwarrior characters will tend to control character abuse of this rule" — a 3rd-level mage has one slot and simply cannot afford a barred long sword. |
| ~~**6.5**~~ | ✅ **Done.** `unarmed_profs` rides the same rung ladder. Overbearing has an empty ladder (cannot be advanced); pummeling/wrestling reach master; martial arts stop at specialist. **Expertise is open to any class here** (unlike weapons) — only specialisation and mastery are the single-class fighter's. Martial arts confer no familiarity on each other (CT: they "do not constitute a weapon group"), you may be expert or specialised in only one style, and dropping your last style prunes the martial-arts talents that required it. |
| ~~**6.6**~~ | ✅ **Done.** Artillerist and Vehicle Handling, warrior-only, drawing on the **nonweapon** budget. Rather than touch the generated NWP table, `SpecialTalent` gained a `slot_source` (`weapon` / `nonweapon` / `either`) which also cleanly replaced the ad-hoc `either_slot` flag from phase 5. |
| ~~**7**~~ | ✅ **Done.** Mastery/high/grand mastery landed in phase 1 (gated at 5th/6th/9th). The escalating **re-specialisation** cost is now modelled: the first specialisation costs 1 extra slot, moving it costs 2, and every later move 3. The old weapon keeps its proficiency forever but its extra slots are **sunk, not refunded** — `Character.sunk_slots` keeps them counting against the budget, which is what CT means by "loses all benefits of specializing in the previous one". |

## Tests
- `char_rules`: rung table + gates, cost function (house rules + barred penalty),
  group membership/familiarity, talents, shield/armor tables, warrior Int slots.
- `character`: **legacy `from_dict` migration**, slot accounting, encumbrance halving.
- `charactermancer`: dispatch refuses over-budget / illegal rung / second specialization.
- `roll20_export`: `wpsslots` carries invested slots; legacy payloads still build.
- `charactermancer_html`: renders rungs, budgets, and the new sections.

## Roll20
The sheet's `repeating_wps` section already has a **`wpsslots`** column — export the
invested slots there instead of the current hardcoded `1`. Fighting styles and
special talents have no native home on the sheet (open question below).

## Open questions
1. ~~**Talent checks.**~~ **Answered (2026-07-09): use the PHB check,
   `d20 ≤ ability + modifier`.**

   CT prints *two* notations on each talent line because it supports two proficiency
   systems. `Intelligence/Reason` and the `, +1` / `, -2` are the **PHB** form
   (score = ability + modifier). `Initial rating: 5` is the **Skills & Powers** form
   of the *same check*, where the score starts at a flat 3–8 and the ability only
   nudges it through S&P's ±5 Table 44. They are not cumulative — they're
   alternatives, and they differ wildly: an Int-15 Ambush is **75%** under the PHB
   and **35%** under S&P.

   The campaign spends proficiency slots, not character points, so the PHB reading
   is the consistent one. `Character.talent_skill()` already returns
   `ability + modifier`; `initial_rating` stays in `char_rules` for fidelity but is
   **no longer shown in the UI** — two numbers on a row only invite the wrong roll.
   Note the house-rule `+2 per extra slot` never applies to a talent: it's a single
   purchase, so the check is just the ability plus the book's modifier.
2. ~~**`Shield, Aspis`** → CT "medium" or "body"?~~ **Answered: medium.**
3. **Roll20**: where do fighting styles / special talents / unarmed disciplines live —
   NWP rows, WP rows, or notes?
4. **Specialization benefit tables** — transcribe melee/missile/bow/crossbow now, or
   record the rung and let the DM adjudicate?
5. ~~**Martial arts in this campaign?**~~ **Answered (2026-07-09): they exist.** All
   four styles (A–D) are available; no flavour gate in the builder.
6. **Nonwarrior pummeling/wrestling.** CT says nonwarriors gain *no benefit* from
   proficiency. Should the builder let a wizard spend the slot anyway (RAW: yes,
   pointless), or block it as a footgun? *Currently: allowed, and the row says
   "nonwarriors gain no benefit".*

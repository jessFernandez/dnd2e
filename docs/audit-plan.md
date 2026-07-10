# Code / architecture audit

Status: **complete** (phases 1–8 landed) · Last updated: 2026-07-10
Baseline was `master` @ `577421c` (413 passed, 1 skipped; 70% line coverage). After
the audit: **955 passed, 1 skipped**; char_rules 98%, character 96%, the tables now
checked against the rulebook itself. Each phase is a commit on `feat/combat-tactics-phase0`
(`925f7ab` … `cd72f4b`).

Everything below is measured, not guessed. Each finding names the probe that produced
it so it can be re-run after the fix.

## Summary of what's actually wrong

The engine is in better shape than the numbers suggest, and the *tests* are in worse
shape than the numbers suggest. `char_rules.py` reports 98% line coverage, but the
hundreds of transcribed rulebook numbers inside it are barely asserted — the suite
exercises the functions that read the tables without pinning what the tables say.
Meanwhile a sweep of every legal race × class × level found no crashes and no broken
invariants at all. Fix the tests first; the code needs tuning, not rescue.

---

## Finding 1 — Transcribed table data is effectively untested (**highest value**)

The rulebook tables in `char_rules.py` are hand-copied numbers. Corrupt one and the
suite stays green.

Probe (mutate a value, run the whole suite):

| Mutation | Result |
| --- | --- |
| `_THIEF_BASE["Pick Pockets"]` 15 → 16 | **survived** |
| `_THIEF_RACIAL["Dwarf"]["Find/Remove Traps"]` +15 → +14 | **survived** |
| `_TURN_UNDEAD["Wight or 5 HD"]` column 4 → 5 | killed |
| `THIEF_SKILL_MAX` 95 → 96 | killed |
| `roll20_export` always exports level 1 | killed |
| `Charactermancer.add_weapon` budget guard removed | killed |

Only **2 assertions in the entire suite** reference a table constant. The turn-undead
mutation died solely because `test_thief_skills.py` asserts the table's *diagonal
property* — a structural invariant rather than a transcription of the numbers. That's
the technique to generalise.

### The fix, in two layers

**(a) Check the transcription against the book.** The rulebook is *in the repo*, in
`dnd2e.db`. A test can parse the source page and compare it to the constant. Prototyped
and working:

```
Table 26 (base scores):        8 skill rows parsed, 0 mismatches
Table 27 (racial adjustments): 8 rows x 5 races = 40 cells, 0 mismatches
corrupting _THIEF_BASE["Climb Walls"] in memory -> mismatch reported (check is live)
```

Note the trap: the first version of that parser split rows on `</tr>`, matched nothing,
and reported "0 mismatches" from **0 rows compared**. Any test added here must assert
the *row count it parsed* before asserting agreement, or it proves nothing.

Candidates, all clean HTML tables with a stable page URL:

| Table | Page | Constant |
| --- | --- | --- |
| 26 thief base | `PHB/DD01501` | `_THIEF_BASE` |
| 27 thief racial | `PHB/DD01502` | `_THIEF_RACIAL` |
| 28 thief Dexterity | `PHB/DD01503` | `_THIEF_DEX` |
| 29 thief armor | `PHB/DD01504` | `_THIEF_ARMOR` |
| 61 turning undead | `PHB/DD01734` | `_TURN_UNDEAD` |
| 21 / 24 spell slots | wizard / priest | `_WIZARD_SPELL_SLOTS`, `_PRIEST_SPELL_SLOTS` |
| saves, THAC0, XP | (locate) | `_SAVES`, THAC0/XP tables |

Guard with the existing `needs_db` skipif so the suite still runs without `dnd2e.db`.

**(b) Property tests for the tables the book renders as prose or a shape.** The
diagonal test is the model: assert the structure, not 156 numbers. Spell progressions
are monotonic per level; saves never increase with level; THAC0 never increases; the
XP table is strictly ascending. These catch transposition errors the cell-by-cell
check would also catch, but they keep working if a page's HTML changes.

## Finding 2 — Coverage collapses at the Qt edge

| Module | Stmts | Cover | Note |
| --- | --- | --- | --- |
| `app.py` | 1167 | **20%** | 114 functions; `_build_ui` alone is 215 lines |
| `calculator.py` | 83 | **18%** | contains two *pure* functions (below) |
| `proficiencies_html.py` | 58 | **21%** | pure string templating, **zero tests** |
| `rules_agent.py` | 265 | 52% | `_retrieve` is 80 lines |
| `charactermancer_profs_html.py` | 323 | 79% | newest code, thinnest view coverage |

`proficiencies_html.py` is pure and has no test at all — the cheapest coverage win in
the repo. The `app.py` number is expected for a Qt shell, but 1167 statements is a lot
of shell; see Finding 4.

## Finding 3 — Pure logic marooned in a Qt module

`calculator.py` correctly *re-exports* the house-rule conversions from `char_rules`
(the CLAUDE.md rule holds). But it also **defines** two pure functions, `to_hit_need`
and `hit_chance`, which can only be imported by dragging in PyQt — which is why they
are untested. They belong in `char_rules.py`.

While reading it: the module docstring and an on-screen hint both promise "crit on a
natural 18+ that beats AC by 5+". **No code computes that.** It's a reference note to
the player, not a bug, but the rule exists nowhere in the engine and nothing tests it.
Decide whether it should be `char_rules.is_critical(nat_roll, margin)` or stay prose.

## Finding 4 — Two oversized control structures

- **`Charactermancer.dispatch`** is a 127-line `if verb == ...` chain over **52 verbs**.
  Every new feature this month appended to it. Replace with a verb → handler table;
  the arity split (`verb`, `verb/tail`) is uniform enough to dispatch declaratively,
  and an unknown verb still returns `False`. This also makes "is every verb reachable
  from the rendered HTML?" a testable question.
- **`app.py::_build_ui`** at 215 lines. CLAUDE.md already names session save/restore
  (`_save_session` / `_restore_session`) as the next extraction, following
  `character_library.py` and `ask_controller.py`. Bookmarks and zoom/find are the two
  other Qt-light clusters.

## Finding 5 — Test-suite hygiene

- `tests/retrieval_report.py` is **not collected** by pytest (no `test_` prefix) and is
  **referenced by nothing**. `answer_eval.py` and `golden_retrieval.py` are also
  uncollected but are imported by real tests, so they're legitimate helpers.
  Move `retrieval_report.py` to `scripts/` or delete it.
- Three tests contain **no assertion**: `test_ask_stop_with_no_worker_is_noop`,
  `test_actionsscreen`, `test_spells_screen_empty`. The first is a legitimate
  "doesn't raise" check but should say so with an explicit assertion; the other two are
  smoke tests that would pass on an empty string.
- One skip, `test_answer_quality.py` behind `JARVIS_LIVE=1`. Intentional and correct.
- `rules_agent.py:491` swallows a broad exception with a bare `pass`. It's the only
  silent swallow in the app; confirm it's deliberate and comment it.

## Finding 6 — What the audit *cleared*

Worth recording so nobody re-audits it:

- **Layering is intact.** Only `app.py`, `calculator.py`, `rules_agent.py` import PyQt.
  `char_rules` imports nothing upward.
- **No mutable default arguments, no bare `except:`, no `== None`, no stray `print()`,
  no TODO/FIXME/XXX/HACK** anywhere in the app code.
- **The engine is robust.** A sweep over every legal race × class × level (respecting
  each race's class list and level cap) calling `max_hp`, `thac0`, `saving_throws`,
  `attacks_per_round`, `spell_slots`, `turn_undead`, `thief_skill_scores`,
  `armor_class`, `movement`, and a `to_dict`/`from_dict` round-trip produced
  **0 exceptions and 0 invariant violations** (no negative budgets, no HP below level,
  round-trip stable). This sweep should become a permanent test — it is worth more than
  most of the hand-written cases.
- **The guard-predicate pattern is consistent**: 19 `can_*` methods on `Character`,
  each called once by the controller and once by the view.

---

## Outcome (all phases landed)

1. ✅ **Table-transcription tests** — `test_rulebook_tables.py` checks Tables 26–29,
   60, 61, 21, 24 against their `dnd2e.db` pages, asserting parsed row/column counts
   first. The two mutations that used to survive now die.
2. ✅ **Property tests** — `test_rules_invariants.py`: saves/THAC0 never worsen, XP
   strictly ascends and `level_for_xp` inverts `xp_for_level`, spell slots never
   shrink, attacks never decrease.
3. ✅ **The sweep** — every legal race × class × level built and fully derived
   (~470 parametrized cases); zero exceptions, zero invariant violations.
4. ✅ **Combat math moved to `char_rules`** — `to_hit_need`/`hit_chance` left the Qt
   module; `is_critical` (with `CRIT_MIN_ROLL`/`CRIT_MIN_MARGIN`) implements the
   previously-prose-only crit rule and the converter now displays it live.
5. ✅ **`proficiencies_html` tested** — 21% → 100%.
6. ✅ **Hygiene** — `retrieval_report.py` moved to `scripts/`; the bare test got an
   assertion; the silent `except` is commented.
7. ✅ **`dispatch` is tables** — 127-line chain → three dicts + 7 explicit branches,
   proven equivalent over 918 verb×tail cases; `handles()` + a wiring test catch a
   dead button.
8. ✅ **Session coercions extracted** — `session.py`, pure and tested.

## Proposed order (as executed)

Cheapest and highest-value first; each phase is independently shippable.

1. **Table-transcription tests** (Finding 1a). Start with Tables 26–29 and 61, where
   the parser is already proven. Assert parsed row counts. ~1 test module.
2. **Table property tests** (Finding 1b) for the progressions the cell check can't
   reach. Re-run the mutation probes above; they must all die.
3. **The race × class × level sweep** as a permanent test (Finding 6).
4. **Move `to_hit_need` / `hit_chance` into `char_rules`** and test them; decide the
   crit rule's fate (Finding 3).
5. **Test `proficiencies_html`** (Finding 2) — pure, 58 statements, no tests.
6. **Test-suite hygiene** (Finding 5): relocate `retrieval_report.py`, give the three
   assertion-free tests assertions, comment the silent `except`.
7. **`dispatch` verb table** (Finding 4). Behaviour-preserving; verify with the same
   byte-identical-render technique used for the `charactermancer_html` split.
8. **Extract session save/restore from `app.py`** (Finding 4), the extraction CLAUDE.md
   already calls for.

Phases 1–3 change no application code and would have caught a real class of bug.
Phases 7–8 are refactors with no user-visible effect and should be proven by
before/after equivalence rather than by tests alone.

## Method notes

- Mutation probes: apply a one-line source change, run the full suite with
  `python -B -m pytest -q -x`, revert. **Set `PYTHONDONTWRITEBYTECODE=1`** — a stale
  `.pyc` from a mutation reverted within the same second will silently poison the next
  run, which happened during this audit and produced a bogus "everything differs".
- Refactor equivalence: render every step for a spread of builds and compare SHA-256
  per page, then mutate a constant to prove the comparison is not vacuous.

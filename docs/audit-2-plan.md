# Architecture / code-quality audit — round 2 (post-monster-mode)

Status: **in progress** on `chore/architecture-audit-2` · Written 2026-07-21 · Baseline
`feat/monster-mode-v2` @ `e8473d4`

| Phase | State |
|---|---|
| 1 — one coercing `esc` everywhere | **done** (1195 passed, 1 skipped) |
| 2 — tooling + invariant tests | **done** (1234 passed, 1 skipped; ruff clean) |
| 3 — `route_destination` | not started |
| 4 — search/bookmarks extraction | not started |
| 5 — `theme.py` | not started |
| 6 — JSON-blob store + `from_dict` coercion | not started |

Baseline, measured: **1182 passed, 1 skipped in 6.2 s**. Line coverage by module is in
Finding 2. The first audit ([`audit-plan.md`](audit-plan.md), complete 2026-07-10) left
the suite at 955 tests; monster mode v1+v2 added ~227.

Everything below names the probe that produced it, so each finding can be re-run after
the fix. Where this contradicts `CLAUDE.md`, `CLAUDE.md` is the thing that's wrong —
several of its claims describe an intent that was only partly carried out.

---

## Summary

The engine is in good shape and the layering rule that matters is genuinely holding.
The problems are **not** in the pure modules — they're at the seams:

1. Escaping is a per-module choice rather than a layer guarantee, and it has a
   **reproducible crash** behind it.
2. `app.py` is where all the untested logic now pools (28% covered, 966 uncovered
   statements) — every other quality metric is fine because everything hard was moved
   out, and what remains was never finished being moved.
3. The destination grammar is written down in two places, and the Qt copy is the
   authoritative one. This is `nav-controller-plan.md` phase 4, still open.
4. Several "shared" layers (`screen_common`, the palette, the persistence pattern) are
   shared by two callers and copy-pasted by the rest.

None of it is urgent. All of it gets more expensive once v3 (the Roll20 monster sheet)
adds a third consumer to each of these seams — which is the argument for doing it now.

---

## What the audit cleared

Checked and genuinely fine. **Don't spend effort here.**

| Claim | Probe | Result |
|---|---|---|
| Qt confined to 3 modules | `grep -ln PyQt5 *.py` | Exactly `app.py`, `calculator.py`, `rules_agent.py`. Holds. |
| No import cycles | AST import-graph walk over all root modules | Clean DAG, `char_rules` at the base. No cycles. |
| Pure modules are tested | `coverage report` | `monster_parser` 99%, `navigation` 100%, `monster` 100%, `monster_html` 100%, `char_rules` 98%, `character` 96%. |
| `dnd2e.spec` hiddenimports in sync | Set-difference of spec list vs `*.py` on disk | In sync (`app` correctly absent — it's the entry script). |
| Code hygiene | grep for `except:`, `TODO`/`FIXME`/`HACK`, mutable default args | Zero bare excepts, zero TODO rot, zero mutable defaults. |
| Suite speed | `python -m pytest -q` | 6.2 s for 1182 tests. Nothing to fix. |

`monster_parser.py` deserves a specific note: it's the module `CLAUDE.md` calls "the big,
fiddly layer", it's 979 lines, and it is **99% covered**. The parser/model split worked.

---

## Finding 1 — HTML escaping is six spellings with two different behaviours (**highest value**)

Two modules wrap `html.escape` in a coercing helper; the rest call it raw, under three
more names; one escapes nothing. Raw `html.escape` **raises on non-`str`**:

```
html.escape(None) -> AttributeError: 'NoneType' object has no attribute 'replace'
html.escape(5)    -> AttributeError: 'int' object has no attribute 'replace'
```

Spelling, per module:

| Module | Escapes as | Coerces? |
|---|---|---|
| `charactermancer_common` (→ `charactermancer_html`, `_profs_html`) | `esc` | **yes** |
| `proficiencies_html` | private `_esc` wrapper | **yes** |
| `monster_html` | `esc` | no |
| `actionsscreen_html`, `askscreen_html`, `dmscreen_html`, `splash_html` | `e` | no |
| `spellsscreen_html` | `escape` | no |
| `toc_html` | **nothing** — see 1b | — |
| `screen_common` | n/a — pure CSS/JS, interpolates no data | — |

Two modules independently arrived at the same coercing wrapper, which is the clearest
evidence the raw form doesn't survive contact with optional fields.

### 1a. Reproducible crash

```python
python -c "
import monster, monster_html
monster_html.generate(monster.Monster.from_dict({'name': None, 'armor_class': 5}))
"
# AttributeError: 'NoneType' object has no attribute 'replace'
```

Reachable from `monster_library.load()` → `Monster.from_dict(json.loads(raw))` whenever a
saved monster's JSON carries a `null` in a string field. `monster_html` guards *some*
call sites by hand (`esc(value or "—")`, `str(n)` in `_init_control`) and misses others
(`esc(m.name)` at monster_html.py:253) — which is exactly what "escaping is a per-call-site
habit" produces.

### 1b. `toc_html` doesn't escape at all, and real data needs it

`toc_html.py:27-45` interpolates `ch["name"]`, `ch["page_url"]`,
and house-rule `cat`/`text` straight from the DB with no escaping. Probe:

```
sqlite3 dnd2e.db: 9 toc_entries rows contain '<' or '&'
  "AD&D Game Line (Player's Handbook)"
  "Gear & Equipment"  "Food & Provisions"  "Employment & Wages"  ...
```

**Honest severity:** none of those bare `&` sequences form a valid entity name, so
browsers recover and it renders correctly *today*. This is invalid markup from real
data, not a visible breakage, and there is no untrusted input here — do not call it XSS.
It matters because it proves the gap is reachable with the data actually in the DB.

### Fix

One coercing `esc` in one place, imported by every view module; delete the four aliases.
`charactermancer_common.esc` is already correct but is named for the builder — promote it
to a neutral module (see Finding 5, which wants the same module for the palette).

Regression test worth having: parametrize over every public `generate*` in every view
module, feed it a model with `None`/`int` in each field, assert no exception. That single
test would have caught 1a.

### 1c. Follow-up found while fixing this — `Monster.from_dict` doesn't coerce

Writing the fuzz test turned up a *second*, unrelated crash on the same input shape.
It is **not** an escaping problem and was deliberately left out of phase 1:

```python
monster_html.generate(monster.Monster.from_dict({"armor_class": 5}))
# TypeError: expected string or bytes-like object, got 'int'
#   monster.py:155  _map_numbers -> re.sub(pattern, ..., text)
```

`_map_numbers` guards `if not text` (so `None` and `""` are fine) but a non-empty
non-string sails through into `re.sub`. **Not currently reachable** — `monster_parser`
only ever produces strings, so nothing writes a JSON number into a stat field — which is
why it's recorded rather than fixed.

The principled fix is at the boundary: `Monster.from_dict` is where untyped JSON becomes
a typed model, and it currently trusts the blob completely (`selected_tier` and
`initiative_override` are the only fields whose types it thinks about). Coercing declared
`str` fields there would close this and anything like it. That's a model-layer decision,
so it belongs with Finding 4's persistence work in phase 6, not here.

---

## Finding 2 — `app.py` is the coverage sink, and it's the *only* one

`python -m coverage run -m pytest -q && python -m coverage report --sort=miss --skip-covered`:

| Module | Stmts | Miss | Cover |
|---|---|---|---|
| **`app.py`** | **1350** | **966** | **28%** |
| `rules_agent.py` | 265 | 126 | 52% |
| `calculator.py` | 84 | 74 | 12% |
| `charactermancer_profs_html.py` | 330 | 69 | 79% |
| everything else | — | ≤44 | ≥91% |

`rules_agent` and `calculator` are Qt-by-design and their pure parts are already extracted
(`ask_controller`). **`app.py` is the real number.** It's 2210 lines and imports 25 of the
32 app modules — the 7 it doesn't touch are all reached transitively.

This is the same Finding 2 the first audit raised ("coverage collapses at the Qt edge").
The extractions since then (`ask_controller`, `session`, `navigation`, `character_library`)
all worked — the pattern is proven, it just hasn't been applied to what's left.

What's still in there, from the uncovered-line map:

- `_build_ui` (app.py:711, **215 lines** — the longest function in the codebase after
  `splash_html.generate`, which is a CSS blob and doesn't count)
- `_load_topics` + `_add_tree_node` (app.py:1108, 84+22 lines) — tree construction
- the search cluster (app.py:2000-2058) and bookmarks cluster (app.py:2062-2109) — the two
  `CLAUDE.md` already names as next candidates
- session restore/save, adjacent-page nav, tab management, house-rule callouts

### Fix

Phases 3 and 4 below. Note the pure logic in search/bookmarks is *small* but genuinely
duplicated — the same title-cleanup regex appears **three** times:

```
app.py:1144   _load_topics    re.sub(r"\s*\([^)]+\)\s*$", "", subtopic).strip()
app.py:2030   _show_results   re.sub(r"\s*\([^)]+\)\s*$", "", title or page_url).strip()
app.py:2082   _load_bookmarks re.sub(r"\s*\([^)]+\)\s*$", "", title or page_url).strip()
```

and `_show_results`/`_load_bookmarks` additionally share the book-colour lookup
(`BOOK_ITEM_COLORS.get(book_code or "", "#1a1d24")` — another palette literal, see
Finding 5).

That's the extractable part: a pure `display_title(text)` plus a
`list_row(title, book_name, book_code, snippet=None)` returning display text + colour,
with the Qt widget construction left behind.

---

## Finding 3 — The destination grammar lives in two files, and the Qt copy wins

`CLAUDE.md` says `navigation.py` "owns the grammar and the policy". It half does.

`navigation.takes_full_width` (`navigation.py:53-55`) knows the
monster destinations only as a prefix catch-all:

```python
or dest.startswith("monster-")     # monster-sheet, monster-variant/…
```

while `app._render_destination` (`app.py:1312-1335`) is the file that
actually enumerates them — a 20-line `if/elif` ladder re-parsing `"toc:"`, `"spells#"`,
`"monster-sheet"`, `"monster-family/"`, `"monster-variant/"`, `"proficiencies#"`. Probe:
grep those tokens in each file — `navigation.py` has one (`"toc:"`), `app.py` has all of them.

So adding a destination means editing both files, and the authoritative list is the one in
the untested module. `route_link` and `route_mon` both got the tagged-union treatment;
`_render_destination` never did.

This is **exactly** `nav-controller-plan.md`'s phase 4 (`classify(dest) -> Kind`), which
that doc still lists as remaining while its header says "in progress" and `CLAUDE.md` says
"phases 1–3 complete". The plan was right; it just stopped one phase early.

### Fix

`navigation.route_destination(dest) -> Dest` (tagged, mirroring `Route`/`MonAct`), so
`_render_destination` becomes a `match` of side effects and `takes_full_width` derives from
the same enumeration instead of a `startswith`. Unit-tested in `test_navigation.py` with no
Qt. Then update both docs.

---

## Finding 4 — The two libraries are the same object written twice

`character_library.py` and `monster_library.py` are structurally identical: hold a user-DB
connection, `ensure_*_schema` on every call, int-coerce the id in `load`/`delete`, store a
JSON blob from `to_dict`, keep loose columns for listing, return `None` on a malformed id.

Underneath, `db.py:240-334` is the same ~95 lines twice —
`ensure_characters_schema`/`ensure_monsters_schema`, `insert_`/`update_`/`all_`/`get_`/
`delete_` × 2 — differing only in table name and which loose columns are indexed.

Adding v3's saved-encounter or saved-Roll20-sheet storage would make it three times.

### Fix

A single parameterized JSON-blob store in `db.py` (table name + loose-column spec), and a
small shared base or helper for the two library classes. Keep the two public classes —
their *callers* differ (`CharacterLibrary.load` returns a `Charactermancer` positioned on
its last step; `MonsterLibrary.load` returns a `Monster`) and that difference is real.

Minor, same area: `character_library.roll20_payload` does a function-local
`import roll20_export` (character_library.py:80) as if guarding a cycle. There is no cycle
— `roll20_export` doesn't import `character_library`. Hoist it to module scope.

---

## Finding 5 — There is no shared design layer; the palette is copy-pasted

`CLAUDE.md`: "`screen_common.py` holds the shared card-grid chrome … `dmscreen_html.py`,
`actionsscreen_html.py`, `spellsscreen_html.py`, `splash_html.py` each just supply their
cards."

Probe — `grep -ln screen_common *.py`: importers are **`actionsscreen_html` and
`dmscreen_html`**. That's it. `spellsscreen_html` and `splash_html` are named in the doc
but don't import it; `monster_html`, `charactermancer_html`, `toc_html`,
`proficiencies_html`, `askscreen_html` each roll their own CSS.

Probe — unique hex colours per file, and how many files repeat each value:

```
67 unique colours  charactermancer_html.py       #c8cad8 appears in 10 files
38                 spellsscreen_html.py          #e6e9f6 appears in  8
32                 askscreen_html.py             #c9a84c appears in  8   <-- this one has a name
30                 splash_html.py                #5b9bd5 appears in  6
30                 actionsscreen_html.py         #5a6080 appears in  6
24                 screen_common.py              #23263a appears in  6
20                 monster_html.py               …
```

`#c9a84c` is *already* defined as `charactermancer_common.ACCENT` with a docstring saying
`app.py` reads it to tint the sidebar — and it's still hardcoded as a literal in 8 files.
`app.py` has 9 `setStyleSheet` calls carrying the same palette into Qt.

### Fix

A `theme.py` with the palette as named constants (and the handful of shared CSS fragments),
imported by every view module *and* by `app.py` for its Qt stylesheets. This is the same
module Finding 1 wants for `esc` — one small pure `view_common.py`/`theme.py` serves both,
and `charactermancer_common.py` folds into it or keeps only the builder-specific `ABBR`
and `budget_bar`.

Do this **before** v3 adds a tenth stylesheet.

---

## Finding 6 — A logic module imports a view module

`monster_spells.py` imports `spellsscreen_html` for `spell_slug()`. `CLAUDE.md` defends
this ("so a link can't drift from the anchor it points at") and the *goal* is right — one
owner for the slug — but the dependency points the wrong way through the layers: the
monster stack's logic now can't be imported without the spell screen's view code.

### Fix

Move `spell_slug()` into a tiny pure module (or `theme.py`'s neighbour — a `slugs.py`);
`spellsscreen_html` and `monster_spells` both import it. The anti-drift property is
preserved — strengthened, actually, since the slug no longer lives in a file whose job is
CSS.

Low effort, low risk, do it alongside Finding 5.

---

## Finding 7 — No lint, no CI, no pinned deps

- No `pyproject.toml`, `setup.cfg`, `.ruff.toml`, `mypy.ini`, `pytest.ini`, or
  `.github/workflows/`. Probe: `ls` for each — none exist.
- `requirements.txt` pins nothing (`PyQt5>=5.15.0`) and omits the dev deps the suite
  actually needs (`pytest`, `coverage`).
- Return-type annotations on 449/819 functions (55%), unevenly — the newer pure modules are
  well annotated, `app.py` mostly isn't.

`conftest.py` as a `sys.path` shim is fine and `CLAUDE.md` is right that it must not be
deleted — but a `pyproject.toml` with `[tool.pytest.ini_options] pythonpath = ["."]` would
do the same job declaratively, and gives ruff and coverage somewhere to live.

### Fix

`pyproject.toml` (pytest config + ruff), a `requirements-dev.txt`, and one CI workflow
running the suite. Plus invariant tests that encode rules `CLAUDE.md` currently states in
prose, turning conventions into checks.

**Landed as `tests/test_architecture.py`** (39 tests). Ruff is configured for
**correctness only** — `select = ["F", "E9"]`. The stylistic pycodestyle families are
deliberately off: `E701`/`E702` alone flag 63 sites, nearly all of them this codebase's
intentional compact style (`def _zoom_in(self):    self._set_zoom(...)`), and `E402`
flags the intentional function-local imports. CLAUDE.md says match the surrounding style;
a linter that argues with it would be churn.

Pyflakes found 15 real defects, all fixed: 10 unused imports, 5 dead locals. One was
load-bearing — an unused `import db` in `monster_parser` sitting directly above the raw
SQL from Finding 7's sibling, evidence someone meant to route it through `db.py` and
didn't. That query is now `db.all_mm_page_titles`, so **`monster_parser` no longer
contains SQL**.

Each guard was mutation-tested (break the rule, confirm the test fails) rather than
merely observed passing:

| Test | Guards |
|---|---|
| `test_qt_stays_out_of_the_pure_modules` | the rule that matters |
| `test_sql_stays_in_the_data_access_layer` | allowlist `{db, rules_agent}` — see below |
| `test_spec_lists_every_app_module` + stale-entry check | the frozen build |
| `test_no_import_cycles_between_app_modules` | layering direction |
| `test_every_app_module_is_importable` (parametrized) | no import-order dependencies |

`rules_agent` is **grandfathered** on the SQL rule, not endorsed: its FTS queries are
shaped by what's being retrieved, and moving them is a refactor of a 52%-covered module.
The allowlist exists so *new* violations fail.

---

## Not worth doing

Stated explicitly so it doesn't get picked up later as "obvious cleanup":

- **Splitting `char_rules.py`.** It's 2244 lines spanning ability scores, races, classes,
  progressions, proficiencies, and the whole CT mastery/styles/unarmed/talents block — so
  it *looks* like a god module. But it's 98% covered, it's the base of the import DAG, its
  section markers are clear, and its whole value is being one greppable answer to "what
  does the rulebook say". Splitting it buys tidiness and costs the single-source-of-truth
  property. Leave it.
- **Splitting `charactermancer_html.py`** (1538 lines). It was already split once
  (`_profs_html`), the seam is sensible, and a second split has no natural line.
- **Rewriting the HTML-string templating** into a template engine. It's ~4000 lines of
  f-strings, it's 92-100% covered, it has no dependency, and PyInstaller never has to
  bundle a template loader. The *escaping* problem (Finding 1) is real and fixable without
  touching the approach.
- **Chasing `app.py` to high coverage.** The target is extracting the *decisions*; the
  remaining Qt wiring (`_build_ui`'s 215 lines of widget construction) is not worth a test
  harness. Finding 2 is about the logic, not the number.

---

## Proposed order

Sequenced so each phase is independently shippable and green, cheapest-risk first. Phase 1
is the only one fixing a live defect; 2 is the guardrail that protects the rest.

| # | Phase | Touches | Why here |
|---|---|---|---|
| 1 | **One coercing `esc`, everywhere** + the fuzz regression test | Finding 1 | Fixes a reproducible crash. Mechanical, high confidence. |
| 2 | **Tooling + invariant tests** — `pyproject.toml`, ruff, dev reqs, CI, Qt-confinement and spec-sync tests | Finding 7 | Cheap, and it guards phases 3-6 while they move code. |
| 3 | **`route_destination`** — finish `nav-controller-plan.md` phase 4; update it and `CLAUDE.md` | Finding 3 | Closes a known open item; grammar ends up in one tested place. |
| 4 | **Extract search + bookmarks row formatting** | Finding 2 | The two candidates `CLAUDE.md` already names. Small, proven pattern. |
| 5 | **`theme.py`** — palette + shared CSS + `esc` + `spell_slug`; retire the duplicated literals | Findings 5, 6 | Do before v3 adds another stylesheet and another view importer. |
| 6 | **Parameterize the JSON-blob store**; coerce in `from_dict` (1c); hoist the lazy `roll20_export` import | Findings 4, 1c | Do before v3 adds a third saved-thing table. |

Phases 5 and 6 are both "do it before v3" — if v3 starts first, they get harder, not
impossible. Phases 1-4 stand alone and are worth doing regardless.

## Method notes

- Coverage: `python -m coverage run -m pytest -q && python -m coverage report --sort=miss`
  from the repo root. `.coverage` is gitignored.
- Import graph: AST walk over `*.py`, resolving only names that match a root module stem.
- Function lengths: `ast` walk, `end_lineno - lineno`.
- Palette counts: `grep -o "#[0-9a-fA-F]\{6\}"` per file, lowercased, `sort -u`, then
  counted across files.
- The crash in 1a and the DB scan in 1b are both one-liners quoted inline above — re-run
  them to confirm the fix.

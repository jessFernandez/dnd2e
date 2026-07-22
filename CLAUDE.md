# CLAUDE.md

Guidance for working in this repository.

## What this is

A desktop reference + character-builder app for **AD&D 2nd Edition**, tuned for a
specific home campaign's house rules. The rulebooks (PHB/DMG/etc.) are scraped
into a SQLite database and browsed in a Qt window; on top of that sit a step-by-step
character builder, a DM monster sheet imported from the Monstrous Manual,
quick-reference screens (DM Screen, Actions, Spells), a house-rule combat calculator,
a Roll20 export, and a local-LLM "Ask the Rules" feature.

Python + PyQt5 (with PyQtWebEngine for HTML content). Packaged for distribution
with PyInstaller (`dnd2e.spec`). Developed on Windows (PowerShell); the commands
below are shell-agnostic.

## Run / test / build

```bash
python app.py                 # run the app (needs dnd2e.db present)
python -m pytest -q           # run the test suite — from the repo root
ruff check .                  # lint (correctness rules only; see pyproject.toml)
pyinstaller dnd2e.spec        # build the distributable bundle into dist/
```

Runtime deps are in `requirements.txt`, the suite's in `requirements-dev.txt`. Almost
every module is Qt-free, but the *suite* still needs PyQt5 installed — `test_ask_lifecycle`
and `test_search_worker` drive real `QThread`s, so collection fails without it (headless:
`QT_QPA_PLATFORM=offscreen`). CI runs lint + tests on push and PR
(`.github/workflows/tests.yml`).

Run tests **from the repo root**. The modules under test live at the repo root but
the tests live in `tests/`; `conftest.py` is a `sys.path` shim that bridges that
(flat layout, no `src/` package, no `pytest.ini`). Without it, bare `pytest` can't
import `app`/`rules_agent`/… — don't remove it.

`requirements.txt` covers runtime + scraper deps. "Ask the Rules" talks to a
local **Ollama** server (`http://localhost:11434`); no API key, and the feature
degrades gracefully when Ollama isn't running.

## Architecture — the one rule that matters

**Keep logic Qt-free and out of `app.py`.** Only three modules may import PyQt:
`app.py`, `calculator.py`, `rules_agent.py`. Everything else is pure Python so it
can be unit-tested without a running app — that's why the suite is fast and broad.
When you add a feature, put the *logic* in a pure module and let the Qt layer call
into it.

### The character-builder stack (layered, each layer Qt-free except the top)

```
db.py                data-access layer — ALL SQL lives here, functions take a
                     connection as first arg (thread-safe, testable)
char_rules.py        the computable AD&D 2e rules: chargen tables, THAC0/AC/save
                     progressions, house-rule conversions. Single source of truth.
character.py         Character — the mutable in-progress build; derives everything
                     by delegating to char_rules (can't disagree with the rulebook)
charactermancer.py   Charactermancer — the step-flow controller (state machine)
character_library.py CharacterLibrary — save/load/delete builds + Roll20 payload
charactermancer_html.py   the builder's HTML view (string templating): document
                     shell, progress rail, and every step but the two below
charactermancer_profs_html.py   the Weapon/Nonweapon Proficiency steps — the CT
                     mastery ladder, groups, styles, unarmed, talents, thief skills
charactermancer_common.py   the few primitives both views need (esc, budget_bar),
                     so neither imports the other
app.py               MainWindow — Qt shell that wires the above to the UI
```

Don't confuse `charactermancer_profs_html.py` (a builder step) with
`proficiencies_html.py` (the *Codex of Worldly Craft* reference screen).

`roll20_export.py` and `calculator.py` **re-export** the house-rule conversions
from `char_rules` rather than reimplementing them, so the calculator, the builder,
and the Roll20 sheet can never disagree. Preserve that — don't duplicate a rule.

The builder makes **single-class PHB** characters at any level their race allows:
hit points, THAC0, saves, attacks/round, spell progressions, thief skills and
turning undead are all parameterized by level. That work is recorded in
[`docs/leveling-plan.md`](docs/leveling-plan.md) (complete). So is the adoption of
the *Combat & Tactics* character-building rules — weapon mastery ladder, weapon
groups, fighting styles, unarmed disciplines, special talents, but **not** its
weapon list or spells — in
[`docs/combat-tactics-chargen-plan.md`](docs/combat-tactics-chargen-plan.md)
(complete). Multi-classing and dual-classing remain unmodeled.

### The monster stack (the DM's monster sheet)

The second mini-app, layered the same way: a full AD&D 2e stat block imported from
the **Monstrous Manual** pages already in `dnd2e.db`, with the campaign's house rules
applied. Recorded in [`docs/monster-mode-plan.md`](docs/monster-mode-plan.md) (v1 + v2
complete; v3 — a dedicated Roll20 monster sheet — not started).

```
monster.py           Monster — the stat block model + the house-rule numbers it
                     derives, all through char_rules (attack bonus, ascending AC,
                     size→initiative). Kept small and stable.
monster_parser.py    MM page → Monsters. The big, fiddly layer: multi-variant
                     column grids, compact summary tables, prose attribution,
                     enrichment-table classification. Absorbs the source-format churn
                     so the model doesn't — the char_rules/character split again.
monster_tiers.py     HD / dragon-age scaling: a monster's selectable tiers and the
                     field overrides each applies
monster_abilities.py special abilities + saving throws read out of the Combat prose
monster_spells.py    spell-like abilities matched against the spells compendium
monster_library.py   save/load/delete monsters in the user DB (caller holds the row id)
monster_html.py      the sheet view, the import picker, the family/variant pickers
app.py               the `_mon_*` side effects — everything else here is Qt-free
```

`monster_parser` imports `Monster`, never the reverse; the same goes for `_tiers`,
`_abilities`, `_spells`. **Don't grow `monster.py`** — new source formats belong in the
parser, new derivations in their own pure module.

Two link grammars belong to this stack, both classified in `navigation.py` (see
**Navigation**) and performed in `app.py`:

- `dnd:///mon/…` — every sheet edit and action (`set/<field>/<value>`, `tier/<i>`,
  `pick/<page>`, `save`, `roll20`, …). `navigation.route_mon` parses it into a tagged
  `MonAct`; `app.py._mon_action` is a `match` of side effects.
- `dnd:///spell/<slug>` — a monster's spell-like ability linking into the Spell
  Compendium. `spellsscreen_html` owns both `spell_slug()` and the `id=` anchors it
  emits, and `monster_spells` imports that function, so a link can't drift from the
  anchor it points at.

Editing is guarded on both sides: `monster.house_rule_round_trips` decides whether a
field can be shown in house-rule form *and* taken back (a conditional THAC0 can't —
one number would overwrite the MM's whole string), and `monster_tiers.tiered_fields`
names the fields a selected tier is scaling, which the view renders read-only and
`_mon_set` refuses. Both live with the model, not the view.

### "Ask the Rules" (Jarvis)

`rules_agent.py` runs retrieval + a local Ollama model on a `QThread` (`AskWorker`)
that streams deltas back via Qt signals. The Qt orchestration stays in `app.py`
(`_ask_question` wires the worker's signals to the web view; `_ask_stop` /
`_ask_worker_done` manage the worker's lifecycle — see the regression tests in
`test_ask_lifecycle.py`). The *pure* decisions live in **`ask_controller.py`**:
`resolve_model` (preference vs installed models), `page_state` (ready/setup), and
`Conversation` (the running Q&A thread + in-flight question context).

### The rest of `app.py`

`MainWindow` is still large (it owns tabs, navigation/history, search, bookmarks,
zoom/find, and sessions). The direction of travel is to keep extracting Qt-light
clusters into pure controllers with tests, the way `character_library.py` was
pulled out of the `_cm_*` methods, `ask_controller.py` out of the `_ask_*` ones,
`session.py` out of session save/restore (`_save_session` / `_restore_session`
keep the Qt orchestration; `session.py` does the QSettings coercion),
`navigation.py` out of the link/pane/history logic (see **Navigation** below), and
`browse_lists.py` out of the three side lists.

`browse_lists.py` is worth knowing about: the browse tree, the search results and
the bookmarks list all render the same thing — a rulebook page as a cleaned-up title
over its book name, tinted by which book it came from. That formatting had been
written three times inside `MainWindow`. It now lives in one pure module
(`display_title`, `snippet`, `book_color`, `page_row`, `BOOK_ITEM_COLORS`), with
`_add_row` / `_add_placeholder` as the only Qt left.

Good next candidate: `_build_ui` (215 lines) — though see
[`docs/audit-2-plan.md`](docs/audit-2-plan.md) on why chasing `app.py`'s coverage
number is the wrong target; extract *decisions*, not widget construction.

### Navigation

`navigation.py` is the pure, Qt-free navigation layer, extracted from `MainWindow`
(recorded in [`docs/nav-controller-plan.md`](docs/nav-controller-plan.md), complete).
A "destination" is one canonical string that doubles as a history
entry (`"PHB/DD01671.htm"`, `"toc:PHB"`, `"proficiencies#anchor"`, `"dmscreen"`).
The module owns the grammar and the policy:

- `History` — the per-tab back/forward state machine.
- `route_destination(dest)` — classifies a destination into what should be rendered,
  returning a tagged `Dest` (`Page`, `Toc`, `Screen`, `Spells`, `MonsterFamily`, …);
  `app.py._render_destination` is then just a `match` of side effects. **New
  destinations go here and nowhere else** — `takes_full_width` derives from this
  same classification, so the two can't disagree the way they used to.
- `link_to_destination` / `takes_full_width` / `FULLWIDTH_SCREENS` — the grammar.
- `pane_action(dest, trigger)` — the single truth table for when the browse pane
  opens/closes/stays (a book page reached by a *link* opens it; a full-width
  screen closes it; anything else leaves it as the reader left it).
- `route_link(url, on_jarvis_page=…)` — classifies a `dnd://` click into a tagged
  `Route`; `app.py._on_content_navigate` is then just a `match` that performs the
  side effect. All navigation funnels through `app.py._navigate`.
- `route_mon(payload)` — the same treatment for the monster sheet's own
  `dnd:///mon/…` action grammar (decoding, index/id coercion, what a malformed
  argument means), returning a tagged `MonAct`. New link grammars go here, not in
  `app.py`.

Everything here is unit-tested without Qt (`test_navigation.py`); `app.py` keeps
only the side effects (render, show/hide pane, open tab).

### Reference screens

`screen_common.py` holds the card-grid chrome (CSS + masonry/filter script) — used by
`dmscreen_html.py` and `actionsscreen_html.py`; the other screens still carry their own
CSS, and the palette is duplicated across all of them (a known gap, see
[`docs/audit-2-plan.md`](docs/audit-2-plan.md) finding 5). `toc_html.py` / `toc.py` build
tables of contents.

**`view_common.py` is the bottom of the view layer** — the templating primitives every
HTML module needs, currently `esc`. Use it: escaping is the one thing every view does at
every interpolation, and it only stays correct with a single implementation. It coerces,
so `None` and numbers are safe to interpolate; raw `html.escape` raises on both. Don't
add a local escape helper — `tests/test_architecture.py` and `test_view_common.py` fail
if one comes back.
Navigation uses `dnd://` links intercepted in `app.py._on_content_navigate`.

The browse sidebar renders the site's **real nested tree** (Book → Chapter →
Section → page, arbitrary depth) from the `toc_tree` table, built by
`scripts/build_toc_tree.py` from the site's TOC XML (`pw_toc_6.xml`). `toc.build_tree`
reconstructs it and `app.py._load_topics` renders it, falling back to the flat
`toc_entries` layout if `toc_tree` is absent. (`toc_entries` still drives the
book-contents page and per-chapter house-rule callouts.) Background:
[`docs/toc-tree-fidelity.md`](docs/toc-tree-fidelity.md).

## Data & generated code

- **`dnd2e.db`** (~55 MB) is the scraped rulebook DB, committed to the repo and
  bundled by PyInstaller. The app also opens a separate writable **user DB**
  (bookmarks, saved characters) so user data survives app updates.
- Some modules are **generated — do not hand-edit**. They say so at the top:
  - `equipment.py` ← `scripts/build_items.py`
  - spell data ← `scripts/build_spells.py`; economics ← `scripts/build_economics.py`;
    nonweapon-proficiency book ← `scripts/build_nwp_book.py` / `scripts/build_chunks.py`;
    the `toc_tree` table ← `scripts/build_toc_tree.py` (from the site's TOC XML)
  Regenerate via the `scripts/build_*.py` script named in the file's docstring;
  run it from the repo root (each script anchors its data paths to the repo root).
- The **app icon** `assets/dnd2e.ico` / `assets/dnd2e.png` is generated by
  `scripts/build_icon.py` — embedded in the exe via `icon=` in `dnd2e.spec` and
  set as the window/taskbar icon in `app.py`. Re-run that script to change the art.
- **`scripts/`** holds all the data-tooling: the tracked `build_*.py` generators
  above, plus gitignored one-off provenance scripts (`scraper.py`,
  `fetch_economics.py`, `cleanup_spells.py`, `fix_chapter9.py`,
  `setup_house_rules.py`) that originally built `dnd2e.db` and the economics CSVs.
  None are imported by the app; end users don't need them.

## Conventions

- Match the surrounding style: module-level docstrings explain the *why* and the
  layer boundary — keep that up when adding modules.
- Every new pure module gets a `tests/test_*.py`. Tests use a throwaway temp DB
  (`tmp_path`) for user-DB logic and skip gracefully when `dnd2e.db` is absent
  (guard with a `needs_db` skipif, as in `test_db.py`).
- **Testing `MainWindow`'s Qt wiring:** don't spin up a real window. Bind the
  unbound method to a light `SimpleNamespace` stand-in and assert its behaviour —
  see `test_charactermancer.py` (`_cm_*` routing), `test_ask_lifecycle.py`
  (worker cleanup), and `test_search_worker.py` (driving a `QThread`'s `run()`
  synchronously). This is how the Qt layer stays covered without a display.
- **Adding a new top-level app module?** Add it to `dnd2e.spec`'s `hiddenimports`
  (the spec lists every app module explicitly, belt-and-suspenders over
  PyInstaller's auto-detection) so the frozen build can't miss it.
- **The layering rules above are enforced, not just documented.**
  `tests/test_architecture.py` checks that PyQt stays in the three Qt modules, that SQL
  stays in `db.py` (`rules_agent` is grandfathered), that `dnd2e.spec` lists every module
  and no stale ones, that the import graph stays acyclic, and that every module imports
  standalone. If one fails, the rule it names is the thing to fix — not the test.
- `*.log`, `build/`, `dist/`, `__pycache__/` are gitignored build/run artifacts.

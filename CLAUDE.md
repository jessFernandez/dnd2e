# CLAUDE.md

Guidance for working in this repository.

## What this is

A desktop reference + character-builder app for **AD&D 2nd Edition**, tuned for a
specific home campaign's house rules. The rulebooks (PHB/DMG/etc.) are scraped
into a SQLite database and browsed in a Qt window; on top of that sit a step-by-step
character builder, quick-reference screens (DM Screen, Actions, Spells), a
house-rule combat calculator, a Roll20 export, and a local-LLM "Ask the Rules"
feature.

Python + PyQt5 (with PyQtWebEngine for HTML content). Packaged for distribution
with PyInstaller (`dnd2e.spec`). Developed on Windows (PowerShell); the commands
below are shell-agnostic.

## Run / test / build

```bash
python app.py                 # run the app (needs dnd2e.db present)
python -m pytest -q           # run the test suite (fast, Qt-free) — from the repo root
pyinstaller dnd2e.spec        # build the distributable bundle into dist/
```

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
charactermancer_html.py   the builder's HTML view (string templating)
app.py               MainWindow — Qt shell that wires the above to the UI
```

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
pulled out of the `_cm_*` methods and `ask_controller.py` out of the `_ask_*`
ones. Good next candidate: session save/restore (`_save_session` /
`_restore_session`).

### Reference screens

`screen_common.py` holds the shared card-grid chrome (CSS + masonry/filter script);
`dmscreen_html.py`, `actionsscreen_html.py`, `spellsscreen_html.py`, `splash_html.py`
each just supply their cards. `toc_html.py` / `toc.py` build tables of contents.
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
- `*.log`, `build/`, `dist/`, `__pycache__/` are gitignored build/run artifacts.

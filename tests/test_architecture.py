"""The layering rules CLAUDE.md states in prose, as checks.

Each of these held when written — they exist to keep holding. A rule that only
lives in a document gets broken by the next person who hasn't read it, and the
first audit found two that had already drifted (docs/audit-2-plan.md findings 3
and 5). These are cheap; the point is that breaking one is a test failure rather
than a code review someone has to notice.
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_MODULES = sorted(p for p in ROOT.glob("*.py") if p.stem != "conftest")


def _imports(path: pathlib.Path) -> set:
    """Top-level module names imported by a file, including function-local ones."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


# ── the rule that matters ────────────────────────────────────────────────────

#: CLAUDE.md: "Only three modules may import PyQt." Everything else stays pure so
#: it can be unit-tested without a running app — that's why the suite is fast.
QT_MODULES = {"app", "calculator", "rules_agent"}


def test_qt_stays_out_of_the_pure_modules():
    offenders = {p.stem for p in APP_MODULES
                 if p.stem not in QT_MODULES and "PyQt5" in _imports(p)}
    assert offenders == set(), (
        f"PyQt5 imported outside {sorted(QT_MODULES)}: {sorted(offenders)}. "
        "Put the logic in a pure module and let the Qt layer call into it."
    )


# ── data access ──────────────────────────────────────────────────────────────

#: CLAUDE.md: "db.py — data-access layer — ALL SQL lives here."
#:
#: rules_agent is the one remaining exception: its retrieval builds FTS queries
#: whose shape depends on what's being retrieved, and moving them wholesale is a
#: refactor of a module the suite barely covers. It is grandfathered rather than
#: endorsed — the point of the allowlist is that *new* violations fail.
SQL_ALLOWED = {"db", "rules_agent"}

_SQL = re.compile(r"\b(SELECT|INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE)\b")


def test_sql_stays_in_the_data_access_layer():
    offenders = []
    for path in APP_MODULES:
        if path.stem in SQL_ALLOWED:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and _SQL.search(node.value):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        f"SQL outside db.py: {offenders}. Add a function to db.py and call it, "
        "so the schema keeps one owner."
    )


# ── the frozen build ─────────────────────────────────────────────────────────

def test_spec_lists_every_app_module():
    """dnd2e.spec enumerates every module in hiddenimports, belt-and-suspenders
    over PyInstaller's auto-detection. A new module that isn't listed imports
    fine in development and is missing from the bundle."""
    spec = (ROOT / "dnd2e.spec").read_text(encoding="utf-8")
    block = re.search(r"hiddenimports\s*=\s*\[(.*?)\]", spec, re.S)
    assert block, "could not find hiddenimports in dnd2e.spec"
    listed = set(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", block.group(1)))

    # app.py is the entry script, not a hidden import.
    expected = {p.stem for p in APP_MODULES} - {"app"}
    missing = sorted(expected - listed)
    assert missing == [], (
        f"modules missing from dnd2e.spec hiddenimports: {missing}. "
        "The spec lists every app module explicitly (see CLAUDE.md)."
    )


def test_spec_does_not_list_modules_that_no_longer_exist():
    spec = (ROOT / "dnd2e.spec").read_text(encoding="utf-8")
    block = re.search(r"hiddenimports\s*=\s*\[(.*?)\]", spec, re.S)
    listed = set(re.findall(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]", block.group(1)))
    stale = sorted(listed - {p.stem for p in APP_MODULES})
    assert stale == [], f"dnd2e.spec lists modules that don't exist: {stale}"


# ── the destination grammar has one home ─────────────────────────────────────

def test_simple_screens_matches_the_registry_in_app():
    """navigation.SIMPLE_SCREENS names the destinations route_destination tags as
    Screen(...), and app.py's `self._screens` maps those names to their generator.
    If they drift, _render_screen raises KeyError on a destination that routed fine.

    Checked statically (the registry is built in MainWindow.__init__, which needs
    Qt) by reading the dict literal's keys out of the source.
    """
    import navigation

    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    keys = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            target = node.targets[0]
            if isinstance(target, ast.Attribute) and target.attr == "_screens":
                keys = {k.value for k in node.value.keys
                        if isinstance(k, ast.Constant)}
                break
    assert keys is not None, "could not find `self._screens = {...}` in app.py"
    assert keys == set(navigation.SIMPLE_SCREENS), (
        f"app.py _screens {sorted(keys)} != navigation.SIMPLE_SCREENS "
        f"{sorted(navigation.SIMPLE_SCREENS)}"
    )


# ── views depend on logic, never the reverse ─────────────────────────────────

#: The view layer: HTML string builders plus the two shared-chrome modules.
def _is_view(stem: str) -> bool:
    return stem.endswith("_html") or stem in {"screen_common", "view_common"}


def test_logic_modules_do_not_import_view_modules():
    """A view may import the model it renders; the model must not import the view.

    `monster_spells` used to import `spell_slug` from `spellsscreen_html` — right
    instinct (one owner for the slug, so a link can't drift from the id it targets),
    wrong direction: the monster stack couldn't be imported without dragging in the
    spell screen. The slug now lives in `slugs.py`, which both import.
    See docs/audit-2-plan.md finding 6.

    app.py is exempt — wiring the views to the UI is its whole job.
    """
    offenders = {}
    for path in APP_MODULES:
        if path.stem == "app" or _is_view(path.stem):
            continue
        views = {m for m in _imports(path) if _is_view(m)}
        if views:
            offenders[path.stem] = sorted(views)
    assert offenders == {}, (
        f"logic modules importing view modules: {offenders}. "
        "Move the shared piece into a pure module both can import (see slugs.py)."
    )


# ── layering direction ───────────────────────────────────────────────────────

def test_no_import_cycles_between_app_modules():
    """The internal import graph is a DAG with char_rules at the base. A cycle is
    the usual symptom of logic drifting into the wrong layer."""
    stems = {p.stem for p in APP_MODULES}
    graph = {p.stem: (_imports(p) & stems) - {p.stem} for p in APP_MODULES}

    visiting, done = set(), set()
    cycles = []

    def walk(node, trail):
        if node in visiting:
            cycles.append(" -> ".join(trail[trail.index(node):] + [node]))
            return
        if node in done:
            return
        visiting.add(node)
        for dep in sorted(graph.get(node, ())):
            walk(dep, trail + [dep])
        visiting.discard(node)
        done.add(node)

    for stem in sorted(graph):
        walk(stem, [stem])
    assert cycles == [], f"import cycles: {cycles}"


@pytest.mark.parametrize("module", sorted(p.stem for p in APP_MODULES))
def test_every_app_module_is_importable(module):
    """Catches a module that only works because something else imported it first."""
    if module in QT_MODULES:
        pytest.importorskip("PyQt5")
    __import__(module)

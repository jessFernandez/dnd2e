"""Tests for theme.py and slugs.py — the shared palette and the anchor ids.

theme.BOOKS replaced four separate per-book colour tables plus a second copy of the
book *names*, which had already drifted (the splash screen said "Skills & Powers"
while the DB and every other surface said "Skills and Powers"). These tests pin the
things that drift: that the names match the rulebook DB, and that every book has
every colour role. See docs/audit-2-plan.md findings 5 and 6.
"""
import os
import re
import sqlite3

import pytest

import slugs
import theme

RULES_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

HEX = re.compile(r"^#[0-9a-f]{6}$")


# ── the books ────────────────────────────────────────────────────────────────

def test_every_book_has_every_colour_role():
    for code, b in theme.BOOKS.items():
        assert b.code == code, f"{code} keyed under the wrong code"
        assert b.name, code
        for role in ("tree", "accent", "item"):
            assert HEX.match(getattr(b, role)), f"{code}.{role} = {getattr(b, role)!r}"


def test_book_order_covers_every_book_exactly_once():
    assert set(theme.BOOK_ORDER) == set(theme.BOOKS)
    assert len(theme.BOOK_ORDER) == len(theme.BOOKS)


@needs_db
def test_book_names_match_the_rulebook_db():
    """The DB's `pages.book_name` is the source of truth — the sidebar, the search
    results and the bookmarks all read it. A book named differently in theme.BOOKS
    would show one name on the splash screen and another everywhere else, which is
    exactly the drift this table was created to end.
    """
    conn = sqlite3.connect(RULES_DB)
    db_names = dict(conn.execute("SELECT DISTINCT book_code, book_name FROM pages"))
    mismatched = {code: (b.name, db_names[code])
                  for code, b in theme.BOOKS.items()
                  if code in db_names and b.name != db_names[code]}
    assert mismatched == {}, f"theme.BOOKS name != DB book_name for: {mismatched}"


@needs_db
def test_theme_covers_every_book_in_the_db():
    conn = sqlite3.connect(RULES_DB)
    codes = {r[0] for r in conn.execute("SELECT DISTINCT book_code FROM pages")}
    assert codes - set(theme.BOOKS) == set(), "a book in the DB has no theme.Book"


def test_colour_roles_are_distinct_per_book():
    """The three roles are different jobs — a vivid sidebar colour used as a row tint
    would be unreadable. Catches a copy-paste when a book is added."""
    for code, b in theme.BOOKS.items():
        assert len({b.tree, b.accent, b.item}) == 3, f"{code} reuses a colour across roles"


def test_lookups_fall_back_for_unknown_codes():
    for fn, default in [(theme.tree_color, theme.DEFAULT_TREE_COLOR),
                        (theme.accent_color, theme.DEFAULT_ACCENT_COLOR),
                        (theme.item_color, theme.DEFAULT_ITEM_COLOR)]:
        assert fn("NOPE") == default
        assert fn("") == default
        assert fn(None) == default
    assert theme.book("NOPE") is None
    assert theme.book_name("NOPE", "fallback") == "fallback"
    assert theme.book_name("PHB") == "Player's Handbook"


def test_lookups_resolve_known_codes():
    assert theme.tree_color("PHB") == theme.BOOKS["PHB"].tree
    assert theme.accent_color("MM") == theme.BOOKS["MM"].accent
    assert theme.item_color("CT") == theme.BOOKS["CT"].item


# ── the palette ──────────────────────────────────────────────────────────────

def test_palette_values_are_well_formed():
    names = [n for n in dir(theme)
             if n.isupper() and isinstance(getattr(theme, n), str) and n != "BOOK_ORDER"]
    assert names, "no palette constants found"
    for n in names:
        assert HEX.match(getattr(theme, n)), f"theme.{n} = {getattr(theme, n)!r}"


def test_the_accent_has_exactly_one_definition():
    """ACCENT was hardcoded in eight files and *named* in three of them. The three
    named ones now point here; if one forks again this fails."""
    import charactermancer_common
    import monster_html
    import proficiencies_html
    assert charactermancer_common.ACCENT == theme.ACCENT
    assert monster_html.ACCENT == theme.ACCENT
    assert proficiencies_html.ACCENT == theme.ACCENT


# ── slugs ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("Cone of Cold",             "cone-of-cold"),
    ("Otto's Irresistible Dance", "otto-s-irresistible-dance"),
    ("Bowyer/Fletcher",          "bowyer-fletcher"),
    ("Reading/Writing",          "reading-writing"),
    ("  Weird---Name!!  ",       "weird-name"),
    ("",                         ""),
    (None,                       ""),          # both callers feed parsed text
])
def test_slug_normalises(name, expected):
    assert slugs.slug(name) == expected


def test_anchors_carry_their_namespace_prefix():
    assert slugs.spell_anchor("Cone of Cold") == "spell-cone-of-cold"
    assert slugs.prof_anchor("Bowyer/Fletcher") == "prof-bowyer-fletcher"
    assert slugs.spell_anchor("x").startswith(slugs.SPELL_PREFIX)
    assert slugs.prof_anchor("x").startswith(slugs.PROF_PREFIX)


def test_a_spell_link_lands_on_the_anchor_the_compendium_emits():
    """The whole point of one owner: navigation turns dnd:///spell/<slug> into a
    fragment, and spellsscreen_html emits the id. They must agree."""
    import navigation
    name = "Cone of Cold"
    dest = navigation.link_to_destination("spell/" + slugs.slug(name))
    assert dest == "spells#" + slugs.spell_anchor(name)
    # and the destination classifies to the compendium at that fragment
    assert navigation.route_destination(dest) == navigation.Spells(slugs.spell_anchor(name))


# ── the palette as CSS custom properties ─────────────────────────────────────
#
# theme.py was a *reference* the view layer was asked to copy from by hand, which is
# why 247 hex literals accumulated and ACCENT was typed out 37 times. The obstacle
# was never QtWebEngine -- it is Chromium and has supported custom properties for
# years -- but that most view CSS lives in plain (non-f) triple-quoted strings,
# where interpolating `{TEXT}` renders the brace literally. `var(--text)` passes
# through such a string untouched, which is what made the migration possible.

def test_css_vars_declares_every_named_colour():
    block = theme.css_vars()
    assert block.startswith(":root {")
    for name, value in theme.CSS_VARS.items():
        assert f"--{name}: {value};" in block


def test_css_vars_values_are_the_constants_not_copies():
    """Each entry must *be* the module constant, so retheming one place moves the
    screens too. A hand-typed duplicate here would defeat the whole exercise."""
    named = {v for k, v in vars(theme).items()
             if k.isupper() and isinstance(v, str) and v.startswith("#")}
    for name, value in theme.CSS_VARS.items():
        assert value in named, f"--{name} is not one of theme.py's own constants"


def test_every_var_a_view_uses_is_declared_somewhere():
    """A `var(--typo)` renders as *nothing* — no error, no warning, just an element
    with that property unset. Every custom property a view reads must therefore be
    declared: either by theme.CSS_VARS (the shared palette) or by the module itself.

    Screen-local properties are legitimate and common — the splash sets `--c` per
    tool tile and `--blue`/`--red` on the body, the spells screen sets `--sc` per
    card — so the rule is "declared somewhere", not "in the palette". Checking that
    a module assigns what it reads keeps this honest without an exception list that
    would quietly absorb a genuine typo.
    """
    import pathlib
    import re

    root = pathlib.Path(theme.__file__).parent
    palette = set(theme.CSS_VARS)
    undeclared = {}
    for path in list(root.glob("*_html.py")) + [root / "screen_common.py"]:
        source = path.read_text(encoding="utf-8")
        local = set(re.findall(r"--([a-z0-9-]+)\s*:", source))     # set by this module
        for name in set(re.findall(r"var\(\s*--([a-z0-9-]+)\s*\)", source)):
            if name not in palette and name not in local:
                undeclared.setdefault(path.name, set()).add(name)
    assert undeclared == {}, (
        f"var() names nothing declares: {undeclared} — these render as unset")


def test_a_screen_that_uses_vars_also_emits_the_root_block():
    """Using var() without the declarations is the one way this migration can fail
    silently: the page renders with every themed colour missing."""
    import charactermancer_html
    import monster_html
    import spellsscreen_html
    import askscreen_html
    import actionsscreen_html
    import dmscreen_html
    import proficiencies_html
    from charactermancer import Charactermancer

    pages = {
        "charactermancer": charactermancer_html.generate(Charactermancer(), []),
        "monster": monster_html.generate(__import__("monster").Monster(name="X")),
        "spells": spellsscreen_html.generate([]),
        "ask": askscreen_html.generate("ready", model="m", models=["m"]),
        "actions": actionsscreen_html.generate(),
        "dmscreen": dmscreen_html.generate(),
        "proficiencies": proficiencies_html.generate(),
    }
    for name, html in pages.items():
        if "var(--" in html:
            assert ":root {" in html, f"{name} uses var() but declares no :root block"

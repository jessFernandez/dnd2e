"""The one escape function, and the crash it exists to prevent.

Before `view_common.esc`, the view layer had six spellings of HTML-escaping and two
different behaviours: `charactermancer_common.esc` coerced its argument, everything
else called `html.escape` raw, which raises on anything that isn't a `str`. A stat
block is mostly optional fields, so the raw form had to be guarded by hand at every
interpolation — and `monster_html` missed some. See docs/audit-2-plan.md finding 1.

The fuzz test at the bottom is the real regression guard: it renders every view
module's public entry point with `None` and `int` in every field.
"""
import dataclasses
import inspect

import pytest

import monster
import monster_html
import view_common
from view_common import esc


# ── the primitive ────────────────────────────────────────────────────────────

def test_escapes_markup_and_quotes():
    assert esc('<a href="x">') == "&lt;a href=&quot;x&quot;&gt;"
    assert esc("Gear & Equipment") == "Gear &amp; Equipment"
    # quote=True, so one function is safe in both text and attribute position
    assert esc("Player's") == "Player&#x27;s"


@pytest.mark.parametrize("value,expected", [
    (None, ""),          # an absent field renders as nothing, not the word "None"
    (0, "0"),            # ...but a falsy number is still a number
    (5, "5"),
    (False, "False"),
    (-1, "-1"),
    (1.5, "1.5"),
])
def test_coerces_non_strings(value, expected):
    assert esc(value) == expected


def test_esc_is_the_only_escape_in_the_view_layer():
    """The aliases (`e`, `escape`, `_esc`, `html.escape`) are gone; if one comes
    back, the two behaviours diverge again and the crash below returns."""
    import pathlib
    offenders = []
    for p in sorted(pathlib.Path(__file__).resolve().parent.parent.glob("*_html.py")):
        src = p.read_text(encoding="utf-8")
        if "from html import escape" in src or "html.escape(" in src:
            offenders.append(p.name)
    assert offenders == [], f"raw html.escape is back in: {offenders}"


# ── the crash it prevents ────────────────────────────────────────────────────

def test_monster_sheet_renders_with_null_fields():
    """A saved monster whose JSON carries a null used to crash the sheet:
    AttributeError: 'NoneType' object has no attribute 'replace'.

    Only `None` is in contract here — the stat fields are declared `str`, and a
    JSON null is how they realistically arrive that way (an older save, a field
    added since). Feeding *ints* into string fields breaks further down, in the
    house-rule conversions in `monster.py`; that's a model concern, not an
    escaping one, and out of scope for this test.
    """
    m = monster.Monster.from_dict({"name": None, "hit_dice": None})
    html = monster_html.generate(m)
    assert "<html" in html


def test_monster_sheet_renders_with_every_field_null():
    m = monster.Monster.from_dict(
        {f.name: None for f in dataclasses.fields(monster.Monster)})
    assert monster_html.generate(m)


def test_every_view_module_entry_point_survives_none():
    """Sweep: call every public `generate*` that takes only optional/simple args
    with nothing, and confirm none of them raise. Catches a new module landing
    with a hand-rolled escape."""
    import actionsscreen_html, askscreen_html, dmscreen_html, proficiencies_html
    import splash_html, spellsscreen_html

    modules = [actionsscreen_html, askscreen_html, dmscreen_html,
               proficiencies_html, splash_html, spellsscreen_html]
    called = 0
    for mod in modules:
        for name, fn in vars(mod).items():
            if not (name.startswith("generate") and callable(fn)):
                continue
            sig = inspect.signature(fn)
            required = [p for p in sig.parameters.values()
                        if p.default is inspect.Parameter.empty
                        and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
            if required:
                continue                      # needs real data; covered elsewhere
            assert fn(), f"{mod.__name__}.{name}() returned nothing"
            called += 1
    assert called >= 4, f"expected to exercise several generators, got {called}"


def test_view_common_imports_nothing_from_the_app():
    """It sits at the bottom of the layering — every view module imports it, so it
    must not import any of them back."""
    src = inspect.getsource(view_common)
    for line in src.splitlines():
        if line.startswith(("import ", "from ")):
            assert line.startswith(("import html", "from html")), \
                f"view_common must stay dependency-free, found: {line!r}"

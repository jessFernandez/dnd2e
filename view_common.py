"""view_common.py — the primitives every HTML view module needs.

The views are pure string templating (see `charactermancer_html` for the layer
rules), which means escaping is applied by hand at each interpolation. That only
works if *one* escape function is in play: before this module, seven view modules
imported `html.escape` under four different spellings (`e`, `esc`, `escape`,
`html.escape`) while `charactermancer_common` defined a fifth that coerced its
argument first. The two behaviours disagree on non-strings —

    html.escape(None)  ->  AttributeError: 'NoneType' object has no attribute 'replace'

— and a stat block full of optional fields hits that constantly, so the raw form
had to be guarded by hand at every call site and wasn't. `esc` below is the
coercing one, and it's the only one; see docs/audit-2-plan.md finding 1.

Qt-free, and it imports nothing from the app — every view module may import this,
so it has to sit at the bottom of the layering. Not to be confused with
`screen_common.py`, which is the reference screens' shared *chrome* (CSS + the
masonry/filter script) rather than a templating primitive.
"""
import html


def esc(value) -> str:
    """HTML-escape a value for interpolation into a template, quotes included.

    Coerces first, so `None`, ints and dataclass fields that are only sometimes
    strings are safe to interpolate — `None` renders as the empty string rather
    than the word "None", since every caller means "this field is absent".
    """
    return "" if value is None else html.escape(str(value), quote=True)

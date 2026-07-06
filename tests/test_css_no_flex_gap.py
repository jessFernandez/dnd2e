"""Guard against the QtWebEngine flexbox-`gap` bug.

The app's bundled Chromium (< v84) silently IGNORES the CSS `gap` property on
flex containers, so any `display:flex`/`inline-flex` rule that relies on `gap`
for spacing renders with its children jammed together in the actual app (grid
`gap` works fine, and is allowed). We repeatedly hit and fixed this by hand; this
test fails the build if a flex rule with a non-zero `gap` sneaks back into any
`*_html.py` CSS, so the regression can't recur silently.

The scan splits each module's CSS into brace-delimited rule bodies and flags any
body that declares a flex display AND a non-zero gap. It handles both plain CSS
and the templates that live inside f-strings — where `{{`/`}}` are literal CSS
braces and bare `{name}` are Python interpolations that must not be mistaken for
rule boundaries.
"""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_FLEX = re.compile(r"display\s*:\s*(inline-)?flex\b")        # grid gap is fine in Qt
_GAP = re.compile(r"\bgap\s*:[^;]*[1-9][^;]*;")               # any non-zero gap
_BODY = re.compile(r"\{([^{}]*)\}", re.DOTALL)               # a CSS rule body


def _css_bodies(source: str):
    """Yield CSS rule bodies from module source, tolerating f-string braces.

    Double-brace templates write CSS rules as `{{ ... }}` and interpolate values
    as bare `{name}`; plain modules write rules as `{ ... }`. So only strip bare
    interpolations when the file actually uses `{{` — otherwise `{ ... }` *is* the
    rule body and must be kept.
    """
    s = source
    if "{{" in s:
        s = s.replace("{{", "\x01").replace("}}", "\x02")
        s = re.sub(r"\{[^{}]*\}", "", s)      # f-string interpolations -> gone
        s = s.replace("\x01", "{").replace("\x02", "}")
    for m in _BODY.finditer(s):
        yield m.group(1)


def _offenders(source: str):
    return [" ".join(b.split())[:120]
            for b in _css_bodies(source)
            if _FLEX.search(b) and _GAP.search(b)]


def test_no_flex_gap_in_html_modules():
    problems = {}
    for path in glob.glob(os.path.join(ROOT, "*_html.py")):
        with open(path, encoding="utf-8") as f:
            offenders = _offenders(f.read())
        if offenders:
            problems[os.path.basename(path)] = offenders
    assert not problems, (
        "flex `gap` breaks under QtWebEngine — convert to child margins:\n"
        + "\n".join(f"  {mod}: {rule}" for mod, rules in problems.items() for rule in rules)
    )

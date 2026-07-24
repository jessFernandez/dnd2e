"""splash_html.py — Welcome / landing screen for the D&D 2E app.

The home screen is styled around the campaign's AD&D 2nd Edition logo. The matted
logo art and the Death Star display font are embedded as inline `data:` URIs (from
the generated `splash_assets` module) so the screen ships offline — the app makes
no network requests. See `scripts/build_splash_assets.py` for how those are baked.

The tool tiles and the book strip reuse the existing `dnd://` link grammar
(`screen/…` for a built-in screen, `toc/…` for a book's contents — see
`navigation`). Book codes and names come from `theme.BOOKS`, so this screen and the
sidebar can't disagree about a book's name.

Palette is pulled from the logo: royal blue is the core, white the glow and type,
red the accent. Colour also carries meaning — the two build tools (Character
Builder, Monsters) are red, the reference tools blue.
"""
import theme
from view_common import esc
from splash_assets import FONT_DATA_URI, LOGO_DATA_URI

#: The six rail tools, in grid order: the two red "build" tools fill the top row,
#: the blue reference tools sit below. Each href is a `screen/…` link the same as
#: the rail buttons trigger (navigation.link_to_destination strips the prefix).
TOOLS = [
    ("screen/charactermancer", "Character Builder", "#ff4a4f"),
    ("screen/monster",         "Monsters",          "#ff4a4f"),
    ("screen/dmscreen",        "DM Screen",         "#3a86ff"),
    ("screen/actions",         "Actions",           "#3a86ff"),
    ("screen/spells",          "Spells",            "#3a86ff"),
    ("screen/ask",             "Jarvis",            "#3a86ff"),
]

#: Blue spectrum for the Browse Books ticks — one per rulebook, in theme.BOOK_ORDER.
#: The unified palette means the strip is blue rather than each book's own colour;
#: the book's name rides along as the link tooltip, and the true per-book colours
#: still identify it everywhere else in the UI.
_BOOK_TICKS = ["#123f8a", "#1b56a8", "#2465c4", "#2f6fd6", "#3f83e6",
               "#4f92ee", "#62a1f2", "#79b3f6", "#93c4f9", "#aed3fb"]

_STYLES = """
*, *::before, *::after { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  color: #d6dbec;
  display: flex; align-items: center; justify-content: center;
  padding: 28px;
  --blue: #2f6fd6; --red: #e0393f;
  background-color: #080a0f;
  background-image:
    radial-gradient(ellipse 58% 44% at 50% 22%, rgba(47,111,214,.20), transparent 64%),
    radial-gradient(ellipse 54% 40% at 50% 98%, rgba(224,57,63,.09), transparent 72%),
    radial-gradient(1.5px 1.5px at 12% 16%, rgba(255,255,255,.42), transparent 60%),
    radial-gradient(1.5px 1.5px at 84% 22%, rgba(255,255,255,.34), transparent 60%),
    radial-gradient(1.5px 1.5px at 66% 12%, rgba(255,255,255,.30), transparent 60%),
    radial-gradient(1.5px 1.5px at 30% 9%,  rgba(255,255,255,.24), transparent 60%),
    radial-gradient(1.5px 1.5px at 91% 66%, rgba(255,255,255,.22), transparent 60%),
    radial-gradient(1.5px 1.5px at 8%  72%, rgba(255,255,255,.20), transparent 60%),
    radial-gradient(1.5px 1.5px at 50% 84%, rgba(255,255,255,.18), transparent 60%),
    radial-gradient(ellipse 132% 104% at 50% 50%, transparent 52%, rgba(0,0,0,.72) 100%);
}
a { text-decoration: none; color: inherit; }
a:focus-visible { outline: 2px solid #eaf3ff; outline-offset: 3px; border-radius: 4px; }

.frame {
  position: relative; width: 100%; max-width: 1000px;
  padding: 36px 48px 30px;
  border: 2px solid var(--blue);
  box-shadow: inset 0 0 0 1px #060810, inset 0 0 0 3px rgba(120,175,255,.42),
              inset 0 0 60px rgba(47,111,214,.12);
  display: flex; flex-direction: column;
}
.brk { position: absolute; width: 20px; height: 20px; border: 2px solid var(--red);
       filter: drop-shadow(0 0 4px rgba(224,57,63,.6)); }
.brk.tl { top: -2px; left: -2px;  border-width: 2px 0 0 2px; }
.brk.tr { top: -2px; right: -2px; border-width: 2px 2px 0 0; }
.brk.bl { bottom: -2px; left: -2px;  border-width: 0 0 2px 2px; }
.brk.br { bottom: -2px; right: -2px; border-width: 0 2px 2px 0; }

.hero { text-align: center; padding: 12px 0 8px; }
.logo-wrap { position: relative; width: min(560px, 84%); margin: 0 auto; }
.logo-wrap::before {
  content: ""; position: absolute; inset: -18% -8%;
  background: radial-gradient(ellipse at center, rgba(47,111,214,.28), transparent 70%);
  filter: blur(10px);
}
.logo-wrap img { position: relative; display: block; width: 100%; height: auto;
  filter: drop-shadow(0 6px 16px rgba(0,0,0,.6)); }

.subtitle {
  font-family: "Death Star", "Arial Black", Impact, sans-serif;
  font-size: 15px; letter-spacing: .24em; margin: 22px 0 0; color: #eaf3ff;
  text-shadow: 0 0 3px rgba(120,175,255,.95), 0 0 11px rgba(58,134,255,.85),
               0 0 24px rgba(47,111,214,.55);
}
.rule { display: flex; align-items: center; justify-content: center;
  margin: 15px auto 2px; width: min(440px, 78%); }
.rule > * + * { margin-left: 14px; }  /* QtWebEngine drops flex gap */
.rule .ln { flex: 1; height: 2px; background: linear-gradient(90deg, transparent, var(--blue)); }
.rule .ln.r { background: linear-gradient(270deg, transparent, var(--blue)); }
.rule .gem { color: var(--red); font-size: 10px; text-shadow: 0 0 8px rgba(224,57,63,.75); }

.tools { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 24px 0 0; }
.neon {
  display: flex; align-items: center; justify-content: center; padding: 16px 18px;
  border: 2px solid var(--c); border-radius: 9px; background: rgba(4,7,14,.42);
  box-shadow: inset 0 0 12px -6px var(--c), 0 0 12px -3px var(--c);
  transition: box-shadow .15s, background .15s, transform .12s;
}
.neon .nm {
  font-family: "Death Star", "Arial Black", Impact, sans-serif;
  font-size: 22px; letter-spacing: .03em; color: #fff; text-align: center;
  text-shadow: 0 0 9px var(--c), 0 0 2px var(--c);
}
.neon:hover { transform: translateY(-2px); background: rgba(4,7,14,.2);
  box-shadow: inset 0 0 18px -6px var(--c), 0 0 26px -4px var(--c), 0 0 46px -12px var(--c); }

.browse {
  margin-top: 12px; padding: 12px 18px 13px; border: 2px solid var(--blue);
  border-radius: 9px; text-align: center; background: rgba(4,7,14,.42);
  box-shadow: inset 0 0 12px -6px var(--blue), 0 0 12px -3px var(--blue);
}
.browse .nm { font-family: "Death Star", "Arial Black", Impact, sans-serif;
  font-size: 18px; letter-spacing: .03em; color: #fff; text-shadow: 0 0 9px var(--blue); }
.browse .ticks { display: flex; justify-content: center; margin-top: 9px; flex-wrap: wrap; }
.browse .ticks a { display: block; width: 42px; height: 8px; margin: 3px; border-radius: 2px;
  background: var(--c); box-shadow: 0 0 6px -1px var(--c); transition: transform .12s, filter .12s; }  /* margin, not gap: QtWebEngine drops flex gap */
.browse .ticks a:hover { transform: scaleY(1.6); filter: brightness(1.25); }

.colophon { text-align: center; padding-top: 18px; font-family: Georgia, serif;
  font-style: italic; font-size: 12px; color: #5c6480; }

@media (max-width: 720px) { .tools { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""


def generate() -> str:
    tools = ""
    for path, label, color in TOOLS:
        tools += (
            f'<a class="neon" style="--c:{color}" href="dnd:///{path}">'
            f'<span class="nm">{esc(label)}</span></a>'
        )

    ticks = ""
    for code, color in zip(theme.BOOK_ORDER, _BOOK_TICKS):
        b = theme.BOOKS[code]
        ticks += (
            f'<a href="dnd:///toc/{b.code}" title="{esc(b.name)}" style="--c:{color}"></a>'
        )

    # CSS built by concatenation, not an f-string, so the stylesheet's own braces
    # need no escaping; only the font's data: URI is spliced in.
    css = ('@font-face { font-family: "Death Star"; src: url("' + FONT_DATA_URI
           + '") format("opentype"); font-weight: 400; font-style: normal; }\n' + _STYLES)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>D&amp;D 2nd Edition — Rules Reference</title>
<style>{css}</style>
</head>
<body>
  <div class="frame">
    <span class="brk tl"></span><span class="brk tr"></span><span class="brk bl"></span><span class="brk br"></span>

    <div class="hero">
      <div class="logo-wrap"><img src="{LOGO_DATA_URI}" alt="Advanced Dungeons &amp; Dragons 2nd Edition"></div>
      <p class="subtitle">Rules Reference &amp; Campaign Tools</p>
      <div class="rule"><span class="ln"></span><span class="gem">◆</span><span class="ln r"></span></div>
    </div>

    <div class="tools">{tools}</div>

    <div class="browse">
      <span class="nm">Browse Books</span>
      <span class="ticks">{ticks}</span>
    </div>

    <div class="colophon">Offline · house rules applied</div>
  </div>
</body>
</html>"""

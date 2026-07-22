"""proficiencies_html.py — the browsable "book" view of the nonweapon-proficiency
sourcebook (char_rules.NONWEAPON_PROFICIENCIES / nonweapon_book.py).

Like spellsscreen_html.py, `generate()` returns one self-contained HTML document
that app.py writes to a temp file and loads as a file:// URL (so the A–Z index and
the sidebar's per-skill links jump to `#prof-<slug>` anchors natively). `slug()`
is shared with app.py so the sidebar's anchors match the page's ids.
"""
import re

import char_rules as cr
from view_common import esc

ACCENT = "#c9a84c"


def slug(name: str) -> str:
    """Anchor id for a proficiency name, e.g. 'Bowyer/Fletcher' -> 'bowyer-fletcher'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _slots_label(n: int) -> str:
    if n == 0:
        return "Free"
    return f"{n} slot" + ("s" if n != 1 else "")


def _classes_label(classes) -> str:
    return " · ".join(classes) if classes else "All classes"


def _render_desc(desc: str) -> str:
    """Render a proficiency's prose, turning '* ' lines into bullet lists."""
    if not desc:
        return ""
    out = []
    for block in desc.split("\n\n"):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        bullets = [ln for ln in lines if ln[0] in "*•"]
        if len(bullets) >= 2:            # a real list
            items = "".join(f"<li>{esc(ln.lstrip('*• ').strip())}</li>" for ln in lines
                            if ln[0] in "*•")
            leads = [ln for ln in lines if ln[0] not in "*•"]
            if leads:
                out.append("<p>" + "<br>".join(esc(ln) for ln in leads) + "</p>")
            out.append(f"<ul>{items}</ul>")
        else:
            out.append("<p>" + "<br>".join(esc(ln) for ln in lines) + "</p>")
    return "".join(out)


def letters() -> list:
    """The first-letter section keys present, in order (for the sidebar + index)."""
    seen = []
    for name in sorted(cr.NONWEAPON_PROFICIENCIES, key=str.lower):
        L = name[0].upper()
        if L not in seen:
            seen.append(L)
    return seen


def grouped() -> dict:
    """{letter: [Proficiency, …]} alphabetically — shared shape for page + sidebar."""
    out: dict = {}
    for name in sorted(cr.NONWEAPON_PROFICIENCIES, key=str.lower):
        p = cr.NONWEAPON_PROFICIENCIES[name]
        out.setdefault(name[0].upper(), []).append(p)
    return out


def _card(p) -> str:
    badges = [
        f'<span class="badge slots">{_slots_label(p.slots)}</span>',
        (f'<span class="badge">{esc(p.ability)} check ({p.modifier:+d})</span>'
         if p.ability else '<span class="badge">No ability check</span>'),
        f'<span class="badge cls">{esc(_classes_label(p.classes))}</span>',
    ]
    if p.prereq:
        badges.append(f'<span class="badge pre" title="Prerequisite">'
                      f'{esc(", ".join(p.prereq))}</span>')
    return (
        f'<article class="prof" id="prof-{slug(p.name)}">'
        f'<h3>{esc(p.name)}</h3>'
        f'<div class="badges">{"".join(badges)}</div>'
        f'<div class="body">{_render_desc(p.description)}</div>'
        '</article>'
    )


def generate() -> str:
    groups = grouped()
    total = len(cr.NONWEAPON_PROFICIENCIES)

    index = "".join(f'<a href="#letter-{L}">{L}</a>' for L in groups)

    sections = ""
    for L, profs in groups.items():
        cards = "".join(_card(p) for p in profs)
        sections += f'<section><h2 id="letter-{L}">{L}</h2>{cards}</section>'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #14151d; color: #c8cad8;
         font-family: "Segoe UI", system-ui, sans-serif; line-height: 1.55;
         padding: 32px 40px 80px; }}
  header {{ border-bottom: 1px solid #2a2e40; padding-bottom: 18px; margin-bottom: 8px; }}
  h1 {{ margin: 0; font-size: 26px; color: #f2e8cc; letter-spacing: .3px; }}
  .subtitle {{ color: #8a90a8; font-size: 13px; margin-top: 6px; }}
  /* margins, not flex `gap`: the bundled QtWebEngine Chromium ignores flex gap. */
  .index {{ position: sticky; top: 0; background: #14151dee; backdrop-filter: blur(3px);
           padding: 12px 0; margin: 0 0 8px; display: flex; flex-wrap: wrap;
           border-bottom: 1px solid #20232f; z-index: 5; }}
  .index a {{ display: inline-block; min-width: 24px; text-align: center; text-decoration: none;
             color: {ACCENT}; font-weight: 700; font-size: 13px; padding: 3px 6px; margin: 0 4px 4px 0;
             border: 1px solid #2a2e40; border-radius: 6px; }}
  .index a:hover {{ background: {ACCENT}22; }}
  section {{ margin-top: 10px; }}
  h2 {{ font-size: 20px; color: {ACCENT}; border-bottom: 1px solid #2a2e40;
       padding: 24px 0 6px; margin: 0 0 12px; scroll-margin-top: 60px; }}
  .prof {{ background: #1b1e2b; border: 1px solid #2a2e40; border-radius: 10px;
          padding: 14px 18px; margin: 0 0 12px; scroll-margin-top: 62px; }}
  .prof h3 {{ margin: 0 0 8px; font-size: 16px; color: #e6e9f6; }}
  .badges {{ display: flex; flex-wrap: wrap; margin-bottom: 4px; }}
  .badge {{ font-size: 11px; color: #b9c0d8; background: #23273a; border: 1px solid #313650;
           border-radius: 20px; padding: 2px 10px; margin: 0 6px 6px 0; }}
  .badge.slots {{ color: {ACCENT}; border-color: {ACCENT}55; }}
  .badge.cls {{ color: #8fb7d6; }}
  .badge.pre {{ color: #d6a866; border-color: #6b5426; }}
  .body p {{ margin: 0 0 8px; }}
  .body ul {{ margin: 0 0 8px; padding-left: 20px; }}
  .body li {{ margin: 0 0 4px; }}
  a {{ color: {ACCENT}; }}
</style></head><body>
  <header>
    <h1>{esc(cr.PROFICIENCY_BOOK)}</h1>
    <div class="subtitle">Nonweapon Proficiencies &middot; {total} skills &middot;
      hover a skill in the picker or open the Character Builder to spend slots.</div>
  </header>
  <nav class="index">{index}</nav>
  {sections}
</body></html>"""

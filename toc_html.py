"""toc_html.py — HTML for a book's table-of-contents page and the per-page
house-rules callout.

Pure string builders (no DB, no Qt), matching the other *_html screen modules.
Callers pass the resolved book name / accent colour and the already-fetched
chapters and house rules, so this is unit-testable (see tests/test_screens.py).

Content comes from the local rulebook DB, so it is trusted — but trusted is not the
same as *well-formed*, which is why it is escaped anyway. Nine `toc_entries` rows
carry a bare `&` ("AD&D Game Line", "Gear & Equipment"); emitting those raw is
invalid markup that only renders correctly because browsers recover from it. No
row in either table contains `<`, so escaping changes nothing else on screen.
"""
from view_common import esc


def _chapter_house_rules(chapter_name: str, hr_by_chapter: dict) -> list:
    """House-rule (category, text) tuples whose keyword names this chapter."""
    out = []
    for keyword, rules in hr_by_chapter.items():
        if (keyword + ":") in chapter_name or chapter_name == keyword:
            out.extend(rules)
    return out


def book_toc(book_name: str, accent: str, chapters: list, hr_by_chapter: dict) -> str:
    """The full table-of-contents page for one book."""
    rows = ""
    for i, ch in enumerate(chapters, 1):
        count = len(ch["entries"])
        num   = f"{i:02d}"
        name_html = (f'<a href="dnd:///{esc(ch["page_url"])}">{esc(ch["name"])}</a>'
                     if ch.get("page_url") else esc(ch["name"]))

        ch_rules = _chapter_house_rules(ch["name"], hr_by_chapter)
        badge = hr_block = ""
        if ch_rules:
            badge = (
                f' <span style="background:{accent}22;color:{accent};font-size:9px;'
                f'font-weight:700;padding:2px 7px;border-radius:3px;'
                f'letter-spacing:.06em;vertical-align:middle;">⚔ HR</span>'
            )
            by_cat: dict = {}
            for cat, text in ch_rules:
                by_cat.setdefault(cat, []).append(text)
            inner = ""
            for cat, texts in by_cat.items():
                inner += f'<div class="hr-cat">{esc(cat)}</div><ul class="hr-list">'
                inner += "".join(f"<li>{esc(text)}</li>" for text in texts)
                inner += "</ul>"
            hr_block = f'<div class="hr-block">{inner}</div>'

        rows += (
            f'    <div class="row">'
            f'<span class="num">{num}</span>'
            f'<span class="name">{name_html}{badge}</span>'
            f'<span class="count">{count}</span>'
            f'</div>\n'
            f'{hr_block}'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: #2a2d36;
    min-height: 100vh;
    padding: 56px 72px;
  }}
  .book-tag {{
    display: inline-block;
    background: {accent}18;
    color: {accent};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 4px;
    margin-bottom: 14px;
  }}
  h1 {{
    font-size: 2.4em;
    font-weight: 800;
    color: #e4e6f0;
    line-height: 1.1;
    margin-bottom: 6px;
  }}
  .divider {{
    height: 3px;
    width: 48px;
    background: {accent};
    border-radius: 2px;
    margin: 18px 0 36px;
  }}
  .toc {{ max-width: 720px; }}
  .row > * + * {{ margin-left: 18px; }}  /* QtWebEngine drops flex gap */
  .row {{
    display: flex;
    align-items: baseline;
    padding: 13px 10px;
    border-radius: 8px;
    transition: background .12s;
    cursor: default;
  }}
  .row:hover {{ background: #323642; }}
  .num {{
    font-size: 11px;
    font-weight: 700;
    color: #bdc3d0;
    min-width: 22px;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }}
  .name {{
    flex: 1;
    font-size: 15px;
    color: #c8cad8;
    font-weight: 500;
  }}
  .name a {{ color: {accent}; text-decoration: none; }}
  .name a:hover {{ text-decoration: underline; }}
  .count {{
    font-size: 12px;
    color: #9ca3af;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }}
  .count::after {{ content: " entries"; }}
  .hr-block {{
    margin: 0 0 6px 50px;
    padding: 10px 14px 12px;
    background: {accent}0f;
    border-left: 2px solid {accent}55;
    border-radius: 0 4px 4px 0;
  }}
  .hr-cat {{
    color: {accent};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .09em;
    text-transform: uppercase;
    margin-bottom: 4px;
    margin-top: 10px;
  }}
  .hr-cat:first-child {{ margin-top: 0; }}
  .hr-list {{
    margin: 0 0 0 14px;
    padding: 0;
    color: #9ca3b8;
    font-size: 12px;
    line-height: 1.7;
  }}
  hr.sep {{ border: none; border-top: 1px solid #3a3e50; margin: 2px 0; }}
</style>
</head>
<body>
  <div class="book-tag">2nd Edition AD&amp;D</div>
  <h1>{esc(book_name)}</h1>
  <div class="divider"></div>
  <div class="toc">
{rows}
  </div>
</body>
</html>"""


def house_rules_callout(rules: list, accent: str) -> str:
    """A slim, collapsed house-rules chip injected at the top of a rules page."""
    by_cat: dict = {}
    for cat, text in rules:
        by_cat.setdefault(cat, []).append(text)

    inner = ""
    for cat, texts in by_cat.items():
        items = "".join(f"<li>{esc(text)}</li>" for text in texts)
        inner += (f'<div class="hrx-cat" style="color:{accent}">{esc(cat)}</div>'
                  f'<ul class="hrx-list">{items}</ul>')

    return f"""<style>
      .hrx {{ margin: 2px 0 26px; font-family:'Segoe UI',system-ui,sans-serif; }}
      .hrx > summary {{ list-style:none; cursor:pointer; outline:none; user-select:none;
        display:inline-flex; align-items:center; padding:6px 14px;
        border-radius:7px; background:#23262f; border:1px solid #34384a;
        color:#aeb4c6; font-size:12px; font-weight:600;
        transition:background .12s, border-color .12s; }}
      .hrx > summary:hover {{ background:#2a2e3c; border-color:{accent}; }}
      .hrx > summary::-webkit-details-marker {{ display:none; }}
      .hrx-ico {{ font-size:13px; }}
      .hrx-txt {{ margin:0 10px; }}
      .hrx-body {{ margin-top:10px; padding:12px 16px 14px; background:#1d2028;
        border:1px solid #2a2e3b; border-left:3px solid {accent}; border-radius:8px; }}
      .hrx-cat {{ font-size:10px; font-weight:700; letter-spacing:.09em;
        text-transform:uppercase; margin:14px 0 5px; }}
      .hrx-cat:first-child {{ margin-top:0; }}
      .hrx-list {{ margin:0 0 0 18px; padding:0; color:#c2c6d6; font-size:13.5px; line-height:1.7; }}
      .hrx-list li {{ margin-bottom:3px; }}
    </style>
    <details class="hrx">
      <summary>
        <span class="hrx-ico">&#x2694;&#xFE0F;</span>
        <span class="hrx-txt">House rules affect this chapter</span>
        <span class="hrx-ico">&#x2694;&#xFE0F;</span>
      </summary>
      <div class="hrx-body">{inner}</div>
    </details>"""

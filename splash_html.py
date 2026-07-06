"""splash_html.py — Welcome / landing screen for the D&D 2E app."""
from html import escape as e

BOOKS = [
    ("PHB", "Player's Handbook",        "#5b9bd5"),
    ("DMG", "Dungeon Master Guide",     "#e07b2a"),
    ("MM",  "Monstrous Manual",         "#4db870"),
    ("SP",  "Skills & Powers",          "#c8a828"),
    ("HLC", "High-Level Campaigns",     "#a76bcc"),
    ("TM",  "Tome of Magic",            "#e05555"),
    ("SM",  "Spells & Magic",           "#3dbfa8"),
    ("CT",  "Combat & Tactics",         "#e0924a"),
    ("AEG", "Arms & Equipment Guide",   "#8a9bb0"),
    ("ECO", "Economics of the Realm",   "#c9a84c"),
]

FEATURES = [
    ("screen/charactermancer",  "🧙",  "Character Builder",
     "Build a 2e character step by step — abilities, race, class, proficiencies, equipment, and spells — with house rules and PHB references.",
     "#c9a84c", "#22200a"),
    ("screen/dmscreen", "⚔",  "DM Screen",
     "50+ quick-reference tables — THAC0, saves, ability scores, spells, and more.",
     "#e05555", "#220a0a"),
    ("screen/actions",  "⚡", "Actions Reference",
     "Every combat action explained: offense, defense, movement, and forced movement.",
     "#5b9bd5", "#0a1222"),
    ("screen/spells",   "📖", "Spell Compendium",
     "Every wizard & priest spell — searchable and filterable by class, level, and school.",
     "#b06fd6", "#170a22"),
]


def generate() -> str:
    book_chips = ""
    for code, name, color in BOOKS:
        book_chips += (
            f'<a class="book-chip" href="dnd:///toc/{code}" '
            f'style="border-color:{color};color:{color}" title="{e(name)}">'
            f'{e(code)}</a>'
        )

    feature_cards = ""
    for url, icon, title, desc, color, bg in FEATURES:
        feature_cards += f"""
<a class="feat-card" href="dnd:///{url}"
   style="--fc:{color};--fb:{bg}">
  <div class="feat-icon">{icon}</div>
  <div class="feat-title">{e(title)}</div>
  <div class="feat-desc">{e(desc)}</div>
  <div class="feat-arrow">Open →</div>
</a>"""

    css = """
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      body {
        background: #0f1018;
        font-family: "Segoe UI", system-ui, sans-serif;
        color: #c8cad8;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background-image:
          radial-gradient(ellipse 80% 50% at 50% -10%, rgba(201,168,76,.07) 0%, transparent 70%),
          radial-gradient(ellipse 60% 40% at 50% 110%, rgba(91,155,213,.04) 0%, transparent 70%);
      }

      /* ── Outer frame ── */
      .frame {
        width: min(820px, 96vw);
        padding: 48px 52px 40px;
        position: relative;
        border: 1px solid #2a2d3e;
        background: #13151f;
        box-shadow:
          0 0 0 1px #1c1e2c,
          0 0 60px rgba(0,0,0,.6),
          inset 0 1px 0 rgba(201,168,76,.06);
      }

      /* corner decorations */
      .frame::before, .frame::after,
      .frame .c2::before, .frame .c2::after {
        content: "";
        position: absolute;
        width: 18px; height: 18px;
        border-color: #4a3c10;
        border-style: solid;
      }
      .frame::before  { top: 8px; left: 8px;   border-width: 2px 0 0 2px; }
      .frame::after   { top: 8px; right: 8px;  border-width: 2px 2px 0 0; }
      .frame .c2::before { bottom: 8px; left: 8px;  border-width: 0 0 2px 2px; }
      .frame .c2::after  { bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }

      /* ── Hero ── */
      .hero {
        text-align: center;
        padding-bottom: 32px;
        border-bottom: 1px solid #1e2030;
        position: relative;
      }

      .pre-title {
        font-size: 10.5px;
        letter-spacing: .25em;
        text-transform: uppercase;
        color: #4a5070;
        margin-bottom: 22px;
      }

      .sword-row {
        font-size: 18px;
        color: #3a3010;
        margin-bottom: 18px;
        letter-spacing: .2em;
        user-select: none;
      }

      .main-title {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 13px;
        letter-spacing: .3em;
        text-transform: uppercase;
        color: #5a6080;
        margin-bottom: 6px;
      }

      .edition {
        font-family: Georgia, "Times New Roman", serif;
        font-size: 46px;
        font-weight: bold;
        letter-spacing: .04em;
        color: #c9a84c;
        line-height: 1;
        margin-bottom: 6px;
        animation: glow 4s ease-in-out infinite;
      }

      .sub-title {
        font-size: 11px;
        letter-spacing: .35em;
        text-transform: uppercase;
        color: #4a5070;
        margin-bottom: 28px;
      }

      .divider > * + * { margin-left: 12px; }  /* QtWebEngine drops flex gap */
      .divider {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #3a3010;
        font-size: 12px;
      }
      .divider-line {
        flex: 1;
        max-width: 160px;
        height: 1px;
        background: linear-gradient(to right, transparent, #3a3010);
      }
      .divider-line.r { background: linear-gradient(to left, transparent, #3a3010); }
      .divider-gem { color: #7a6020; font-size: 10px; }

      @keyframes glow {
        0%, 100% { text-shadow: 0 0 24px rgba(201,168,76,.25), 0 0 48px rgba(201,168,76,.08); }
        50%       { text-shadow: 0 0 36px rgba(201,168,76,.45), 0 0 72px rgba(201,168,76,.15); }
      }

      /* ── Books section ── */
      .section-label {
        font-size: 9.5px;
        letter-spacing: .2em;
        text-transform: uppercase;
        color: #3a3f58;
        margin: 28px 0 12px;
      }

      .book-chips > * { margin: 0 7px 7px 0; }  /* QtWebEngine drops flex gap */
      .book-chips {
        display: flex;
        flex-wrap: wrap;
      }

      .book-chip {
        display: inline-block;
        padding: 5px 13px;
        border: 1px solid;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: .1em;
        text-decoration: none;
        background: rgba(255,255,255,.02);
        transition: background .15s, box-shadow .15s;
      }
      .book-chip:hover {
        background: rgba(255,255,255,.06);
        box-shadow: 0 0 8px rgba(255,255,255,.04);
      }

      /* ── Feature cards ── */
      .feat-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-top: 14px;
      }

      .feat-card > * + * { margin-top: 8px; }  /* QtWebEngine drops flex gap */
      .feat-card {
        display: flex;
        flex-direction: column;
        padding: 20px 18px 18px;
        border: 1px solid #1e2130;
        border-radius: 8px;
        background: var(--fb);
        text-decoration: none;
        color: inherit;
        transition: border-color .15s, transform .12s, box-shadow .15s;
        position: relative;
        overflow: hidden;
      }
      .feat-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: var(--fc);
        opacity: .5;
        transition: opacity .15s;
      }
      .feat-card:hover {
        border-color: var(--fc);
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(0,0,0,.35);
      }
      .feat-card:hover::before { opacity: 1; }

      .feat-icon {
        font-size: 22px;
        color: var(--fc);
        line-height: 1;
      }
      .feat-title {
        font-size: 13px;
        font-weight: 700;
        color: #e0e2f0;
        letter-spacing: .03em;
      }
      .feat-desc {
        font-size: 11px;
        color: #5a6080;
        line-height: 1.6;
        flex: 1;
      }
      .feat-arrow {
        font-size: 10.5px;
        color: var(--fc);
        opacity: .6;
        letter-spacing: .06em;
        margin-top: 4px;
        transition: opacity .15s;
      }
      .feat-card:hover .feat-arrow { opacity: 1; }

      /* ── Footer quote ── */
      .quote {
        margin-top: 32px;
        padding-top: 24px;
        border-top: 1px solid #1e2030;
        text-align: center;
        color: #2e3248;
        font-family: Georgia, serif;
        font-style: italic;
        font-size: 12px;
        line-height: 1.7;
        letter-spacing: .02em;
      }
      .quote cite {
        display: block;
        margin-top: 6px;
        font-size: 10px;
        letter-spacing: .15em;
        font-style: normal;
        text-transform: uppercase;
      }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>D&amp;D 2nd Edition — Rules Reference</title>
<style>{css}</style>
</head>
<body>
<div class="frame">
  <div class="c2"></div>

  <div class="hero">
    <div class="pre-title">Welcome to the</div>
    <div class="sword-row">✦ &nbsp; ◆ &nbsp; ✦</div>
    <div class="main-title">Advanced Dungeons &amp; Dragons</div>
    <div class="edition">2nd Edition</div>
    <div class="sub-title">Rules Reference &nbsp;&amp;&nbsp; Campaign Tools</div>
    <div class="divider">
      <div class="divider-line"></div>
      <span class="divider-gem">◆</span>
      <div class="divider-line r"></div>
    </div>
  </div>

  <div class="section-label">Books &amp; Sourcebooks</div>
  <div class="book-chips">
    {book_chips}
  </div>

  <div class="section-label" style="margin-top:28px">Quick Reference</div>
  <div class="feat-grid">
    {feature_cards}
  </div>

  <div class="quote">
    "The secret we should never let the game masters know is that they don't
    need any rules."
    <cite>— Gary Gygax</cite>
  </div>
</div>
</body>
</html>"""

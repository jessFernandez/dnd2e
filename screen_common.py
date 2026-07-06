"""screen_common.py — Shared layout for the card-grid reference screens.

Both the DM Screen and the Actions Screen are the same kind of page: a sticky
search / category bar above a set of category sections, each holding a compact
grid of cards.  The common CSS chrome, the masonry + filter script, the section
builder, and the page skeleton live here so the individual screens only supply
their category metadata, their cards, and any small style tweaks (``css_extra``).
"""

import re

# Chrome shared by every card-grid screen.  Screen-specific rules (card-body
# padding, table-cell spacing, rule lists, section labels …) are appended after
# this via ``css_extra`` and therefore win where they overlap.
COMMON_CSS = """
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: #1a1c26; font-family: "Segoe UI", system-ui, sans-serif;
             font-size: 12px; color: #c8cad8; }
      .top-bar > * + * { margin-top: 8px; }  /* QtWebEngine drops flex gap */
      .top-bar { position: sticky; top: 0; z-index: 100; background: #13151f;
                 border-bottom: 1px solid #2a2d3e; padding: 10px 14px;
                 display: flex; flex-direction: column; }
      .search-row > * + * { margin-left: 8px; }  /* QtWebEngine drops flex gap */
      .search-row { display: flex; align-items: center; }
      #search { flex: 1; background: #23263a; border: 1px solid #383c52;
                border-radius: 6px; color: #e0e2f0; padding: 7px 12px;
                font-size: 13px; outline: none; }
      #search:focus { border-color: #c9a84c; }
      #clear-btn { background: #23263a; border: 1px solid #383c52; border-radius: 6px;
                   color: #9ca3c0; padding: 6px 12px; cursor: pointer; font-size: 12px; }
      #clear-btn:hover { background: #2d3048; }
      .cat-row > * { margin: 0 6px 6px 0; }  /* QtWebEngine drops flex gap */
      .cat-row { display: flex; flex-wrap: wrap; }
      .cat-btn, #all-btn { background: #23263a; border: 1px solid #383c52;
                           border-radius: 5px; color: #c8cad8; padding: 4px 10px;
                           cursor: pointer; font-size: 11px; font-weight: 600;
                           letter-spacing: .04em; transition: background .1s; }
      .cat-btn:hover, .cat-btn.active,
      #all-btn:hover, #all-btn.active { background: #2d3048; }
      .fold-btn { background: transparent; border: 1px solid #2a2e45; color: #7c85a8;
                  border-radius: 5px; padding: 4px 10px; cursor: pointer; font-size: 11px;
                  font-weight: 600; letter-spacing: .04em; }
      #collapse-all { margin-left: auto; }  /* push the fold controls to the right edge */
      .fold-btn:hover { background: #23263a; color: #c8cad8; }

      /* ── Category sections (collapsible) ── */
      .screen { padding: 14px 0 28px; }
      .cat-section { margin: 0 12px 20px; }
      .cat-header { display: flex; align-items: center; margin: 0 0 12px;
                    padding-bottom: 7px; border-bottom: 2px solid var(--c);
                    cursor: pointer; user-select: none; }
      .cat-header::before { content: ""; width: 9px; height: 9px; border-radius: 2px;
                            background: var(--c); flex-shrink: 0; margin-right: 9px; }  /* QtWebEngine drops flex gap */
      .cat-header:hover .cat-name { color: #fff; }
      .cat-name { font-size: 12.5px; font-weight: 800; letter-spacing: .09em;
                  text-transform: uppercase; color: #e6e9f6; }
      .cat-count { margin-left: auto; font-size: 10.5px; font-weight: 700; color: #8891b5;
                   background: #1c1f32; border: 1px solid #2a2e45; border-radius: 9px;
                   padding: 1px 8px; }
      .cat-chevron { margin-left: 10px; color: #6878a8; font-size: 11px; flex-shrink: 0;
                     transition: transform .15s ease; }
      .cat-section.collapsed .cat-chevron { transform: rotate(-90deg); }
      .cat-section.collapsed .cat-header { margin-bottom: 0; }
      .cat-section.collapsed .grid { display: none; }

      /* ── Card grid: JS masonry positions cards absolutely inside .grid ── */
      .grid { position: relative; }
      .card { position: absolute; top: 0; left: 0; width: 100%;
              background: #21243a; border-radius: 7px; overflow: hidden;
              border: 1px solid #2a2e45; }
      .card-head > * + * { margin-left: 8px; }  /* QtWebEngine drops flex gap */
      .card-head { display: flex; align-items: center; padding: 8px 10px;
                   background: #1c1f32; }
      .cat-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
      .card-title { font-size: 11px; font-weight: 700; letter-spacing: .07em;
                    text-transform: uppercase; color: #e0e2f0; }
      .card-body { padding: 10px; }
      .tscroll { overflow-x: auto; }
      table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
      th { background: #17192a; color: #a0a8cc; font-size: 10px; font-weight: 700;
           letter-spacing: .06em; text-transform: uppercase; padding: 5px 7px;
           white-space: nowrap; border-bottom: 1px solid #2a2e45; }
      td { padding: 6px 8px; border-bottom: 1px solid #23263a; color: #c0c4d8;
           vertical-align: top; }
      tr:hover td { background: #262a40; }
      td.r, th.r { text-align: right; }
      .note { color: #5a6080; font-size: 10.5px; font-style: italic;
              margin-top: 8px; line-height: 1.5; }
"""

# Per-section masonry plus search / category filtering.
#
# Each section is packed independently: columns adapt to the window width, then
# cards are measured and placed largest-first into whichever column stack is
# currently shortest (span-2 / span-3 cards occupy the best-fitting run of
# adjacent columns).  This balances the columns and minimises wasted vertical
# space.  A category button shows just that section; the search box filters
# individual cards and hides any section left empty.
SCREEN_SCRIPT = """
      const GAP = 12, MIN_COL = 300, MAX_COLS = 4;
      const sections = Array.from(document.querySelectorAll('.cat-section'));
      let activeCat = 'all';

      const spanOf = c =>
        c.classList.contains('span-3') ? 3 : c.classList.contains('span-2') ? 2 : 1;

      function layoutGrid(grid) {
        const cw = grid.clientWidth;
        if (cw <= 0) return;
        const cols = Math.max(1, Math.min(MAX_COLS, Math.floor((cw + GAP) / (MIN_COL + GAP))));
        const colW = (cw - (cols - 1) * GAP) / cols;

        const cards = Array.from(grid.children)
          .filter(c => c.classList.contains('card') && c.style.display !== 'none');

        // Give every card its final width so heights measure correctly.
        for (const card of cards) {
          const span = Math.min(spanOf(card), cols);
          card._span = span;
          card.style.width = (span * colW + (span - 1) * GAP) + 'px';
        }
        // Measure once (forces a single reflow), then order each section so the
        // widest reference tables anchor the top and smaller ones pack beneath —
        // widest span first, tallest first within a span. Because placement below
        // always picks the shortest fitting column run, the narrow gap left beside
        // a wide table gets back-filled by a later small card, keeping columns even.
        for (const card of cards) card._h = card.offsetHeight;
        cards.sort((a, b) => (b._span - a._span) || (b._h - a._h));

        const colH = new Array(cols).fill(0);
        for (const card of cards) {
          const span = card._span, h = card._h;
          let bestCol = 0, bestTop = Infinity;
          for (let c = 0; c + span <= cols; c++) {
            let top = 0;
            for (let k = c; k < c + span; k++) top = Math.max(top, colH[k]);
            if (top < bestTop) { bestTop = top; bestCol = c; }
          }
          card.style.left = (bestCol * (colW + GAP)) + 'px';
          card.style.top  = bestTop + 'px';
          for (let k = bestCol; k < bestCol + span; k++) colH[k] = bestTop + h + GAP;
        }
        grid.style.height = Math.max(0, Math.max(...colH) - GAP) + 'px';
      }

      function layoutAll() {
        for (const sec of sections) {
          if (sec.style.display === 'none') continue;
          layoutGrid(sec.querySelector('.grid'));
        }
      }

      // Collapsing a category hides its grid (cards stay in the DOM, so search
      // can still reveal them); expanding re-runs masonry since a hidden grid
      // measures as zero height.
      function toggleSection(header) {
        const sec = header.closest('.cat-section');
        const collapsed = sec.classList.toggle('collapsed');
        if (!collapsed) layoutGrid(sec.querySelector('.grid'));
      }
      function setAllCollapsed(collapsed) {
        for (const sec of sections) {
          if (sec.style.display === 'none') continue;
          sec.classList.toggle('collapsed', collapsed);
        }
        if (!collapsed) layoutAll();
      }

      function applyFilter() {
        const q = document.getElementById('search').value.toLowerCase();
        for (const sec of sections) {
          const catShown = (activeCat === 'all' || activeCat === sec.dataset.cat);
          let anyVisible = false;
          for (const card of sec.querySelectorAll('.card')) {
            const textMatch = !q || card.textContent.toLowerCase().includes(q);
            const show = catShown && textMatch;
            card.style.display = show ? '' : 'none';
            if (show) anyVisible = true;
          }
          sec.style.display = anyVisible ? '' : 'none';
          if (q && anyVisible) sec.classList.remove('collapsed');  // reveal matches in a folded section
        }
        layoutAll();
      }
      function filterCat(cat) {
        activeCat = cat;
        document.querySelectorAll('.cat-btn, #all-btn').forEach(b => b.classList.remove('active'));
        const el = cat === 'all'
          ? document.getElementById('all-btn')
          : document.querySelector(`.cat-btn[data-cat="${cat}"]`);
        if (el) el.classList.add('active');
        applyFilter();
      }
      document.getElementById('search').addEventListener('input', applyFilter);
      document.getElementById('clear-btn').addEventListener('click', () => {
        document.getElementById('search').value = '';
        applyFilter();
      });
      document.getElementById('all-btn').classList.add('active');

      let resizeTimer;
      window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(layoutAll, 120);
      });
      window.addEventListener('load', layoutAll);
      layoutAll();
"""

_CARD_CAT_RE = re.compile(r'data-cat="([^"]+)"')


def render_sections(cards, cat_order, cat_labels, cat_colors) -> str:
    """Group a flat list of card-HTML strings by their data-cat attribute and
    emit one titled section per category, in cat_order."""
    groups: dict = {}
    for html in cards:
        m = _CARD_CAT_RE.search(html)
        cat = m.group(1) if m else (cat_order[0] if cat_order else "")
        groups.setdefault(cat, []).append(html)

    out = []
    for cat in cat_order:
        items = groups.get(cat)
        if not items:
            continue
        color = cat_colors.get(cat, "#8b93b8")
        label = cat_labels.get(cat, cat.title())
        out.append(
            f'<section class="cat-section" data-cat="{cat}">'
            f'<div class="cat-header" style="--c:{color}" onclick="toggleSection(this)">'
            f'<span class="cat-name">{label}</span>'
            f'<span class="cat-count">{len(items)}</span>'
            f'<span class="cat-chevron">▾</span>'
            f'</div>'
            f'<div class="grid" data-cat="{cat}">{"".join(items)}</div>'
            f'</section>'
        )
    return "".join(out)


def page(title: str, css_extra: str, cat_buttons: str, body_html: str,
         search_placeholder: str) -> str:
    """Assemble a full card-grid screen document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{COMMON_CSS}{css_extra}</style>
</head>
<body>
<div class="top-bar">
  <div class="search-row">
    <input id="search" type="text" placeholder="{search_placeholder}" autocomplete="off">
    <button id="clear-btn">Clear</button>
  </div>
  <div class="cat-row">
    <button id="all-btn" onclick="filterCat('all')">All</button>
    {cat_buttons}
    <button id="collapse-all" class="fold-btn" onclick="setAllCollapsed(true)">Collapse all</button>
    <button id="expand-all" class="fold-btn" onclick="setAllCollapsed(false)">Expand all</button>
  </div>
</div>
<div class="screen">
{body_html}
</div>
<script>{SCREEN_SCRIPT}</script>
</body>
</html>"""

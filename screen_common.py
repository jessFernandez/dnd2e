"""screen_common.py — Shared layout for the card-grid reference screens.

Both the DM Screen and the Actions Screen are the same kind of page: a sticky
search/category bar above a masonry grid of category-coloured cards.  The common
CSS chrome, the masonry + filter script, and the page skeleton live here so the
individual screens only have to supply their category buttons, their cards, and
whatever small style tweaks are unique to them (via ``css_extra``).
"""

# Chrome shared by every card-grid screen.  Screen-specific rules (card-body
# padding, table-cell spacing, rule lists, section labels …) are appended after
# this via ``css_extra`` and therefore win where they overlap.
COMMON_CSS = """
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: #1a1c26; font-family: "Segoe UI", system-ui, sans-serif;
             font-size: 12px; color: #c8cad8; }
      .top-bar { position: sticky; top: 0; z-index: 100; background: #13151f;
                 border-bottom: 1px solid #2a2d3e; padding: 10px 14px;
                 display: flex; flex-direction: column; gap: 8px; }
      .search-row { display: flex; gap: 8px; align-items: center; }
      #search { flex: 1; background: #23263a; border: 1px solid #383c52;
                border-radius: 6px; color: #e0e2f0; padding: 7px 12px;
                font-size: 13px; outline: none; }
      #search:focus { border-color: #5b6aaa; }
      #clear-btn { background: #23263a; border: 1px solid #383c52; border-radius: 6px;
                   color: #9ca3c0; padding: 6px 12px; cursor: pointer; font-size: 12px; }
      #clear-btn:hover { background: #2d3048; }
      .cat-row { display: flex; gap: 6px; flex-wrap: wrap; }
      .cat-btn, #all-btn { background: #23263a; border: 1px solid #383c52;
                           border-radius: 5px; color: #c8cad8; padding: 4px 10px;
                           cursor: pointer; font-size: 11px; font-weight: 600;
                           letter-spacing: .04em; transition: background .1s; }
      .cat-btn:hover, .cat-btn.active,
      #all-btn:hover, #all-btn.active { background: #2d3048; }
      .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
              grid-auto-rows: 8px; column-gap: 12px; row-gap: 12px;
              padding: 12px; align-items: start; }
      .card { background: #21243a; border-radius: 7px; overflow: hidden;
              border: 1px solid #2a2e45; align-self: start; }
      .card.span-2 { grid-column: span 2; }
      .card.span-3 { grid-column: span 3; }
      .card[style*="display:none"], .card[style*="display: none"] { display: none !important; }
      .card-head { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
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

# Masonry packing (variable-height cards, no row gaps) plus search/category
# filtering.  Re-packs after filtering and on window resize.
SCREEN_SCRIPT = """
      const grid  = document.querySelector('.grid');
      const cards = Array.from(document.querySelectorAll('.card'));
      let activeCat = 'all';

      function layoutMasonry() {
        const styles  = getComputedStyle(grid);
        const rowUnit = parseFloat(styles.gridAutoRows) || 8;
        const rowGap  = parseFloat(styles.rowGap) || 0;
        for (const card of cards) {
          if (card.style.display === 'none') continue;
          const h = card.getBoundingClientRect().height;
          const span = Math.ceil((h + rowGap) / (rowUnit + rowGap));
          card.style.gridRowEnd = 'span ' + span;
        }
      }

      function applyFilter() {
        const q = document.getElementById('search').value.toLowerCase();
        cards.forEach(c => {
          const catMatch = activeCat === 'all' || c.dataset.cat === activeCat;
          const textMatch = !q || c.textContent.toLowerCase().includes(q);
          c.style.display = (catMatch && textMatch) ? '' : 'none';
        });
        layoutMasonry();
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
        resizeTimer = setTimeout(layoutMasonry, 120);
      });
      window.addEventListener('load', layoutMasonry);
      layoutMasonry();
"""


def page(title: str, css_extra: str, cat_buttons: str, grid_html: str,
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
  </div>
</div>
{grid_html}
<script>{SCREEN_SCRIPT}</script>
</body>
</html>"""

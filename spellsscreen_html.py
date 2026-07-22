"""spellsscreen_html.py — the 2e Spell Compendium screen.

Renders every wizard and priest spell (imported by build_spells.py into the
`spells` table) as a filterable card grid: search by name/effect and narrow by
caster and level, plus a context category that follows the caster — school for
All, wizard specialization for Wizard, priest sphere for Priest. Cards are
masonry-packed and colour-coded by school.
"""
import re
from view_common import esc


def spell_slug(name: str) -> str:
    """The stable anchor slug for a spell name — 'Cone of Cold' -> 'cone-of-cold'.
    Owned here because this screen emits the ``id="spell-<slug>"`` anchors; the
    monster spell-linker (monster_spells) imports it so its links can't drift from
    the ids they target."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


# School accent colours (readable on the dark background, both casters share them).
SCHOOL_COLORS = {
    "Abjuration":  "#5b9bd5",
    "Alteration":  "#3fb6a0",
    "Conjuration": "#d99a3f",
    "Divination":  "#9b8cce",
    "Enchantment": "#e07ba0",
    "Evocation":   "#e0684a",
    "Illusion":    "#b06fd6",
    "Necromancy":  "#6f9f74",
}
SCHOOL_ORDER = list(SCHOOL_COLORS)

# Wizard specialists (filter = spells that specialist can learn) and priest spheres.
SPEC_ORDER = ["Abjurer", "Conjurer", "Diviner", "Enchanter", "Illusionist",
              "Invoker", "Necromancer", "Transmuter", "Dimensionalist"]
SPHERE_ORDER = ["Animal", "Astral", "Chaos", "Charm", "Combat", "Creation", "Divination",
                "Elemental Air", "Elemental Earth", "Elemental Fire", "Elemental Water",
                "Guardian", "Healing", "Law", "Necromantic", "Numbers", "Plant",
                "Protection", "Summoning", "Sun", "Thought", "Time", "Travelers", "War",
                "Wards", "Weather"]


def _tok(csv: str) -> str:
    """A comma list -> '|a|b|' form for substring membership tests in JS ('' if empty)."""
    parts = [p.strip() for p in (csv or "").split(",") if p.strip()]
    return "|" + "|".join(parts) + "|" if parts else ""


def _desc_html(text: str) -> str:
    paras = [esc(p).strip() for p in (text or "").split("\n") if p.strip()]
    return "<br><br>".join(paras)


def _stat(label: str, value: str) -> str:
    v = (value or "").strip()
    return f'<div class="st"><span>{esc(label)}</span><b>{esc(v) if v else "—"}</b></div>'


def _card(s: dict, anchor: str = "") -> str:
    school = s.get("school") or ""
    color = SCHOOL_COLORS.get(school, "#8b93b8")
    caster = (s.get("caster") or "").capitalize()
    comps = "".join(f"<i>{esc(c.strip())}</i>" for c in (s.get("components") or "").split(",") if c.strip())
    spheres, specs = (s.get("spheres") or ""), (s.get("specializations") or "")
    # Priest cards read more naturally by sphere than by the site's assigned school.
    cat_label = spheres if (s.get("caster") == "priest" and spheres) else school

    stats = "".join([
        _stat("Range", s.get("range", "")),
        _stat("Casting Time", s.get("casting_time", "")),
        _stat("Duration", s.get("duration", "")),
        _stat("Area", s.get("aoe", "")),
        _stat("Saving Throw", s.get("save", "")),
        _stat("Damage", s.get("damage", "")),
    ])
    mat = ""
    if (s.get("materials") or "").strip():
        mat = f'<div class="mat"><span>Materials</span> {esc(s["materials"].strip())}</div>'

    foot_bits = []
    if (s.get("residue") or "").strip():
        foot_bits.append(f'<span class="res">Residue: {esc(s["residue"].strip())}</span>')
    if (s.get("source") or "").strip():
        foot_bits.append(f'<span class="src">{esc(s["source"].strip())}</span>')
    foot = f'<div class="foot">{"".join(foot_bits)}</div>' if foot_bits else ""

    lvl = s.get("level") or 0
    anchor_attr = f' id="{anchor}"' if anchor else ""
    return (
        f'<article class="card"{anchor_attr} style="--sc:{color}" '
        f'data-caster="{esc(s.get("caster",""))}" data-level="{lvl}" '
        f'data-school="{esc(school)}" '
        f'data-spheres="{esc(_tok(spheres))}" data-specs="{esc(_tok(specs))}">'
        f'<div class="chead">'
        f'<span class="lvl" title="Level {lvl}">{lvl}</span>'
        f'<div class="ctitle"><div class="nm">{esc(s.get("name",""))}</div>'
        f'<div class="meta">{caster} · {esc(cat_label)}<span class="comp">{comps}</span></div></div>'
        f'</div>'
        f'<div class="stats">{stats}</div>'
        f'{mat}'
        f'<div class="desc">{_desc_html(s.get("description",""))}</div>'
        f'<button class="more" type="button">more</button>'
        f'{foot}'
        f'</article>'
    )


def _cat_pills(names, with_dots=False) -> str:
    out = ['<button class="pill on" data-k="all">All</button>']
    for name in names:
        dot = (f'<span class="dot" style="background:{SCHOOL_COLORS[name]}"></span>'
               if with_dots else "")
        out.append(f'<button class="pill" data-k="{esc(name)}">{dot}{esc(name)}</button>')
    return "".join(out)


def generate(spells) -> str:
    spells = sorted(spells, key=lambda s: (s.get("caster", ""), s.get("level", 0), s.get("name", "")))
    # One `id="spell-<slug>"` anchor per distinct name (the first card), so a
    # dnd:///spell/<slug> link from a monster sheet scrolls here. Duplicate names
    # (same spell, two schools) share the slug; the first card wins the id.
    seen = set()
    cards = []
    for s in spells:
        slug = spell_slug(s.get("name", ""))
        anchor = "" if (not slug or slug in seen) else f"spell-{slug}"
        seen.add(slug)
        cards.append(_card(s, anchor))
    cards = "".join(cards)
    n_wiz = sum(1 for s in spells if s.get("caster") == "wizard")
    n_pri = sum(1 for s in spells if s.get("caster") == "priest")
    level_pills = "".join(f'<button class="pill lvl" data-k="{i}">{i}</button>' for i in range(1, 10))

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Spells</title><style>{_CSS}</style></head>
<body>
<div class="top">
  <div class="row1">
    <div class="brand">✦ Spell Compendium <span class="tot">{len(spells)} spells · {n_wiz} wizard · {n_pri} priest</span></div>
    <input id="q" type="text" placeholder="Search spells by name or effect…" autocomplete="off">
    <span id="count" class="count"></span>
  </div>
  <div class="row2">
    <div class="seg" id="caster">
      <button data-k="all" class="on">All</button>
      <button data-k="wizard">Wizard</button>
      <button data-k="priest">Priest</button>
    </div>
    <div class="grp" id="levels"><span class="lbl">Level</span>
      <button class="pill lvl on" data-k="all">All</button>{level_pills}</div>
  </div>
  <!-- One context category row is shown at a time, chosen by the caster toggle. -->
  <div class="row2" id="catwrap">
    <div class="grp cat" id="cat-school"><span class="lbl">School</span>{_cat_pills(SCHOOL_ORDER, with_dots=True)}</div>
    <div class="grp cat" id="cat-spec" hidden><span class="lbl">Specialization</span>{_cat_pills(SPEC_ORDER)}</div>
    <div class="grp cat" id="cat-sphere" hidden><span class="lbl">Sphere</span>{_cat_pills(SPHERE_ORDER)}</div>
  </div>
</div>
<div id="wrap"><div id="grid">{cards}</div>
  <div id="empty">No spells match those filters.</div>
</div>
<script>{_JS}</script>
</body></html>"""


_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #14151d; color: #c8cad8; font-family: "Segoe UI", system-ui, sans-serif; font-size: 12px; }
a { color: inherit; }

/* Vertical row spacing uses margins, not flex `gap`, which this webengine drops. */
.top { position: sticky; top: 0; z-index: 50; background: #101119; border-bottom: 1px solid #262a3d;
       padding: 11px 16px; display: flex; flex-direction: column; }
.row1 > * + * { margin-left: 14px; }
.row1 { display: flex; align-items: center; margin-bottom: 14px; }
.brand { font-size: 15px; font-weight: 800; color: #c9a84c; letter-spacing: .02em; white-space: nowrap; }
.brand .tot { font-size: 11px; font-weight: 600; color: #5a6080; margin-left: 8px; letter-spacing: .04em; }
#q { flex: 1; min-width: 160px; background: #21243a; border: 1px solid #383c52; border-radius: 7px;
     color: #e6e9f6; padding: 8px 13px; font-size: 13px; outline: none; }
#q:focus { border-color: #c9a84c; }
.count { font-size: 11px; color: #8891b5; font-weight: 700; white-space: nowrap; min-width: 66px; text-align: right; }

.row2 > * { margin: 0 16px 16px 0; }
.row2 { display: flex; align-items: center; flex-wrap: wrap; margin-bottom: 9px; }
.row2:last-child { margin-bottom: 0; }
.seg { display: inline-flex; background: #21243a; border: 1px solid #383c52; border-radius: 8px; overflow: hidden; }
.seg button { background: transparent; border: 0; color: #aeb4d0; padding: 6px 15px; font-size: 12px;
              font-weight: 700; cursor: pointer; letter-spacing: .03em; }
.seg button.on { background: #c9a84c; color: #17130a; }
.grp > * { margin: 0 5px 5px 0; }
.grp { display: flex; align-items: center; flex-wrap: wrap; }
.grp .lbl { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: #565c7d; margin-right: 3px; }
#catwrap { padding-top: 0; }
.cat[hidden] { display: none !important; }   /* beat .grp's display:flex */
.pill { background: #21243a; border: 1px solid #363a52; border-radius: 20px; color: #b8bcd4;
        padding: 4px 11px; font-size: 11px; font-weight: 700; cursor: pointer; display: inline-flex;
        align-items: center; transition: background .1s, border-color .1s; }
.pill .dot { margin-right: 6px; }  /* QtWebEngine drops flex gap */
.pill:hover { background: #2b2f47; }
.pill.on { background: #2f3350; border-color: #c9a84c; color: #f0e4c0; }
.pill .dot { width: 8px; height: 8px; border-radius: 50%; }
/* Level pills are single digits — keep them tight. Spacing via margin, not flex
   `gap` (this webengine renders gap far larger than specified). */
#levels { gap: 0; }
#levels .pill { padding: 4px 7px; margin: 0 2px; }

#wrap { padding: 16px; }
/* Uniform CSS grid (grid `gap` renders fine here; only flex `gap` is buggy).
   Cards share a fixed height so the grid reads cleanly; a description longer than
   fits is clamped with a "more" toggle that expands just that card. */
#grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
        gap: 14px; align-items: start; }
#empty { display: none; text-align: center; color: #5a6080; padding: 60px 0; font-size: 14px; }

.card { height: 402px; background: #1e2133;
        border: 1px solid #2b2f47; border-left: 3px solid var(--sc); border-radius: 10px;
        overflow: hidden; display: flex; flex-direction: column;
        scroll-margin-top: 92px; }   /* clear the sticky header when jumped to via #anchor */
.card.open { height: auto; }
.card.target { border-color: #c9a84c; box-shadow: 0 0 0 2px #c9a84c66; }
/* NB: QtWebEngine (Chromium 87) drops flexbox `gap` here, so the badge/text
   spacing is set with an explicit margin instead. */
.chead { display: flex; align-items: center; padding: 11px 13px 10px; }
.lvl { flex-shrink: 0; width: 32px; height: 32px; border-radius: 8px; background: var(--sc);
       color: #14151d; font-weight: 800; font-size: 15px; line-height: 1; margin-right: 13px;
       display: flex; align-items: center; justify-content: center; }
.ctitle { min-width: 0; }
.nm { font-size: 14.5px; font-weight: 700; color: #f0f1fa; line-height: 1.25; }
.meta { font-size: 10.5px; color: #7e85a8; margin-top: 4px; text-transform: uppercase;
        letter-spacing: .05em; font-weight: 700; display: flex; align-items: center; }
.comp { display: inline-flex; margin-left: 8px; }
.comp i { font-style: normal; background: #2b2f47; color: #aeb4d0; border-radius: 3px;
          padding: 1px 5px; font-size: 9.5px; font-weight: 800; letter-spacing: .04em; margin-left: 3px; }
.comp i:first-child { margin-left: 0; }

.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #2a2e45;
         border-top: 1px solid #2a2e45; border-bottom: 1px solid #2a2e45; }
.st > * + * { margin-top: 1px; }
.st { background: #191c2c; padding: 6px 13px; display: flex; flex-direction: column; }
.st span { font-size: 9px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; color: #616784; }
.st b { font-size: 11.5px; font-weight: 600; color: #d6d9ec; }

.mat { padding: 8px 13px 0; font-size: 11px; color: #9aa0c0; line-height: 1.45; }
.mat span { font-weight: 800; text-transform: uppercase; font-size: 9px; letter-spacing: .08em; color: #616784; }
.desc { padding: 8px 13px 4px; font-size: 12px; line-height: 1.5; color: #b9bdd4;
        flex: 1; min-height: 0; overflow: hidden; position: relative; }
.card.open .desc { flex: none; }
.desc::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 34px;
               background: linear-gradient(transparent, #1e2133); pointer-events: none; }
.card.open .desc::after, .card.short .desc::after { display: none; }
.more { align-self: flex-start; margin: 0 13px 8px; background: none; border: 0; color: #c9a84c;
        font-size: 11px; font-weight: 700; cursor: pointer; padding: 3px 0; }
.more::after { content: " ▾"; }
.card.short .more { display: none; }
.card.open .more::after { content: " ▴"; }

.foot > * + * { margin-left: 10px; }  /* QtWebEngine drops flex gap */
.foot { padding: 8px 13px; border-top: 1px solid #262a3d; display: flex;
        justify-content: space-between; font-size: 10px; color: #5f6688; }
.foot .res { color: #7e6f4a; font-weight: 700; }
.foot .src { color: #565c7d; text-align: right; }
"""

_JS = """
const grid = document.getElementById('grid');
const cards = Array.from(grid.children);
const countEl = document.getElementById('count');
const emptyEl = document.getElementById('empty');
// The category dimension depends on the caster: All→school, Wizard→specialization,
// Priest→sphere. `cat` holds the current selection within whichever is active.
const f = { caster: 'all', level: 'all', cat: 'all', q: '' };
const CAT_ROW = { all: 'cat-school', wizard: 'cat-spec', priest: 'cat-sphere' };

// Cards are a fixed height; mark those whose description doesn't overflow so their
// "more" button and fade are hidden. Measured on visible, un-expanded cards (a
// hidden card has no height to measure).
function markShort() {
  for (const c of cards) {
    if (c.style.display === 'none' || c.classList.contains('open')) continue;
    const d = c.querySelector('.desc');
    if (d) c.classList.toggle('short', d.scrollHeight <= d.clientHeight + 2);
  }
}

function catOk(c) {
  if (f.cat === 'all') return true;
  if (f.caster === 'wizard') return (c.dataset.specs || '').includes('|' + f.cat + '|');
  if (f.caster === 'priest') return (c.dataset.spheres || '').includes('|' + f.cat + '|');
  return c.dataset.school === f.cat;   // caster 'all' → school
}
function matches(c) {
  if (f.caster !== 'all' && c.dataset.caster !== f.caster) return false;
  if (f.level !== 'all' && c.dataset.level !== f.level) return false;
  if (!catOk(c)) return false;
  if (f.q && !c.textContent.toLowerCase().includes(f.q)) return false;
  return true;
}
function apply() {
  let n = 0;
  for (const c of cards) { const v = matches(c); c.style.display = v ? '' : 'none'; if (v) n++; }
  countEl.textContent = n + (n === 1 ? ' spell' : ' spells');
  emptyEl.style.display = n ? 'none' : 'block';
  markShort();   // the CSS grid handles reflow itself; we only re-measure clamps
}

document.getElementById('q').addEventListener('input', e => { f.q = e.target.value.toLowerCase().trim(); apply(); });

// Simple pill groups (caster, level) set a field directly.
function wireGroup(id, key, after) {
  document.getElementById(id).addEventListener('click', e => {
    const btn = e.target.closest('button'); if (!btn) return;
    f[key] = btn.dataset.k;
    for (const b of document.getElementById(id).querySelectorAll('button')) b.classList.toggle('on', b === btn);
    if (after) after();
    apply();
  });
}
wireGroup('levels', 'level');
wireGroup('caster', 'caster', () => {
  // Switching caster resets the category and swaps in that caster's category row.
  f.cat = 'all';
  for (const row of document.querySelectorAll('#catwrap .cat')) row.hidden = (row.id !== CAT_ROW[f.caster]);
  const active = document.getElementById(CAT_ROW[f.caster]);
  for (const b of active.querySelectorAll('button')) b.classList.toggle('on', b.dataset.k === 'all');
});
// Category rows all feed the single `cat` field (only one row is visible at a time).
document.getElementById('catwrap').addEventListener('click', e => {
  const btn = e.target.closest('button'); if (!btn) return;
  f.cat = btn.dataset.k;
  for (const b of btn.closest('.cat').querySelectorAll('button')) b.classList.toggle('on', b === btn);
  apply();
});

grid.addEventListener('click', e => {
  const btn = e.target.closest('.more'); if (!btn) return;
  btn.closest('.card').classList.toggle('open');   // grid grows this card's row
});

// A dnd:///spell/<slug> link from a monster sheet lands here as #spell-<slug>.
// QtWebEngine's native anchor scroll fires before the grid finishes laying out, so
// jump explicitly once it's settled — expand the card and highlight it too.
function jumpToHash() {
  if (!location.hash) return;
  const el = document.getElementById(location.hash.slice(1));
  if (!el) return;
  el.classList.add('open', 'target');
  el.scrollIntoView({ block: 'start' });
}
window.addEventListener('hashchange', jumpToHash);

// Column width changes on resize → re-measure which descriptions overflow.
window.addEventListener('resize', markShort);
window.addEventListener('load', () => { apply(); [30, 200, 500].forEach(ms => setTimeout(jumpToHash, ms)); });
apply();
[150, 500].forEach(ms => setTimeout(markShort, ms));   // catch late webview sizing
"""

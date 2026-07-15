"""monster_html.py — the DM monster sheet view (pure string templating, Qt-free).

Renders a Monster as an editable stat block for the DM: the campaign house-rule
numbers up front (attack bonus, ascending AC, initiative speed factor, all from
char_rules via the Monster model), the full MM stat block as editable fields, and
the prose — with **Combat shown as first-class functional text**, because ~30% of
MM `special_attacks` fields are just "See below" and the mechanics live in Combat
(see docs/monster-mode-plan.md).

Matches the builder's look (dark navy + gold) and its interaction convention: edits
and actions navigate to ``dnd:///mon/…`` links, which app.py intercepts (phase 4) —
mirroring the ``cm(…)`` / ``cmText(…)`` helpers in charactermancer_html. This module
only builds the HTML; the round-trip wiring is the Qt layer's job.
"""
import re
from html import escape as esc

import char_rules as cr

ACCENT = "#c9a84c"

#: (display label, Monster field) for the 21 stat-block rows, in MM order.
_STAT_ROWS = [
    ("Climate/Terrain", "climate_terrain"),
    ("Frequency", "frequency"),
    ("Organization", "organization"),
    ("Activity Cycle", "activity_cycle"),
    ("Diet", "diet"),
    ("Intelligence", "intelligence"),
    ("Treasure", "treasure"),
    ("Alignment", "alignment"),
    ("No. Appearing", "no_appearing"),
    ("Armor Class", "armor_class"),
    ("Movement", "movement"),
    ("Hit Dice", "hit_dice"),
    ("THAC0", "thac0"),
    ("No. of Attacks", "no_of_attacks"),
    ("Damage/Attack", "damage_attack"),
    ("Special Attacks", "special_attacks"),
    ("Special Defenses", "special_defenses"),
    ("Magic Resistance", "magic_resistance"),
    ("Size", "size"),
    ("Morale", "morale"),
    ("XP Value", "xp_value"),
]

_RANGE = re.compile(r"(\d+)\s*-\s*(\d+)")


def _to_dice(text: str) -> str:
    """Render AD&D damage ranges as dice: '3-18 (crush)+1-4 (acid)' ->
    '3d6 (crush)+d4 (acid)'. A range a-b becomes ``a`` dice of d(b/a) when that
    divides evenly (min a, max b); a single die drops the count (d6, not 1d6).
    Anything that doesn't divide cleanly is left as the original range."""
    def repl(m):
        a, b = int(m.group(1)), int(m.group(2))
        if a >= 1 and b > a and b % a == 0 and (b // a) >= 2:
            die = b // a
            return f"{a}d{die}" if a > 1 else f"d{die}"
        return m.group(0)
    return _RANGE.sub(repl, text or "")


def _init_label(m) -> str:
    n = m.initiative_modifier()
    return "—" if n is None else (f"+{n}" if n > 0 else str(n))


#: Fields the campaign shows in house-rule form only (not the raw MM value):
#: (display label, value function). AC -> ascending, THAC0 -> attack bonus,
#: damage -> dice. The stat field still edits via set/<field>; the phase-4 handler
#: applies the inverse for armor_class/thac0 (both are 20−x involutions).
_HOUSE_RULE_FIELDS = {
    "armor_class": ("Armor Class", lambda m: m.ascending_ac()),
    "thac0": ("Attack Bonus", lambda m: m.attack_bonus()),
    "damage_attack": ("Damage/Attack", lambda m: _to_dice(m.damage_attack)),
}


def _stat_field(label, field, value, derived=""):
    hint = f'<span class="derived">{esc(derived)}</span>' if derived else ""
    return (
        f'<div class="stat">'
        f'<label>{esc(label)}</label>'
        f'<input class="sv" value="{esc(value)}" spellcheck="false" autocomplete="off" '
        f'onchange="monText(\'set/{field}\', this.value)">'
        f'{hint}</div>'
    )


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-l">{esc(label)}</div>'
            f'<div class="tile-v">{esc(value or "—")}</div></div>')


def _prose_panel(title, field, text, feature=False):
    cls = "panel feature" if feature else "panel"
    return (
        f'<div class="{cls}">'
        f'<div class="panel-h">{esc(title)}</div>'
        f'<textarea class="pr" spellcheck="false" '
        f'onchange="monText(\'set/{field}\', this.value)" '
        f'placeholder="—">{esc(text)}</textarea>'
        f'</div>'
    )


def generate(m, saved_id=None) -> str:
    """The full monster sheet HTML for Monster ``m``. ``saved_id`` (if the monster
    is saved) tunes the Save button label."""
    variant_tag = f'<span class="tag">{esc(m.variant)}</span>' if m.variant else ""
    source = (f'<a class="src" href="dnd:///{esc(m.source_page)}">Monstrous Manual ↗</a>'
              if m.source_page else "")

    rows = ""
    for label, field in _STAT_ROWS:
        if field in _HOUSE_RULE_FIELDS:                 # AC/THAC0/damage: house-rule form only
            label, value_fn = _HOUSE_RULE_FIELDS[field]
            value = value_fn(m)
        else:
            value = getattr(m, field, "")
        derived = f"init {_init_label(m)}" if field == "size" and value else ""
        rows += _stat_field(label, field, value, derived)

    tiles = "".join([
        _tile("Attack Bonus", m.attack_bonus()),
        _tile("Armor Class", m.ascending_ac()),
        _tile("Initiative", _init_label(m)),
        _tile("Hit Dice", m.hit_dice),
        _tile("Attacks", m.no_of_attacks),
        _tile("Damage", _to_dice(m.damage_attack)),
    ])

    prose = (
        _prose_panel("Description", "description", m.description)
        + _prose_panel("Combat", "combat", m.combat, feature=True)
        + _prose_panel("Habitat / Society", "habitat_society", m.habitat_society)
        + _prose_panel("Ecology", "ecology", m.ecology)
    )

    save_label = "Save changes" if saved_id else "Save monster"

    body = f"""<div class="sheet">
  <header>
    <div class="title-row">
      <input class="name" value="{esc(m.name)}" placeholder="Monster name" spellcheck="false"
             autocomplete="off" onchange="monText('set/name', this.value)">
      {variant_tag}
    </div>
    <div class="sub">Ascending AC · attack bonus · size-based initiative — house rules applied. {source}</div>
  </header>

  <div class="combat-strip">{tiles}</div>

  <div class="grid">
    <section class="statblock">
      <div class="section-h">Stat Block</div>
      {rows}
    </section>
    <section class="prose-col">{prose}</section>
  </div>

  <div class="actions">
    <a class="btn" href="dnd:///mon/save">{save_label}</a>
    <a class="nav-btn" href="dnd:///mon/import">⇩ Import from Monstrous Manual</a>
    <a class="nav-btn" href="dnd:///mon/new">＋ New monster</a>
  </div>
</div>"""
    return _document(m.name or "Monster", body)


def generate_import_picker(families, standalone, saved=()) -> str:
    """The monster landing: saved monsters to reopen, and the Monstrous Manual to
    import from (client-side filtered). Families (Dragon, Golem, …) collapse to one
    entry that opens a sub-picker; ``standalone`` monsters import directly.
      families   = [(family, general_url|None, [(page_url, subtype), ...]), ...]
      standalone = [(page_url, name), ...]     saved = [(id, name, source_page), ...]"""
    saved_html = ""
    if saved:
        srows = "".join(
            f'<div class="srow">'
            f'<a class="pick-item load" href="dnd:///mon/load/{sid}">{esc(name or "Unnamed Monster")}</a>'
            f'<a class="del" href="dnd:///mon/delete/{sid}" title="Delete">✕</a></div>'
            for sid, name, _src in saved)
        saved_html = (f'<section class="picker-sec"><div class="section-h">Saved Monsters</div>'
                      f'<div class="pick-list">{srows}</div></section>')

    # families and standalone monsters merged into one alphabetical, searchable list
    entries = [(family.lower(),
                f'<a class="pick-item family" data-name="{esc(family.lower())}" '
                f'href="dnd:///mon/family/{esc(family)}">{esc(family)}'
                f'<span class="count">{len(members)}</span></a>')
               for family, _general, members in families]
    entries += [(name.lower(),
                 f'<a class="pick-item" data-name="{esc(name.lower())}" '
                 f'href="dnd:///mon/pick/{esc(url)}">{esc(name)}</a>')
                for url, name in standalone]
    entries.sort(key=lambda e: e[0])
    items = "".join(html for _key, html in entries)

    body = f"""<div class="sheet">
  <header><div class="title-row"><span class="page-title">Monsters</span></div>
    <div class="sub">Import a stat block from the Monstrous Manual — house rules applied automatically.</div>
  </header>
  {saved_html}
  <section class="picker-sec">
    <div class="section-h">Import from the Monstrous Manual</div>
    <input class="search" id="q" placeholder="Search {len(entries)} entries…" oninput="filt()" autocomplete="off">
    <div class="pick-list" id="mmlist">{items}</div>
  </section>
  <div class="actions"><a class="nav-btn" href="dnd:///mon/new">＋ New blank monster</a></div>
</div>"""
    script = """
  function filt() { var q = document.getElementById('q').value.toLowerCase();
    document.querySelectorAll('#mmlist .pick-item').forEach(function(el) {
      el.style.display = el.dataset.name.indexOf(q) >= 0 ? '' : 'none'; }); }"""
    return _document("Monsters", body, script)


def generate_family_picker(family, general_url, members) -> str:
    """A family sub-picker (Dragon → its types), with the '-- General' lore page — if
    any — linked at the top. ``members`` is [(page_url, subtype), ...]."""
    general = ""
    if general_url:
        general = (f'<a class="pick-item general" href="dnd:///{esc(general_url)}">'
                   f'📖 General information</a>')
    items = "".join(
        f'<a class="pick-item" href="dnd:///mon/pick/{esc(url)}">{esc(subtype)}</a>'
        for url, subtype in members)
    body = f"""<div class="sheet">
  <header><div class="title-row"><span class="page-title">{esc(family)}</span></div>
    <div class="sub">Choose a {esc(family.lower())} to import.</div>
  </header>
  <section class="picker-sec"><div class="pick-list">{general}{items}</div></section>
  <div class="actions"><a class="nav-btn" href="dnd:///mon/import">← Back to all monsters</a></div>
</div>"""
    return _document(family, body)


def generate_variant_picker(group, source_page, variant_names) -> str:
    """Pick one creature from a multi-variant MM page (Bear → Black/Brown/…)."""
    items = "".join(
        f'<a class="pick-item" href="dnd:///mon/pickvar/{esc(source_page)}/{i}">{esc(name)}</a>'
        for i, name in enumerate(variant_names))
    body = f"""<div class="sheet">
  <header><div class="title-row"><span class="page-title">{esc(group)}</span></div>
    <div class="sub">This entry covers several creatures — choose one to import.</div>
  </header>
  <section class="picker-sec"><div class="pick-list">{items}</div></section>
  <div class="actions"><a class="nav-btn" href="dnd:///mon/import">← Back to all monsters</a></div>
</div>"""
    return _document(group, body)


def _document(title, body, extra_script="") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>{_CSS}</style></head>
<body>
{body}
<script>
  function mon(path) {{ if (path.endsWith('/')) return; window.location.href = 'dnd:///mon/' + path; }}
  function monText(verb, v) {{ window.location.href = 'dnd:///mon/' + verb + '/' + encodeURIComponent(v); }}{extra_script}
</script>
</body></html>"""


_CSS = f"""
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #1a1c26; color: #c8cad8;
         font-family: "Segoe UI", system-ui, -apple-system, sans-serif; font-size: 13px; }}
  .sheet {{ max-width: 1000px; margin: 0 auto; padding: 22px 24px 40px; }}

  header {{ border-bottom: 1px solid #2a2e3e; padding-bottom: 14px; margin-bottom: 18px; }}
  .title-row {{ display: flex; align-items: center; }}
  .title-row > * + * {{ margin-left: 12px; }}   /* QtWebEngine drops flex gap */
  input.name {{ background: transparent; border: none; border-bottom: 1px dashed #3a3f58;
    color: #f0ead2; font-family: Georgia, "Times New Roman", serif; font-size: 27px;
    font-weight: 700; padding: 2px 2px 4px; flex: 1; min-width: 0; }}
  input.name:focus {{ outline: none; border-bottom-color: {ACCENT}; }}
  .tag {{ display: inline-block; background: {ACCENT}18; color: {ACCENT}; font-size: 10.5px;
    font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
    padding: 3px 9px; border-radius: 20px; border: 1px solid {ACCENT}44; }}
  .sub {{ color: #6a708c; font-size: 11.5px; margin-top: 8px; }}
  .src {{ color: {ACCENT}; text-decoration: none; margin-left: 6px; }}
  .src:hover {{ text-decoration: underline; }}

  .combat-strip {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 20px; }}
  .tile {{ display: flex; flex-direction: column; align-items: center; justify-content: center;
    background: #1e202c; border: 1px solid #2a2e3e; border-radius: 10px;
    padding: 11px 8px; text-align: center; min-height: 78px; }}
  .tile-l {{ font-size: 9.5px; letter-spacing: .09em; text-transform: uppercase;
    color: #6a708c; margin-bottom: 6px; }}
  .tile-v {{ font-size: 16px; font-weight: 800; color: #e6e9f6;
    font-variant-numeric: tabular-nums; line-height: 1.2; word-break: break-word; }}

  .grid {{ display: grid; grid-template-columns: minmax(280px, 360px) 1fr; gap: 20px; align-items: start; }}
  .section-h, .panel-h {{ font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: 10px; }}

  .statblock {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px; padding: 16px; }}
  .stat {{ display: grid; grid-template-columns: 120px 1fr auto; align-items: center;
    gap: 8px; padding: 3px 0; }}
  .stat label {{ font-size: 10.5px; letter-spacing: .04em; text-transform: uppercase; color: #8189a8; }}
  input.sv {{ background: #16181f; border: 1px solid #2f3346; border-radius: 6px;
    color: #e6e9f6; padding: 5px 8px; font-size: 12px; width: 100%; }}
  input.sv:focus {{ outline: none; border-color: {ACCENT}88; }}
  .derived {{ font-size: 10px; color: {ACCENT}; background: {ACCENT}16; border: 1px solid {ACCENT}33;
    border-radius: 5px; padding: 2px 7px; white-space: nowrap; font-variant-numeric: tabular-nums; }}

  .prose-col {{ display: grid; gap: 14px; }}   /* grid gap works in Qt; flex gap doesn't */
  .panel {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px; padding: 14px 16px; }}
  .panel.feature {{ border-color: {ACCENT}55; background: {ACCENT}0d; }}
  .panel.feature .panel-h {{ color: {ACCENT}; }}
  textarea.pr {{ width: 100%; min-height: 66px; resize: vertical; background: #16181f;
    border: 1px solid #2f3346; border-radius: 7px; color: #d3d7e6; padding: 9px 11px;
    font-family: inherit; font-size: 12.5px; line-height: 1.62; }}
  .panel.feature textarea.pr {{ min-height: 120px; }}
  textarea.pr:focus {{ outline: none; border-color: {ACCENT}88; }}

  .actions {{ display: flex; flex-wrap: wrap; margin-top: 22px;
    border-top: 1px solid #2a2e3e; padding-top: 18px; }}
  .actions > * {{ margin: 0 10px 8px 0; }}   /* QtWebEngine drops flex gap */
  .btn {{ text-decoration: none; background: {ACCENT}; color: #1a1c26; font-weight: 800;
    border-radius: 8px; padding: 9px 18px; font-size: 12.5px; }}
  .nav-btn {{ text-decoration: none; background: #262a40; border: 1px solid #3a3f58;
    color: #e6e9f6; font-weight: 700; border-radius: 8px; padding: 9px 16px; font-size: 12.5px; }}
  .nav-btn:hover {{ border-color: {ACCENT}66; }}

  /* import / saved-monster picker */
  .page-title {{ font-family: Georgia, "Times New Roman", serif; font-size: 27px;
    font-weight: 700; color: #f0ead2; }}
  .picker-sec {{ margin-bottom: 22px; }}
  .search {{ width: 100%; background: #16181f; border: 1px solid #2f3346; border-radius: 8px;
    color: #e6e9f6; padding: 9px 12px; font-size: 13px; margin-bottom: 12px; }}
  .search:focus {{ outline: none; border-color: {ACCENT}88; }}
  .pick-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; }}
  .pick-item {{ display: block; text-decoration: none; background: #23263a; border: 1px solid #2f3346;
    border-radius: 8px; padding: 9px 13px; color: #e6e9f6; font-size: 12.5px; }}
  .pick-item:hover {{ border-color: {ACCENT}66; background: #262a40; }}
  .pick-item.family {{ font-weight: 700; }}
  .pick-item.family::after {{ content: "›"; float: right; color: {ACCENT}; font-weight: 700; }}
  .pick-item .count {{ float: right; margin-right: 8px; font-size: 10.5px; font-weight: 700;
    color: #6a708c; background: #16181f; border-radius: 10px; padding: 1px 8px; }}
  .pick-item.general {{ color: {ACCENT}; border-color: {ACCENT}44; background: {ACCENT}12; }}
  .srow {{ display: flex; align-items: center; background: #23263a; border: 1px solid #2f3346;
    border-radius: 8px; }}
  .srow .load {{ flex: 1; background: transparent; border: none; }}
  .srow:hover {{ border-color: {ACCENT}66; }}
  .del {{ text-decoration: none; color: #8189a8; padding: 8px 12px; }}
  .del:hover {{ color: #e7b0b4; }}

  @media (max-width: 720px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .combat-strip {{ grid-template-columns: repeat(3, 1fr); }}
  }}
"""

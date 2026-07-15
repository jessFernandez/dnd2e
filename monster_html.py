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

#: field -> the house-rule value shown beside it (label, function(Monster) -> str)
_DERIVED = {
    "armor_class": ("ascending", lambda m: m.ascending_ac()),
    "thac0": ("attack bonus", lambda m: m.attack_bonus()),
    "size": ("init", lambda m: _init_label(m)),
}


def _init_label(m) -> str:
    n = m.initiative_modifier()
    return "—" if n is None else (f"+{n}" if n > 0 else str(n))


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
    return (f'<div class="tile"><div class="tile-v">{esc(value or "—")}</div>'
            f'<div class="tile-l">{esc(label)}</div></div>')


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
        value = getattr(m, field, "")
        derived = ""
        if field in _DERIVED and value:
            dlabel, dfn = _DERIVED[field]
            dval = dfn(m)
            if dval:
                derived = f"{dlabel} {dval}"
        rows += _stat_field(label, field, value, derived)

    tiles = "".join([
        _tile("Attack Bonus", m.attack_bonus()),
        _tile("Armor Class", m.ascending_ac()),
        _tile("Initiative", _init_label(m)),
        _tile("Hit Dice", m.hit_dice),
        _tile("Attacks", m.no_of_attacks),
        _tile("Damage", m.damage_attack),
    ])

    prose = (
        _prose_panel("Description", "description", m.description)
        + _prose_panel("Combat", "combat", m.combat, feature=True)
        + _prose_panel("Habitat / Society", "habitat_society", m.habitat_society)
        + _prose_panel("Ecology", "ecology", m.ecology)
    )

    save_label = "Save changes" if saved_id else "Save monster"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{esc(m.name or "Monster")}</title>
<style>{_CSS}</style></head>
<body>
<div class="sheet">
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
</div>
<script>
  function mon(path) {{ if (path.endsWith('/')) return; window.location.href = 'dnd:///mon/' + path; }}
  function monText(verb, v) {{ window.location.href = 'dnd:///mon/' + verb + '/' + encodeURIComponent(v); }}
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
  .tile {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 10px;
    padding: 12px 8px; text-align: center; }}
  .tile-v {{ font-size: 18px; font-weight: 800; color: #e6e9f6;
    font-variant-numeric: tabular-nums; line-height: 1.1; }}
  .tile-l {{ font-size: 9.5px; letter-spacing: .09em; text-transform: uppercase;
    color: #6a708c; margin-top: 5px; }}

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

  @media (max-width: 720px) {{
    .grid {{ grid-template-columns: 1fr; }}
    .combat-strip {{ grid-template-columns: repeat(3, 1fr); }}
  }}
"""

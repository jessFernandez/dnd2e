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
from view_common import esc

import monster
import monster_abilities
import monster_spells
import monster_tiers

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

def _to_dice(text: str) -> str:
    """The sheet's damage notation — monster.damage_to_dice in its terse display form
    ('d6', not '1d6'). The conversion itself lives on the model so the Roll20 export
    can't disagree with what the sheet shows."""
    return monster.damage_to_dice(text, terse=True)


def _init_label(m) -> str:
    n = m.initiative_modifier()
    return "—" if n is None else (f"+{n}" if n > 0 else str(n))


#: Fields the campaign shows in house-rule form only (not the raw MM value):
#: (display label, value function). AC -> ascending, THAC0 -> attack bonus,
#: damage -> dice. The stat field still edits via set/<field>; the phase-4 handler
#: applies the inverse for armor_class/thac0 (both are 20−x involutions).
#:
#: Only while the conversion round-trips, though: a THAC0 the MM wrote as a range or
#: an HD-conditional list has no single attack bonus, so writing one back would erase
#: it (monster.house_rule_round_trips). Those rows fall back to the raw MM text,
#: read-only, with the derived bonus as a badge beside it.
_HOUSE_RULE_FIELDS = {
    "armor_class": ("Armor Class", lambda m: m.ascending_ac()),
    "thac0": ("Attack Bonus", lambda m: m.attack_bonus()),
    "damage_attack": ("Damage/Attack", lambda m: _to_dice(m.damage_attack)),
}


def _bonus_badge(bonus: str) -> str:
    """The derived attack bonus, for the badge beside a raw THAC0 row."""
    if not bonus:
        return ""
    return f"Atk {bonus}" if bonus.startswith("-") else f"Atk +{bonus}"


def _stat_field(label, field, value, derived="", editable=True, control=""):
    hint = f'<span class="derived">{esc(derived)}</span>' if derived else ""
    # A tiered view is read-only: edits must land on the base stat block, so the DM
    # switches back to "Base" to change values (the tier selector, below).
    edit = (f'spellcheck="false" autocomplete="off" '
            f'onchange="monText(\'set/{field}\', this.value)"') if editable else "readonly"
    return (
        f'<div class="stat">'
        f'<label>{esc(label)}</label>'
        f'<input class="sv" value="{esc(value)}" {edit}>'
        f'{hint}{control}</div>'
    )


def _init_control(m, editable=True) -> str:
    """An editable initiative speed factor beside the Size row — the size-derived
    value, overridable (blank to fall back to size). Sets Monster.initiative_override
    via the mon/init action; the combat-strip Initiative tile follows on re-render."""
    n = m.initiative_modifier()
    val = "" if n is None else str(n)
    edit = ('onchange="monText(\'init\', this.value)"' if editable else "readonly")
    return (f'<input class="init-ov" value="{esc(val)}" placeholder="init" '
            f'title="Initiative speed factor — overrides the size-derived value" '
            f'autocomplete="off" {edit}>')


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-l">{esc(label)}</div>'
            f'<div class="tile-v">{esc(value or "—")}</div></div>')


def _chips_row(abilities, saves) -> str:
    """A scannable index of the ability types and saving throws the Combat prose
    mentions (monster_abilities). Ability chips are neutral; save chips accented.
    Empty markup when nothing was surfaced."""
    if not abilities and not saves:
        return ""
    pills = "".join(f'<span class="chip">{esc(c)}</span>' for c in abilities)
    pills += "".join(f'<span class="chip save">{esc(c)}</span>' for c in saves)
    return f'<div class="chips">{pills}</div>'


def _prose_panel(title, field, text, feature=False, chips_html=""):
    cls = "panel feature" if feature else "panel"
    return (
        f'<div class="{cls}">'
        f'<div class="panel-h">{esc(title)}</div>'
        f'{chips_html}'
        f'<textarea class="pr" spellcheck="false" '
        f'onchange="monText(\'set/{field}\', this.value)" '
        f'placeholder="—">{esc(text)}</textarea>'
        f'</div>'
    )


#: Friendly heading per classified table kind (monster_parser.classify_tables).
_TABLE_TITLES = {
    "age": "Age Progression",
    "psionics": "Psionics",
    "attack_damage": "Attack Damage",
    "other": "Reference Table",
}


def _extra_table_panel(t) -> str:
    """One captured enrichment table (dragon age chart, psionics, per-attack damage,
    …) as a read-only panel. The first ``header_rows`` rows render as <th>."""
    rows = t.get("rows") or []
    header_rows = t.get("header_rows", 1)
    title = _TABLE_TITLES.get(t.get("kind"), "Reference Table")
    trs = ""
    for i, row in enumerate(rows):
        tag = "th" if i < header_rows else "td"
        trs += "<tr>" + "".join(f"<{tag}>{esc(c)}</{tag}>" for c in row) + "</tr>"
    return (f'<div class="panel xtab" data-kind="{esc(t.get("kind", ""))}">'
            f'<div class="panel-h">{esc(title)}</div>'
            f'<div class="xtab-scroll"><table>{trs}</table></div></div>')


def _related_section(related) -> str:
    """Creatures the MM page describes in prose only — no stat column of their own
    (Phase C): the Archlich on the Lich page, the Kapoacinth on the Gargoyle page.
    Shown verbatim so the DM has them without the parser inventing stats."""
    if not related:
        return ""
    rows = "".join(
        f'<div class="rel-row"><div class="rel-name">{esc(r.get("name", ""))}</div>'
        f'<div class="rel-text">{esc(r.get("text", ""))}</div></div>'
        for r in related)
    return (f'<section class="related">'
            f'<div class="section-h">Also Described on This Page</div>{rows}</section>')


def _extra_tables_section(tables) -> str:
    """The enrichment tables the MM page carried past the stat block, each as its own
    panel below the sheet. Empty (no markup) when the page has none."""
    if not tables:
        return ""
    panels = "".join(_extra_table_panel(t) for t in tables)
    return (f'<section class="extras">'
            f'<div class="section-h">Additional Tables</div>{panels}</section>')


def _abilities_block(abils) -> str:
    """The Special Abilities block at the foot of the stat block (Phase C): a row per
    ability whose mechanics the Combat prose pins down — the ability name, its
    extracted facts as chips (damage/range/frequency neutral, save accented), and the
    source sentence beneath so the parse sits next to the author's own words. Empty
    markup when there's none."""
    if not abils:
        return ""
    rows = ""
    for a in abils:
        chips = "".join(f'<span class="chip">{esc(x)}</span>'
                        for x in (a.damage, a.range, a.frequency) if x)
        if a.save:
            chips += f'<span class="chip save">{esc(a.save)}</span>'
        rows += (f'<div class="abil-row">'
                 f'<div class="abil-head"><span class="abil-name">{esc(a.name)}</span>{chips}</div>'
                 f'<div class="abil-text">{esc(a.text)}</div></div>')
    return f'<div class="sb-extra"><div class="sb-h">Special Abilities</div>{rows}</div>'


def _spells_block(spell_links) -> str:
    """Spell-like abilities the monster names, as chips linking into the Spell
    Compendium (Phase D), at the foot of the stat block. Each ``dnd:///spell/<slug>``
    opens the compendium scrolled to that spell. Empty markup when none were matched."""
    if not spell_links:
        return ""
    chips = "".join(f'<a class="chip spell" href="dnd:///spell/{esc(slug)}">{esc(name)}</a>'
                    for name, slug in spell_links)
    return (f'<div class="sb-extra"><div class="sb-h">Spell-like Abilities</div>'
            f'<div class="chips">{chips}</div></div>')


def _tier_selector(ts, active) -> str:
    """The HD/age scaling selector (Phase B): a dropdown of "Base" + each tier, whose
    change navigates dnd:///mon/tier/<i> (or /base). ``active`` is the selected index
    or None. Empty markup when the monster doesn't scale."""
    if not ts:
        return ""
    opts = [f'<option value="base"{"" if active is not None else " selected"}>'
            f'Base (as written)</option>']
    opts += [f'<option value="{i}"{" selected" if active == i else ""}>{esc(t.label)}</option>'
             for i, t in enumerate(ts)]
    note = ("" if active is None else
            f'<span class="tiernote">Scaled to {esc(ts[active].label)} — switch to '
            f'Base to edit values</span>')
    return (f'<div class="tierbar">'
            f'<label class="tierlab">Scaling</label>'
            f'<select class="tiersel" onchange="monText(\'tier\', this.value)">'
            f'{"".join(opts)}</select>{note}</div>')


def generate(m, saved_id=None, image_url="", spell_index=None) -> str:
    """The full monster sheet HTML for Monster ``m``. ``saved_id`` (if the monster is
    saved) tunes the Save button label; ``image_url`` (the app builds it from the
    source site) shows the MM illustration; ``spell_index`` (a monster_spells index
    the app builds from the compendium) links named spell-like abilities.

    Monsters that scale by HD or dragon age (monster_tiers) get a tier selector; the
    combat strip and stat block render for the selected tier (the base stat block
    when none is selected), read-only while a tier is active."""
    # imported monsters: the name itself opens the MM page; custom ones stay editable
    if m.source_page:
        name_el = (f'<a class="namelink" href="dnd:///{esc(m.source_page)}" '
                   f'title="Open in the Monstrous Manual">{esc(m.name) or "Monster"}'
                   f'<span class="ext"> ↗</span></a>')
    else:
        name_el = (f'<input class="name" value="{esc(m.name)}" placeholder="Monster name" '
                   f'spellcheck="false" autocomplete="off" onchange="monText(\'set/name\', this.value)">')
    image = (f'<img class="mon-img" src="{esc(image_url)}" alt="" '
             f'onerror="this.style.display=\'none\'">') if image_url else ""

    # the scaling selector, and the monster scaled to its chosen tier (view). The
    # base stat block stays editable; a tiered view is a read-only preview.
    ts = monster_tiers.tiers(m)
    active = monster_tiers.active_index(m)
    view = monster_tiers.active_monster(m)
    editable = active is None

    rows = ""
    for label, field in _STAT_ROWS:
        value = getattr(view, field, "")
        derived, row_editable = "", editable
        if field in _HOUSE_RULE_FIELDS:                 # AC/THAC0/damage: house-rule form
            hr_label, value_fn = _HOUSE_RULE_FIELDS[field]
            if monster.house_rule_round_trips(field, value):
                label, value = hr_label, value_fn(view)
            else:      # e.g. an HD-conditional THAC0: keep the MM's own text intact
                derived, row_editable = _bonus_badge(value_fn(view)), False
        # the Size row carries an editable initiative speed factor (overrides the
        # size-derived value); the override lives on the base monster, so use m.
        control = _init_control(m, editable) if field == "size" else ""
        rows += _stat_field(label, field, value, derived=derived,
                            editable=row_editable, control=control)

    tile_specs = [
        ("Attack Bonus", view.attack_bonus()),
        ("Armor Class", view.ascending_ac()),
        ("Initiative", _init_label(view)),
        ("Hit Dice", view.hit_dice),
        ("Attacks", view.no_of_attacks),
        ("Damage", _to_dice(view.damage_attack)),
    ]
    if view.breath_weapon:                              # a dragon age tier's breath (Phase B)
        tile_specs.append(("Breath", _to_dice(view.breath_weapon)))
    tiles = "".join(_tile(label, value) for label, value in tile_specs)

    # Combat ability/save chips index the verbatim prose (Phase C); abilities don't
    # change with the selected tier, so read them from the base monster.
    combat_chips = _chips_row(monster_abilities.ability_types(m),
                              monster_abilities.saving_throws(m))
    # An imported monster shows only the prose sections its MM page actually has, so
    # empty panels don't clutter the sheet (a one-paragraph creature is all
    # Description). A custom monster (no source page) keeps every panel to fill in.
    custom = not m.source_page
    panels = [("Description", "description", m.description, False, ""),
              ("Combat", "combat", m.combat, True, combat_chips),
              ("Habitat / Society", "habitat_society", m.habitat_society, False, ""),
              ("Ecology", "ecology", m.ecology, False, "")]
    prose = "".join(
        _prose_panel(title, field, text, feature=feat, chips_html=chips)
        for title, field, text, feat, chips in panels
        if custom or text.strip())

    save_label = "Save changes" if saved_id else "Save monster"

    body = f"""<div class="sheet">
  <header>
    <div class="title-row">{name_el}</div>
  </header>

  {_tier_selector(ts, active)}
  <div class="combat-strip">{tiles}</div>

  <div class="grid">
    <section class="statblock">
      {image}
      <div class="section-h">Stat Block</div>
      {rows}
      {_abilities_block(monster_abilities.abilities(m))}
      {_spells_block(monster_spells.find_in(m, spell_index))}
    </section>
    <section class="prose-col">{prose}</section>
  </div>

  {_related_section(m.related_creatures)}

  {_extra_tables_section(m.extra_tables)}

  <div class="actions">
    <a class="btn" href="dnd:///mon/save">{save_label}</a>
    <a class="nav-btn" href="dnd:///mon/roll20">⤴ Export to Roll20</a>
    <a class="nav-btn" href="dnd:///mon/import">⇩ Import from Monstrous Manual</a>
    <a class="nav-btn" href="dnd:///mon/new">＋ New monster</a>
  </div>"""
    return _document(m.name or "Monster", body, _AUTOGROW_JS)


#: Auto-size every prose box to its content, so the full text shows without scrolling.
#: Runs immediately and again on `load` — the first pass can mis-measure before the
#: textarea has its final width/fonts, which left long boxes (e.g. a Brown Dragon's
#: Habitat/Society) too short.
_AUTOGROW_JS = """
  function _fit(t) { t.style.height = 'auto'; t.style.height = (t.scrollHeight + 2) + 'px'; }
  function _fitAll() { document.querySelectorAll('textarea.pr').forEach(_fit); }
  _fitAll();
  window.addEventListener('load', _fitAll);
  document.querySelectorAll('textarea.pr').forEach(function(t) {
    t.addEventListener('input', function() { _fit(t); });
  });"""


def _count_badge(n) -> str:
    """A right-aligned count for entries that open a sub-list (a family, or a page
    holding several creatures). Nothing for a single creature."""
    return f'<span class="count">{n}</span>' if n and n > 1 else ""


def _subcategorize(entries, sep):
    """Split (name, href, count) entries into (loose, sections). An entry's
    subcategory is the text before the first ``sep`` ('Chromatic: Black Dragon' ->
    'Chromatic'; 'Eel, Giant' -> 'Eel'); a subcategory shared by ≥2 entries becomes a
    section, its items shown by the text after ``sep``. Everything else stays loose
    under its full name."""
    buckets = {}
    for name, href, count in entries:
        if sep in name:
            sub, _, rest = name.partition(sep)
            buckets.setdefault(sub.strip(), []).append((rest.strip(), name, href, count))
        else:
            buckets.setdefault(None, []).append((name, name, href, count))
    loose, sections = [], []
    for sub, items in buckets.items():
        if sub and len(items) >= 2:
            sections.append((sub, sorted([(disp, href, c) for disp, _f, href, c in items],
                                         key=lambda x: x[0].lower())))
        else:
            loose += [(full, href, c) for _d, full, href, c in items]
    loose.sort(key=lambda x: x[0].lower())
    sections.sort(key=lambda s: s[0].lower())
    return loose, sections


def _pick_link(display, href, count) -> str:
    return (f'<a class="pick-item" data-name="{esc(display.lower())}" '
            f'href="{esc(href)}">{esc(display)}{_count_badge(count)}</a>')


def _grouped_list(loose, sections) -> str:
    """A pick-list of loose items followed by a labelled sub-group per section."""
    html = '<div class="pick-list">' + "".join(_pick_link(d, h, c) for d, h, c in loose) + '</div>'
    for sub, items in sections:
        inner = "".join(_pick_link(d, h, c) for d, h, c in items)
        html += (f'<div class="subcat"><div class="subcat-h">{esc(sub)}</div>'
                 f'<div class="pick-list">{inner}</div></div>')
    return html


def generate_import_picker(families, standalone, saved=()) -> str:
    """The monster landing: saved monsters to reopen, and the Monstrous Manual to
    import from (client-side filtered). Families (Dragon, Golem, …) collapse to one
    entry that opens a sub-picker; ``standalone`` monsters import directly.
      families   = [(family, general_url|None, [(page_url, subtype, count), ...]), ...]
      standalone = [(page_url, name, count), ...]  saved = [(id, name, source_page), ...]"""
    saved_html = ""
    if saved:
        srows = "".join(
            f'<div class="srow">'
            f'<a class="pick-item load" href="dnd:///mon/load/{sid}">{esc(name or "Unnamed Monster")}</a>'
            f'<a class="del" href="dnd:///mon/delete/{sid}" title="Delete">✕</a></div>'
            for sid, name, _src in saved)
        saved_html = (f'<section class="picker-sec"><div class="section-h">Saved Monsters</div>'
                      f'<div class="pick-list">{srows}</div></section>')

    # families and standalone monsters merged into one alphabetical, searchable list;
    # a count badge marks anything that opens a sub-list (a family, or a page holding
    # several creatures).
    entries = [(family.lower(),
                f'<a class="pick-item" data-name="{esc(family.lower())}" '
                f'href="dnd:///mon/family/{esc(family)}">{esc(family)}{_count_badge(len(members))}</a>')
               for family, _general, members in families]
    entries += [(name.lower(),
                 f'<a class="pick-item" data-name="{esc(name.lower())}" '
                 f'href="dnd:///mon/pick/{esc(url)}">{esc(name)}{_count_badge(count)}</a>')
                for url, name, count in standalone]
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
    any — linked at the top. ``members`` is [(page_url, subtype, count), ...]."""
    general = ""
    if general_url:
        general = (f'<div class="pick-list"><a class="pick-item general" '
                   f'href="dnd:///{esc(general_url)}">📖 General information</a></div>')
    loose, sections = _subcategorize(
        [(subtype, f"dnd:///mon/pick/{url}", count) for url, subtype, count in members], ":")
    body = f"""<div class="sheet">
  <header><div class="title-row"><span class="page-title">{esc(family)}</span></div>
    <div class="sub">Choose a {esc(family.lower())} to import.</div>
  </header>
  <section class="picker-sec">{general}{_grouped_list(loose, sections)}</section>
  <div class="actions"><a class="nav-btn" href="dnd:///mon/import">← Back to all monsters</a></div>
</div>"""
    return _document(family, body)


def generate_variant_picker(group, source_page, variant_names) -> str:
    """Pick one creature from a multi-variant MM page (Bear → Black/Brown/…). Creatures
    that share a comma-prefix (Fish → 'Eel, Electric'/'Eel, Giant') group under it."""
    loose, sections = _subcategorize(
        [(name, f"dnd:///mon/pickvar/{source_page}/{i}", 1)
         for i, name in enumerate(variant_names)], ",")
    body = f"""<div class="sheet">
  <header><div class="title-row"><span class="page-title">{esc(group)}</span></div>
    <div class="sub">This entry covers several creatures — choose one to import.</div>
  </header>
  <section class="picker-sec">{_grouped_list(loose, sections)}</section>
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
  a.namelink {{ font-family: Georgia, "Times New Roman", serif; font-size: 27px;
    font-weight: 700; color: #f0ead2; text-decoration: none; }}
  a.namelink:hover {{ color: {ACCENT}; }}
  a.namelink .ext {{ font-size: 15px; color: #6a708c; }}
  a.namelink:hover .ext {{ color: {ACCENT}; }}
  .mon-img {{ display: block; width: 100%; margin: 0 0 14px; border-radius: 8px;
    border: 1px solid #2a2e3e; background: #0f1016; }}

  /* HD / age scaling selector (Phase B) */
  .tierbar {{ display: flex; align-items: center; margin-bottom: 14px; }}
  .tierbar > * + * {{ margin-left: 10px; }}   /* QtWebEngine drops flex gap */
  .tierlab {{ font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase; color: {ACCENT}; }}
  .tiersel {{ background: #16181f; border: 1px solid {ACCENT}55; border-radius: 8px;
    color: #e6e9f6; padding: 7px 10px; font-size: 12.5px; font-family: inherit; }}
  .tiersel:focus {{ outline: none; border-color: {ACCENT}; }}
  .tiernote {{ font-size: 11px; color: {ACCENT}; }}

  /* Special Abilities + Spell-like blocks at the foot of the stat block (Phase C/D) */
  .sb-extra {{ margin-top: 14px; padding-top: 13px; border-top: 1px solid #2a2e3e; }}
  .sb-h {{ font-size: 10px; letter-spacing: .14em; text-transform: uppercase;
    color: {ACCENT}; margin-bottom: 9px; }}
  .abil-row {{ padding: 6px 0; border-bottom: 1px solid #24283a; }}
  .abil-row:last-child {{ border-bottom: none; }}
  .abil-head {{ display: flex; flex-wrap: wrap; align-items: center; margin-bottom: 3px; }}
  .abil-name {{ font-weight: 800; color: {ACCENT}; font-size: 12px; margin-right: 8px; }}
  .abil-text {{ font-size: 11.5px; color: #b7bcd0; line-height: 1.5; }}

  .combat-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
    gap: 10px; margin-bottom: 20px; }}
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
  input.init-ov {{ width: 46px; text-align: center; font-size: 11px; color: {ACCENT};
    background: {ACCENT}14; border: 1px solid {ACCENT}44; border-radius: 5px; padding: 3px 4px;
    font-variant-numeric: tabular-nums; }}
  input.init-ov:focus {{ outline: none; border-color: {ACCENT}; }}

  .prose-col {{ display: grid; gap: 14px; }}   /* grid gap works in Qt; flex gap doesn't */
  .panel {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px; padding: 14px 16px; }}
  .panel.feature {{ border-color: {ACCENT}55; background: {ACCENT}0d; }}
  .panel.feature .panel-h {{ color: {ACCENT}; }}

  /* ability / saving-throw chips indexing the Combat prose (Phase C) */
  .chips {{ display: flex; flex-wrap: wrap; margin: 0 0 10px -6px; }}   /* grid-less; child margins for Qt */
  .chip {{ display: inline-block; margin: 0 0 6px 6px; padding: 3px 9px; border-radius: 11px;
    font-size: 11px; font-weight: 600; background: #2a2e3e; border: 1px solid #3a3f58; color: #c8cad8; }}
  .chip.save {{ background: {ACCENT}18; border-color: {ACCENT}44; color: {ACCENT}; }}
  /* spell-like ability links into the compendium (Phase D) */
  a.chip.spell {{ text-decoration: none; background: #23263a; border-color: #3a3f58; color: #cdd3ec; }}
  a.chip.spell:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
  textarea.pr {{ width: 100%; min-height: 44px; overflow: hidden; resize: none;
    background: #16181f; border: 1px solid #2f3346; border-radius: 7px; color: #d3d7e6;
    padding: 9px 11px; font-family: inherit; font-size: 12.5px; line-height: 1.62; }}
  textarea.pr:focus {{ outline: none; border-color: {ACCENT}88; }}

  /* creatures described only in prose on the same MM page (Phase C) */
  .related {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px;
    padding: 12px 16px 6px; margin-bottom: 20px; }}
  .rel-row {{ padding: 8px 0; border-bottom: 1px solid #24283a; }}
  .rel-row:last-child {{ border-bottom: none; }}
  .rel-name {{ font-weight: 800; color: {ACCENT}; font-size: 12.5px; margin-bottom: 3px; }}
  .rel-text {{ font-size: 12px; color: #b7bcd0; line-height: 1.55; }}

  /* enrichment tables captured past the stat block (Phase A) */
  .extras {{ display: grid; gap: 14px; margin-top: 22px; }}  /* grid gap works in Qt */
  .panel.xtab {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px; padding: 14px 16px; }}
  .xtab-scroll {{ overflow-x: auto; }}
  .xtab table {{ border-collapse: collapse; width: 100%; font-size: 12px;
    font-variant-numeric: tabular-nums; }}
  .xtab th, .xtab td {{ text-align: left; padding: 5px 10px; border-bottom: 1px solid #2a2e3e;
    white-space: nowrap; }}
  .xtab th {{ color: {ACCENT}; font-weight: 700; font-size: 10.5px; letter-spacing: .04em;
    text-transform: uppercase; }}
  .xtab td {{ color: #d3d7e6; }}
  .xtab tr:last-child td {{ border-bottom: none; }}

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
  .pick-item .count {{ float: right; font-size: 10.5px; font-weight: 700; color: #8189a8;
    background: #16181f; border: 1px solid #2f3346; border-radius: 10px; padding: 0 8px; }}
  .pick-item.general {{ color: {ACCENT}; border-color: {ACCENT}44; background: {ACCENT}12; }}
  .subcat {{ margin-top: 16px; }}
  .subcat-h {{ font-size: 10px; letter-spacing: .13em; text-transform: uppercase;
    color: #8189a8; margin: 0 0 8px; border-left: 2px solid {ACCENT}66; padding-left: 8px; }}
  .srow {{ display: flex; align-items: center; background: #23263a; border: 1px solid #2f3346;
    border-radius: 8px; }}
  .srow .load {{ flex: 1; background: transparent; border: none; }}
  .srow:hover {{ border-color: {ACCENT}66; }}
  .del {{ text-decoration: none; color: #8189a8; padding: 8px 12px; }}
  .del:hover {{ color: #e7b0b4; }}

  @media (max-width: 720px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}
"""

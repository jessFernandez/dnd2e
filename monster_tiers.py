"""monster_tiers.py — HD / age scaling for a Monster (pure, Qt-free).

Phase B of the monster v2 plan (docs/monster-mode-plan.md). Many AD&D 2e monsters
scale by Hit Dice or dragon age category rather than carrying a single stat line;
this module turns that scaling into a list of **tiers** the sheet can select between,
recomputing the house-rule combat strip and stat block for the chosen one. Two
sources feed it, both already in the data:

  * **dragon age tables** — the ``age`` extra_tables the parser captures in Phase A
    (Age -> AC, breath, MR, treasure, XP; the Mummy's age chart adds HD/THAC0);
  * **HD-conditional strings** — THAC0/XP fields written as "5-6 HD: 15 7-8 HD: 13
    9-10 HD: 11" or "3+3 HD: 17 4+4 HD: 15" (and the Beholder's "45-49 hp: 11 …").

Each ``Tier`` is a label plus a dict of Monster-field overrides; ``apply_tier``
returns a copy of the Monster with them applied, so the existing char_rules
derivations (attack_bonus, ascending_ac, …) recompute for free. Like monster_parser,
this imports ``Monster`` — the model stays small and stable while the scaling logic
lives here. The Qt layer (app.py) stores the chosen index on ``Monster.selected_tier``
and re-renders; the view (monster_html) draws the selector.
"""
import re
from dataclasses import dataclass, fields, replace

from monster import Monster

_MONSTER_FIELDS = {f.name for f in fields(Monster)}

#: Fields whose value can be written as an "<HD spec> HD: <value>" conditional list.
#: THAC0 and XP are the two the MM actually varies this way; scanning both lets a
#: monster that scales one (or both) surface tiers.
_CONDITIONAL_FIELDS = ("thac0", "xp_value")

#: "<unit>: <value>" segments of a conditional field. The spec (the HD/hp range the
#: value applies at) is whatever precedes each match, back to the prior value.
_CONDITIONAL = re.compile(r"(HD|hp):\s*(-?\d[\d,]*)", re.IGNORECASE)


@dataclass
class Tier:
    """One selectable scaling step: a display ``label`` ("Age 12 (Great Wyrm)",
    "9-10 HD") and the Monster-field ``overrides`` it applies over the base stat
    block."""
    label: str
    overrides: dict


# ── HD-conditional strings ────────────────────────────────────────────────────

def _parse_conditional(text: str):
    """[(spec, unit, value)] for an "X HD: v  Y HD: v2" field, else []. The spec is
    the HD/hp range each value applies at ("5-6", "3+3", "1+1 and 2+2")."""
    out, prev_end = [], 0
    for m in _CONDITIONAL.finditer(text or ""):
        spec = text[prev_end:m.start()].strip()
        if spec:
            out.append((spec, m.group(1).upper(), m.group(2).strip()))
        prev_end = m.end()
    return out


def _conditional_tiers(m: Monster):
    """Tiers from a Monster's HD-conditional THAC0/XP fields. Keyed by HD spec so a
    monster that varies both (rare) aligns them; the spec also becomes the tier's
    Hit Dice. Only returned when there are ≥2 steps — a single "8 HD: 13" is just the
    base value, no choice to make."""
    per_field = {f: _parse_conditional(getattr(m, f)) for f in _CONDITIONAL_FIELDS}
    order, units, seen = [], {}, set()
    for parsed in per_field.values():
        for spec, unit, _val in parsed:
            if spec not in seen:
                seen.add(spec)
                order.append(spec)
                units[spec] = unit
    if len(order) < 2:
        return []
    tiers = []
    for spec in order:
        overrides = {}
        if units[spec] == "HD":                     # the HD spec is the tier's Hit Dice
            overrides["hit_dice"] = spec
        for field, parsed in per_field.items():
            for s, _unit, val in parsed:
                if s == spec:
                    overrides[field] = val
        tiers.append(Tier(label=f"{spec} {units[spec]}", overrides=overrides))
    return tiers


# ── dragon / mummy age tables ─────────────────────────────────────────────────

def _age_col_field(header: str):
    """The Monster field an age-table column maps to (or None). Matched against the
    column's combined header text — "AC", "Treas. Type", "XP Value", "THAC0", "HD"."""
    h = header.strip().lower()
    if h == "ac" or "armor" in h:
        return "armor_class"
    if "breath" in h:
        return "breath_weapon"
    if "thac0" in h or "thaco" in h:
        return "thac0"
    if h == "hd" or "hit dice" in h:
        return "hit_dice"
    if h == "mr" or "magic res" in h:
        return "magic_resistance"
    if "treas" in h:
        return "treasure"
    if "xp" in h or h == "value":
        return "xp_value"
    return None


def _age_label(cell: str) -> str:
    """A tier label from an age-table first cell: "1" -> "Age 1", "1 Hatchling" ->
    "Age 1 (Hatchling)", anything non-numeric left as-is."""
    parts = cell.split(None, 1)
    if parts and parts[0].isdigit():
        return f"Age {parts[0]}" + (f" ({parts[1]})" if len(parts) > 1 else "")
    return cell


def _age_tiers(table: dict):
    """Tiers from a captured ``age`` extra_table: one per data row, columns whose
    header names a Monster field applied as overrides."""
    rows = table.get("rows") or []
    hr = table.get("header_rows", 1)
    header_rows, data = rows[:hr], rows[hr:]
    if not header_rows or not data:
        return []
    width = max(len(r) for r in rows)
    combined = [" ".join(hrow[i] for hrow in header_rows if i < len(hrow)).strip()
                for i in range(width)]
    col_field = {i: f for i, h in enumerate(combined)
                 if (f := _age_col_field(h)) and i > 0}   # col 0 is the age label
    tiers = []
    for row in data:
        label = _age_label(row[0].strip()) if row else ""
        overrides = {col_field[i]: row[i].strip()
                     for i in col_field if i < len(row) and row[i].strip()}
        if label and overrides:
            tiers.append(Tier(label=label, overrides=overrides))
    return tiers


# ── public API ────────────────────────────────────────────────────────────────

def tiers(m: Monster):
    """The monster's selectable scaling tiers, or [] if it doesn't scale. A dragon /
    mummy age table wins when present (richer); otherwise HD-conditional THAC0/XP
    strings. The list is in the source's own order (youngest / fewest-HD first)."""
    for table in m.extra_tables or []:
        if table.get("kind") == "age":
            age = _age_tiers(table)
            if age:
                return age
    return _conditional_tiers(m)


def active_index(m: Monster):
    """The selected tier index if ``m.selected_tier`` is set and still in range for
    the current tier list, else None (meaning: show the base stat block as written)."""
    ts = tiers(m)
    i = m.selected_tier
    return i if isinstance(i, int) and 0 <= i < len(ts) else None


def apply_tier(m: Monster, tier: Tier) -> Monster:
    """A copy of ``m`` with ``tier``'s overrides applied (unknown field names, if any,
    ignored). Every house-rule derivation then recomputes for the chosen tier."""
    overrides = {k: v for k, v in tier.overrides.items() if k in _MONSTER_FIELDS}
    return replace(m, **overrides)


def active_monster(m: Monster) -> Monster:
    """``m`` scaled to its selected tier, or ``m`` unchanged when none is selected."""
    i = active_index(m)
    return apply_tier(m, tiers(m)[i]) if i is not None else m


def tiered_fields(m: Monster) -> frozenset:
    """The Monster fields the *active* tier overrides — the ones the sheet is showing
    scaled rather than as stored. An edit to one of those would write the tier's value
    onto the base stat block, so the sheet renders them read-only and app.py refuses
    them. Empty when no tier is selected (everything edits the base, as written)."""
    i = active_index(m)
    return frozenset(tiers(m)[i].overrides) if i is not None else frozenset()

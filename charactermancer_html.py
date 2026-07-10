"""charactermancer_html.py — the character-builder UI (pure HTML generation).

`generate(cm)` renders the current step of a Charactermancer as a full page for
the content view. Actions are `dnd:///cm/<verb>/…` links / `location.href`
navigations that app.py intercepts and feeds to `cm.dispatch()`, after which the
page is re-rendered — the same in-place round-trip the Jarvis screen uses.

Only the Ability Scores step is fully built (the walking-skeleton vertical slice);
the remaining steps render a placeholder so navigation works end-to-end. They'll
be filled in one at a time, each reusing this shell.

Layout note: QtWebEngine (Chromium 87) mis-renders flexbox `gap`, so spacing uses
CSS grid `gap` (which works) or explicit margins — never flex `gap`.
"""
import html
import json

import char_rules as cr
from charactermancer import STEPS, STEP_TITLES, THIEF_POINT_STEP

ACCENT = "#c9a84c"


# ── small helpers ────────────────────────────────────────────────────────────

def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _exstr_label(roll: int) -> str:
    """Display form of an exceptional-Strength percentile roll, e.g. 76 -> '18/76'."""
    return "18/00" if roll in (0, 100) else f"18/{roll:02d}"


def _ordinal(n: int) -> str:
    """1 -> '1st', 7 -> '7th', 12 -> '12th', 21 -> '21st'."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _next_level_xp(c):
    """XP needed for the next level, or None past the tabulated range."""
    try:
        return cr.xp_for_level(c.char_class, c.level + 1)
    except (ValueError, KeyError):
        return None


def _attacks_label(c) -> str:
    """'1' / '3/2' / '2' attacks per round."""
    atks = c.attacks_per_round()
    if not atks:
        return "&mdash;"
    n, rounds = atks
    return str(n) if rounds == 1 else f"{n}/{rounds}"


def _level_field(cm) -> str:
    """Level stepper + the stored hit-die rolls. Rendered on the Class step (so the
    slot budgets downstream are already right) and again on the finished sheet."""
    c = cm.character
    if not c.char_class:
        return ""
    cap = c.max_level()
    at_cap = cap is not None and c.level >= cap
    minus = (f'<a class="slot-btn" href="dnd:///cm/level/{c.level - 1}">&minus;</a>'
             if c.level > 1 else '<span class="slot-btn off">&minus;</span>')
    plus = ('<span class="slot-btn off">+</span>' if at_cap else
            f'<a class="slot-btn" href="dnd:///cm/level/{c.level + 1}">+</a>')
    cap_txt = "unlimited" if cap is None else str(cap)

    nxt = _next_level_xp(c)
    xp_note = (f'Next level at {nxt:,} XP.' if nxt and not at_cap
               else ('At the racial level limit.' if at_cap else ""))

    rolls = ""
    if c.hp_rolls:
        vals = ", ".join(str(r) for r in c.hp_rolls)
        rolls = ('<div class="hint">Hit dice rolled after 1st: '
                 f'{vals} &middot; <a class="reroll" href="dnd:///cm/rerollhp">reroll</a></div>')

    return (
        '<div class="field"><label>Level '
        f'<span class="hint">(max {cap_txt})</span></label>'
        f'<div class="hand-row"><div class="pr-slots">{minus}'
        f'<span class="pr-sn">{c.level}</span>{plus}</div>'
        f'<span class="hint" style="margin-left:14px">{xp_note}</span></div>'
        f'{rolls}</div>'
    )


def _ability_summary(ability: str, score: int, exceptional: int = None) -> str:
    """A compact, human-readable line of what a score buys, from char_rules."""
    if ability == "Strength" and score == 18 and exceptional is not None:
        m = cr.strength_mods(18, exceptional)
        return (f"{_exstr_label(exceptional)} &middot; to&#8209;hit {m.hit:+d} &middot; "
                f"dmg {m.dmg:+d} &middot; bend {m.bend_bars}%")
    m = cr.ability_mods(ability, score)
    if ability == "Strength":
        return f"to&#8209;hit {m.hit:+d} &middot; dmg {m.dmg:+d}"
    if ability == "Dexterity":
        return f"defensive AC {m.defensive_ac:+d} &middot; missile {m.missile:+d}"
    if ability == "Constitution":
        return f"HP {m.hp_adj:+d}/die &middot; shock {m.system_shock}%"
    if ability == "Intelligence":
        return (f"max spell L{m.max_spell_level} &middot; learn {m.learn_spell}%"
                if m.max_spell_level else f"{m.languages} languages")
    if ability == "Wisdom":
        bonus = cr.priest_bonus_spells(score)
        extra = ("bonus " + ", ".join(f"{n}&times;L{lvl}" for lvl, n in sorted(bonus.items()))
                 if bonus else f"mag. def {m.magic_defense:+d}")
        return extra
    if ability == "Charisma":
        return f"henchmen {m.max_henchmen} &middot; reaction {m.reaction:+d}"
    if ability == "Perception":
        imm = f" &middot; illusion&nbsp;L{m.illusion_immunity}" if m.illusion_immunity else ""
        return f"surprise {m.surprise:+d}{imm}"
    return ""


# ── the progress rail ────────────────────────────────────────────────────────

# Short labels for the progress rail; with ten steps the columns are ~85px wide, so
# the full step titles don't fit. The step heading still uses STEP_TITLES.
_RAIL_LABELS = {
    "abilities": "Abilities",
    "weapons": "Weapons",
    "nonweapon": "Nonweapon",
}


def _rail(cm) -> str:
    cells = []
    for i, step in enumerate(STEPS):
        done = cm.is_complete(step) and i < cm.index
        current = i == cm.index
        # a step is reachable if every earlier step is complete
        reachable = all(cm.is_complete(STEPS[j]) for j in range(i))
        cls = "cur" if current else ("done" if done else "todo")
        label = _RAIL_LABELS.get(step, STEP_TITLES[step])
        inner = (f'<span class="rn">{i + 1}</span><span class="rl">{label}</span>')
        if reachable and not current:
            cells.append(f'<a class="rail-step {cls}" href="dnd:///cm/goto/{step}">{inner}</a>')
        else:
            cells.append(f'<div class="rail-step {cls}">{inner}</div>')
    return '<nav class="rail">' + "".join(cells) + "</nav>"


# ── the Ability Scores step ──────────────────────────────────────────────────

def _abilities_body(cm, saved=None) -> str:
    c = cm.character
    mode = cm.ability_mode

    toggle = (
        '<div class="modes">'
        f'<a class="mode {"on" if mode == "roll" else ""}" href="dnd:///cm/mode/roll">🎲 Roll</a>'
        f'<a class="mode {"on" if mode == "manual" else ""}" href="dnd:///cm/mode/manual">✎ Manual</a>'
        '</div>'
    )

    roll_area = ""
    if mode == "roll":
        pool = c.rolled_pool
        chips = "".join(f'<span class="die">{v}</span>' for v in sorted(pool, reverse=True))
        pool_html = (f'<div class="pool">{chips}</div>'
                     f'<div class="hint">Assign the rolled values below.</div>'
                     if pool else '<div class="hint">Roll a set of six scores to begin.</div>')
        roll_area = (
            '<div class="roll-area">'
            '<a class="btn" href="dnd:///cm/roll">🎲 Roll 4d6, drop lowest</a>'
            f'{pool_html}</div>'
        )
        # In roll mode, the selector offers the rolled values; in manual, 3–18.
        options_for = lambda cur: _select_options(sorted(set(pool), reverse=True), cur)
    else:
        options_for = lambda cur: _select_options(range(18, 2, -1), cur)

    rows = ""
    for ability in c.ability_names():
        cur = c.abilities.get(ability)
        exc = c.exceptional_str if ability == "Strength" else None
        summary = _ability_summary(ability, cur, exc) if cur is not None else "&mdash;"
        sel = (f'<select onchange="cm(\'assign/{ability}/\'+this.value)">'
               f'{options_for(cur)}</select>')
        rows += (
            '<div class="ab-row">'
            f'<span class="ab-name">{_disp(ability)}</span>'
            f'{sel}'
            f'<span class="ab-sum">{summary}</span>'
            '</div>'
        )

    load = _saved_list(saved, compact=True)
    # The side rail (eligibility panel + references) is added by the shell; each
    # body returns only its main-column content. See generate() / _side_rail.
    return (
        f'{toggle}{roll_area}'
        f'<div class="ab-grid">{rows}</div>'
        f'{_exstr_callout(cm)}'
        f'{load}'
    )


def _select_options(values, cur) -> str:
    opts = ['<option value="" %s>—</option>' % ("selected" if cur is None else "")]
    for v in values:
        opts.append(f'<option value="{v}" {"selected" if v == cur else ""}>{v}</option>')
    return "".join(opts)


def _eligibility_panel(cm) -> str:
    c = cm.character
    if not c.has_all_abilities():
        return ('<div class="side-title">Eligibility</div>'
                '<div class="hint">Set all six scores to see which races and '
                'classes you qualify for.</div>')
    races = c.eligible_races()
    classes = cr.eligible_classes(c.final_abilities())   # ignore race here — pre-race preview
    invalid = c.invalid_abilities()
    warn = (f'<div class="warn">Out of range (3–18): '
            f'{", ".join(a for a, _ in invalid)}</div>' if invalid else "")
    race_chips = "".join(f'<span class="chip">{r}</span>' for r in races) or \
        '<span class="hint">none</span>'
    class_chips = "".join(f'<span class="chip">{k}</span>' for k in classes) or \
        '<span class="hint">none</span>'
    return (
        '<div class="side-title">Eligibility</div>'
        f'{warn}'
        '<div class="side-sub">Races</div>'
        f'<div class="chips">{race_chips}</div>'
        '<div class="side-sub">Classes</div>'
        f'<div class="chips">{class_chips}</div>'
    )


_ABBR = {"Strength": "Str", "Dexterity": "Dex", "Constitution": "Con",
         "Intelligence": "Int", "Wisdom": "Wil", "Charisma": "Cha", "Perception": "Per"}

# The campaign calls Wisdom "Willpower". The rules model keeps the internal name
# "Wisdom" (all char_rules tables key on it); only the display label changes.
_DISPLAY_ABILITY = {"Wisdom": "Willpower"}


def _disp(ability: str) -> str:
    return _DISPLAY_ABILITY.get(ability, ability)


def _exstr_callout(cm) -> str:
    """Exceptional-Strength prompt/result. Shown once a warrior with an 18 Strength
    exists (the roll is warrior-only), plus an informational note at the Ability
    step when an 18 is present but no class is chosen yet."""
    c = cm.character
    if c.final_abilities().get("Strength") != 18 or c.race == "Halfling":
        return ""
    is_warrior = c.char_class and cr.CLASSES[c.char_class].group == "Warrior"
    if not is_warrior:
        return ('<div class="callout">💪 <b>Strength 18.</b> If you choose a warrior class '
                '(Fighter, Paladin, Ranger) you’ll roll d100 for <b>exceptional Strength</b> '
                'to set your damage and to-hit bonuses.</div>')
    if c.exceptional_str is None:
        return ('<div class="callout warn2">💪 <b>Exceptional Strength</b> — as a warrior with an '
                '18 Strength, roll d100 to determine your 18/xx bonuses. '
                '<a class="btn small" href="dnd:///cm/exstr">🎲 Roll d100</a></div>')
    m = cr.strength_mods(18, c.exceptional_str)
    return (f'<div class="callout">💪 <b>Exceptional Strength {_exstr_label(c.exceptional_str)}</b> '
            f'— to-hit {m.hit:+d}, damage {m.dmg:+d}, bend bars {m.bend_bars}%, '
            f'weight allow. {m.weight_allow} lb. '
            f'<a class="reroll" href="dnd:///cm/exstr">re-roll</a></div>')


# ── shared build-summary panel (race / class / later steps) ──────────────────

def _summary_panel(cm) -> str:
    c = cm.character
    final = c.final_abilities()
    adjusted = final != c.abilities
    ab_rows = ""
    for a in c.ability_names():
        v = final.get(a)
        base = c.abilities.get(a)
        moved = adjusted and base is not None and v != base
        val = "&mdash;" if v is None else (f'{v}<span class="adj">&nbsp;({base:+d}&rarr;)</span>'
                                           if moved else str(v))
        ab_rows += f'<div class="sm-ab"><span>{_ABBR[a]}</span><span>{val}</span></div>'

    picks = (f'<div class="sm-pick"><span>Race</span><span>{c.race or "&mdash;"}</span></div>'
             f'<div class="sm-pick"><span>Class</span><span>{c.char_class or "&mdash;"}</span></div>'
             f'<div class="sm-pick"><span>Alignment</span><span>{c.alignment or "&mdash;"}</span></div>')

    return (
        '<div class="side-title">Your Character</div>'
        f'<div class="sm-abgrid">{ab_rows}</div>'
        f'<div class="sm-picks">{picks}</div>'
        f'{_derived_block(cm)}'
    )


def _derived_block(cm) -> str:
    c = cm.character
    if not c.char_class:
        return '<div class="hint">Pick a class to see combat stats.</div>'
    saves = c.saving_throws()
    save_cells = "".join(
        f'<div class="sv"><span>{lbl.split("/")[0][:4]}</span><span>{saves[lbl]}</span></div>'
        for lbl in cr.SAVE_CATEGORIES)
    maxlvl = c.max_level()
    maxlvl_txt = "unlimited" if maxlvl is None else str(maxlvl)
    xp = '<span class="badge">+10% XP</span>' if c.xp_bonus() else ""
    return (
        f'<div class="side-sub">At {_ordinal(c.level)} level</div>'
        '<div class="dstats">'
        f'<div class="ds"><span>Hit Die</span><span>d{c.hit_die()}</span></div>'
        f'<div class="ds"><span>Max HP</span><span>{c.max_hp()}</span></div>'
        f'<div class="ds"><span>Attack bonus</span><span>{c.attack_bonus():+d}</span></div>'
        f'<div class="ds"><span>THAC0</span><span>{c.thac0()}</span></div>'
        f'<div class="ds"><span>Attacks/round</span><span>{_attacks_label(c)}</span></div>'
        f'<div class="ds"><span>Wpn slots</span><span>{c.weapon_slots()}</span></div>'
        f'<div class="ds"><span>NWP slots</span><span>{c.nonweapon_slots()}</span></div>'
        f'<div class="ds"><span>Max level</span><span>{maxlvl_txt}</span></div>'
        '</div>'
        '<div class="side-sub">Saving throws</div>'
        f'<div class="saves">{save_cells}</div>'
        f'{xp}'
    )


# ── Race step ────────────────────────────────────────────────────────────────

def _adj_text(race) -> str:
    adj = cr.RACES[race].adjustments
    return ", ".join(f"{d:+d} {_ABBR[a]}" for a, d in adj.items()) or "No adjustments"


def _race_classes_text(race) -> str:
    r = cr.RACES[race]
    if race == "Human":
        return "Any class · no level limit"
    parts = []
    for cls, lim in sorted(r.level_limits.items()):
        parts.append(f'{cls}&middot;{"U" if lim is None else lim}')
    return " ".join(parts)


def _race_card(cm, race) -> str:
    c = cm.character
    fails = cr.meets_racial_requirements(race, c.abilities)
    eligible = not fails
    selected = c.race == race
    r = cr.RACES[race]
    cls = "pick-card" + (" sel" if selected else "") + ("" if eligible else " dis")

    body = (
        f'<div class="pc-name">{race}</div>'
        f'<div class="pc-line">{_adj_text(race)}</div>'
        f'<div class="pc-sub">Classes</div>'
        f'<div class="pc-classes">{_race_classes_text(race)}</div>'
    )
    if r.notes:
        body += f'<div class="pc-note">{_esc(r.notes[0])}</div>'
    if not eligible:
        why = "; ".join(f"{_ABBR[a]} {lo}–{hi} (have {v})" for a, lo, hi, v in fails)
        body += f'<div class="pc-bad">Requires {why}</div>'

    if eligible:
        return f'<a class="{cls}" href="dnd:///cm/race/{race}">{body}</a>'
    return f'<div class="{cls}">{body}</div>'


def _race_body(cm, saved=None) -> str:
    cards = "".join(_race_card(cm, r) for r in cr.RACES)
    return f'<div class="pick-grid">{cards}</div>'


# ── Class step ───────────────────────────────────────────────────────────────

def _class_unavailable_reason(c, class_name) -> str:
    if c.race and not cr.race_allows(c.race, class_name):
        return f"{c.race}s cannot be {class_name}s"
    fails = cr.meets_class_minimums(class_name, c.final_abilities())
    if fails:
        return "Needs " + ", ".join(f"{_ABBR[a]} {m}+ (have {v})" for a, m, v in fails)
    return ""


def _class_card(cm, class_name) -> str:
    c = cm.character
    k = cr.CLASSES[class_name]
    available = class_name in c.eligible_classes()
    selected = c.char_class == class_name
    cls = "pick-card" + (" sel" if selected else "") + ("" if available else " dis")

    mins = ", ".join(f"{_ABBR[a]} {m}" for a, m in k.minimums.items()) or "none"
    prime = "/".join(_ABBR[a] for a in k.prime_requisites)
    hd = cr.hit_die(class_name, c.house_rules)
    align = (" · " + "/".join(k.allowed_alignments)) if k.allowed_alignments else ""
    maxlvl = ""
    if c.race and cr.race_allows(c.race, class_name):
        lim = cr.max_level(c.race, class_name)
        maxlvl = f'<div class="pc-line">Max level: {"unlimited" if lim is None else lim}</div>'

    body = (
        f'<div class="pc-name">{class_name} <span class="pc-grp">{k.group}</span></div>'
        f'<div class="pc-line">Hit die d{hd} · prime {prime}</div>'
        f'<div class="pc-sub">Minimums</div>'
        f'<div class="pc-line">{mins}{align}</div>'
        f'{maxlvl}'
    )
    if not available:
        body += f'<div class="pc-bad">{_class_unavailable_reason(c, class_name)}</div>'

    if available:
        return f'<a class="{cls}" href="dnd:///cm/class/{class_name}">{body}</a>'
    return f'<div class="{cls}">{body}</div>'


def _class_body(cm, saved=None) -> str:
    cards = "".join(_class_card(cm, k) for k in cr.CLASSES)
    # Level lives here, not on Details: it sets the proficiency-slot budgets that
    # the later Proficiencies step spends.
    return f'<div class="pick-grid">{cards}</div>{_exstr_callout(cm)}{_level_field(cm)}'


# ── Alignment step ───────────────────────────────────────────────────────────

ALIGN_DESC = {
    "Lawful Good": "Honor, compassion, and duty; keeps their word.",
    "Neutral Good": "Does the most good; unbound by law or chaos.",
    "Chaotic Good": "Freedom and kindness; follows their conscience.",
    "Lawful Neutral": "Order above all; reliable and bound by code.",
    "True Neutral": "Balance; avoids taking sides.",
    "Chaotic Neutral": "Personal freedom; unpredictable, self-directed.",
    "Lawful Evil": "Takes what they want within a code or hierarchy.",
    "Neutral Evil": "Pure self-interest; no scruples about law or chaos.",
    "Chaotic Evil": "Destruction and cruelty; driven by whim and greed.",
}


def _alignment_body(cm, saved=None):
    c = cm.character
    allowed = set(c.eligible_alignments())
    restricted = len(allowed) < len(ch_alignments())
    cards = ""
    for a in ch_alignments():
        ok = a in allowed
        selected = c.alignment == a
        cls = "pick-card align" + (" sel" if selected else "") + ("" if ok else " dis")
        body = f'<div class="pc-name">{a}</div><div class="pc-line">{ALIGN_DESC[a]}</div>'
        if ok:
            cards += f'<a class="{cls}" href="dnd:///cm/align/{a}">{body}</a>'
        else:
            cards += f'<div class="{cls}">{body}</div>'
    note = ""
    if restricted:
        note = (f'<div class="hint">{c.char_class} is restricted to '
                f'{", ".join(sorted(allowed))}.</div>')
    return f'{note}<div class="pick-grid">{cards}</div>'


# ── Details step ─────────────────────────────────────────────────────────────

def _handedness_field(cm) -> str:
    """House-rule handedness roll (d10, 10 = ambidextrous). Rendered in the
    Proficiencies step, not Details: ambidexterity affects which weapon
    proficiencies you take (a natural 10 grants it free; otherwise warriors and
    rogues may buy it for a slot)."""
    c = cm.character
    if c.handedness_roll is None and not c.ambidextrous:
        hand = '<span class="hint">Not yet rolled.</span>'
    elif c.ambidextrous:
        why = "Ranger — automatically ambidextrous" if c.char_class == "Ranger" \
            else f"Rolled {c.handedness_roll}"
        hand = f'<span class="hand-res">Ambidextrous</span> <span class="hint">({why})</span>'
    else:
        hand = (f'<span class="hand-res">Right-handed</span> '
                f'<span class="hint">(rolled {c.handedness_roll})</span>')
    return (
        '<div class="field"><label>Handedness '
        '<span class="hint">(house rule: d10, 10 = ambidextrous)</span></label>'
        '<div class="hand-row"><a class="btn" href="dnd:///cm/handedness">🎲 Roll d10</a>'
        f'{hand}</div></div>'
    )


def _details_body(cm, saved=None):
    c = cm.character
    aging = _aging_field(cm) if c.house_rules else ""

    return (
        '<div class="field"><label>Name <span class="req">*</span></label>'
        f'<input class="tf" value="{_esc(c.name)}" placeholder="Character name" '
        'onchange="cmText(\'name\', this.value)" autocomplete="off"></div>'
        '<div class="field"><label>Gender</label>'
        f'<input class="tf" value="{_esc(c.gender)}" placeholder="(optional)" '
        'onchange="cmText(\'gender\', this.value)" autocomplete="off"></div>'
        f'{aging}'
    )


def _aging_field(cm) -> str:
    """House-rule aging: pick an age category; the penalties/bonuses are shown for
    the player to place across their scores (physical vs. mental, their choice)."""
    c = cm.character
    labels = {0: "Young adult", 1: "Middle-aged", 2: "Old", 3: "Venerable"}
    btns = ""
    for lvl in (0, 1, 2, 3):
        on = " on" if c.age_level == lvl else ""
        btns += f'<a class="mode{on}" href="dnd:///cm/age/{lvl}">{labels[lvl]}</a>'
    effect = ""
    if c.age_level:
        pen, bonus = c.aging_effects()
        effect = (f'<div class="hint">Apply <b>−{pen} to physical</b> stats and '
                  f'<b>+{bonus} to mental</b> stats — you choose which scores '
                  '(house rule).</div>')
    return ('<div class="field"><label>Age <span class="hint">(house rule: you place the '
            'penalties &amp; bonuses)</span></label>'
            f'<div class="modes">{btns}</div>{effect}</div>')


# ── Review step (finished sheet + save / load) ───────────────────────────────

def _review_age_row(c) -> str:
    if not c.age_level:
        return ""
    labels = {1: "Middle-aged", 2: "Old", 3: "Venerable"}
    pen, bonus = c.aging_effects()
    return (f'<div class="ds"><span>Age</span><span>{labels[c.age_level]} '
            f'<span class="hint">(−{pen} phys / +{bonus} ment)</span></span></div>')


def _review_profs(c) -> str:
    weapons = [w if rung == "proficient" else f"{w} ({cr.RUNG_LABELS[rung]})"
               for w, rung in c.weapon_profs.items()]
    weapons += [f"{g} group" for g in c.weapon_groups]
    weapons += [f"{s} (shield prof.)" for s in c.shield_profs]
    weapons += [f"{a} (armor prof.)" for a in c.armor_profs]
    weapons += [f"{s} style" + (" (specialised)" if c.style_specialisation(s) else "")
                for s in c.fighting_styles]
    weapons += [f"{d} ({cr.RUNG_LABELS[r]})" for d, r in c.unarmed_profs.items()]
    weapons += list(c.special_talents)
    wp = ", ".join(_esc(w) for w in weapons) or "none"
    nwp = ""
    for name in c.nonweapon_profs:
        skill = c.proficiency_skill(name)
        tag = f' ({skill})' if skill is not None else ""
        nwp += f'<span class="chip">{_esc(name)}{tag}</span>'
    nwp = nwp or '<span class="hint">none</span>'
    return (f'<div class="ds"><span>Weapons</span><span>{wp}</span></div>'
            f'<div class="side-sub" style="margin-top:8px">Nonweapon</div>'
            f'<div class="chips">{nwp}</div>')


def _review_equipment(c) -> str:
    items = "".join(
        f'<span class="chip">{_esc(n)}{(" ×" + str(q)) if q > 1 else ""}</span>'
        for n, q in c.inventory.items()) or '<span class="hint">none</span>'
    worn = ", ".join(_esc(n) for n in c.worn) or "none"
    enc = c.encumbrance() or "—"
    return (
        f'<div class="ds"><span>Coins</span><span>{_money(c.money_cp)}</span></div>'
        f'<div class="ds"><span>Weight</span><span>{c.total_weight():g} lb ({enc})</span></div>'
        f'<div class="ds"><span>Worn</span><span>{worn}</span></div>'
        '<div class="side-sub" style="margin-top:8px">Inventory</div>'
        f'<div class="chips">{items}</div>')


def _review_spells(c) -> str:
    slots = c.spell_slots()
    if not slots:
        return f'<span class="hint">No spells at {_ordinal(c.level)} level.</span>'
    if not c.spells:
        return '<span class="hint">none chosen</span>'
    out = ""
    for lvl in sorted(slots):
        names = sorted(c.spells_at(lvl))
        if not names:
            continue
        chips = "".join(f'<span class="chip">{_esc(n)}</span>' for n in names)
        out += (f'<div class="side-sub">{_ordinal(lvl)} level</div>'
                f'<div class="chips">{chips}</div>')
    return out or '<span class="hint">none chosen</span>'


def _review_thief_skills(c) -> str:
    """A thief's or bard's percentage skills, only for the classes that have them."""
    if not c.has_thief_skills():
        return ""
    rows = "".join(
        f'<div class="ds"><span>{_esc(skill)}</span><span>{score}%</span></div>'
        for skill, score in c.thief_skill_scores().items())
    left = c.thief_points_left()
    note = (f'<div class="hint">{left} discretionary points still unspent.</div>'
            if left else "")
    return ('<div class="rv-block"><div class="rv-h">Thieving Skills</div>'
            f'{rows}{note}</div>')


def _review_turn_undead(c) -> str:
    """The character's row of PHB Table 61, for clerics and paladins of 3rd or better."""
    results = c.turn_undead()
    if not results:
        return ""
    rows = ""
    for kind, result in results.items():
        if result is None:
            shown = '<span class="hint">&mdash;</span>'
        elif result == "D*":
            shown = 'D <span class="badge">+2d4</span>'
        elif result in ("T", "D"):
            shown = result
        else:
            shown = f"{result}+"
        rows += f'<div class="ds"><span>{_esc(kind)}</span><span>{shown}</span></div>'
    turns_as = c.turn_undead_level()
    aside = (f" (as a {_ordinal(turns_as)}-level priest)"
             if c.char_class == "Paladin" else "")
    return ('<div class="rv-block"><div class="rv-h">Turn Undead</div>'
            f'<div class="hint">Roll d20 and meet the number{aside}. '
            'T turns automatically, D destroys.</div>'
            f'{rows}</div>')


def _review_body(cm, saved=None):
    c = cm.character
    final = c.final_abilities()
    ab = ""
    for a in c.ability_names():
        v = final.get(a)
        exc = c.exceptional_str if a == "Strength" else None
        ab += (f'<div class="rv-ab"><span class="rv-abn">{_ABBR[a]}</span>'
               f'<span class="rv-abv">{v}</span>'
               f'<span class="rv-abs">{_ability_summary(a, v, exc) if v is not None else ""}</span></div>')

    hand = ("Ambidextrous" if c.ambidextrous else
            ("Right-handed" if c.handedness_roll else "—"))
    saves = c.saving_throws() or {}
    save_cells = "".join(
        f'<div class="sv"><span>{lbl.split("/")[0][:4]}</span><span>{saves.get(lbl, "—")}</span></div>'
        for lbl in cr.SAVE_CATEGORIES)
    maxlvl_txt = "—" if not c.char_class else ("unlimited" if c.max_level() is None else c.max_level())
    xp = ' <span class="badge">+10% XP</span>' if c.xp_bonus() else ""

    def _f(v, sign=False):
        if v is None:
            return "—"
        return f"{v:+d}" if sign else str(v)

    hd = c.hit_die()
    sheet = (
        '<div class="sheet">'
        f'<div class="sheet-head"><div class="sheet-name">{_esc(c.name) or "Unnamed"}</div>'
        f'<div class="sheet-sub">{c.race or "—"} {c.char_class or ""} · '
        f'{_ordinal(c.level)} level · {c.alignment or "—"}</div></div>'
        f'<div class="rv-abgrid">{ab}</div>'
        '<div class="rv-cols">'
        f'<div class="rv-block"><div class="rv-h">Combat ({_ordinal(c.level)} level)</div>'
        f'<div class="ds"><span>Hit Die</span><span>{"d" + str(hd) if hd else "—"}</span></div>'
        f'<div class="ds"><span>Max HP</span><span>{_f(c.max_hp())}</span></div>'
        f'<div class="ds"><span>Armor Class</span><span>{_f(c.armor_class())}</span></div>'
        f'<div class="ds"><span>Attack bonus</span><span>{_f(c.attack_bonus(), sign=True)}</span></div>'
        f'<div class="ds"><span>THAC0</span><span>{_f(c.thac0())}</span></div>'
        f'<div class="ds"><span>Attacks/round</span><span>{_attacks_label(c)}</span></div>'
        f'<div class="ds"><span>Weapon slots</span><span>{_f(c.weapon_slots())}</span></div>'
        f'<div class="ds"><span>NWP slots</span><span>{_f(c.nonweapon_slots())}</span></div>'
        f'<div class="ds"><span>Max level</span><span>{maxlvl_txt}{xp}</span></div>'
        f'<div class="ds"><span>Handedness</span><span>{hand}</span></div>'
        f'{_review_age_row(c)}'
        '</div>'
        '<div class="rv-block"><div class="rv-h">Saving throws</div>'
        f'<div class="saves">{save_cells}</div>'
        '<div class="rv-h" style="margin-top:14px">Proficiencies</div>'
        f'{_review_profs(c)}'
        '</div>'
        '<div class="rv-block"><div class="rv-h">Equipment</div>'
        f'{_review_equipment(c)}'
        '</div>'
        '<div class="rv-block"><div class="rv-h">Spells</div>'
        f'{_review_spells(c)}'
        '</div>'
        f'{_review_thief_skills(c)}'
        f'{_review_turn_undead(c)}'
        '</div>'
        '</div>'
    )

    # Level up the finished character in place (same widget as the Class step).
    advance = f'<div class="saved-box" style="margin-bottom:16px">{_level_field(cm)}</div>' \
        if c.char_class else ""

    save_label = "💾 Update saved" if cm.saved_id else "💾 Save character"
    saved_note = '<span class="saved-ok">Saved ✓</span>' if cm.saved_id else ""
    actions = (
        '<div class="rv-actions">'
        f'<a class="btn" href="dnd:///cm/save">{save_label}</a>{saved_note}'
        '<a class="nav-btn" href="dnd:///cm/roll20export">⎘ Export to Roll20</a>'
        '<a class="nav-btn" href="dnd:///cm/restart">＋ New character</a>'
        '</div>'
    )
    return sheet + advance + actions + _saved_list(saved, heading="Saved characters")


# ── saved-character list (shared: review + abilities entry) ──────────────────

def _saved_list(saved, heading="Load a saved character", compact=False) -> str:
    saved = saved or []
    if not saved:
        return ""
    rows = ""
    for row in saved:
        cid, name, race, klass, align = row
        meta = " · ".join(x for x in (race, klass, align) if x)
        rows += (
            '<div class="sc-row">'
            f'<a class="sc-load" href="dnd:///cm/load/{cid}">{_esc(name) or "Unnamed"}'
            f'<span class="sc-meta">{_esc(meta)}</span></a>'
            f'<a class="sc-del" href="dnd:///cm/delete/{cid}" title="Delete">✕</a>'
            '</div>'
        )
    cls = "saved-box compact" if compact else "saved-box"
    return f'<div class="{cls}"><div class="side-sub">{heading}</div>{rows}</div>'


def ch_alignments():
    # imported lazily to avoid a hard import cycle at module load
    from character import ALIGNMENTS
    return ALIGNMENTS


# ── Proficiencies step ───────────────────────────────────────────────────────

def _prof_meta(p) -> str:
    """The compact 'Str +0' / 'no check' meta shown on a proficiency chip."""
    if p.ability:
        return f'{_ABBR.get(p.ability, p.ability)} {p.modifier:+d}'
    return "no check"


def _prof_tooltip(p) -> str:
    """A one-line hover summary of a proficiency's rules text."""
    desc = " ".join((p.description or "").split())
    return desc if len(desc) <= 280 else desc[:277].rstrip() + "…"


def _prof_description_html(p) -> str:
    """The full rules text as an expandable block (paragraphs preserved)."""
    if not p.description:
        return ""
    paras = "".join(f"<p>{_esc(par)}</p>"
                    for par in p.description.split("\n\n") if par.strip())
    return (f'<details class="pr-desc"><summary>What it does</summary>'
            f'<div class="pr-desc-body">{paras}</div></details>')


def _slot_cost_label(cost: int) -> str:
    return "free" if cost == 0 else str(cost)


#: Shown under an overspent slot bar. Only a level drop can get you here.
_OVER_NOTE = ("Your level affords fewer slots than you have spent. "
              "Give some back to continue.")


def _budget_bar(used: int, total: int, label: str, unit: str = "slots used",
                over_note: str = "") -> str:
    """A spent/remaining bar. Going over budget is reachable by dropping a level,
    so the bar turns red and explains itself rather than quietly reading "-2 left"."""
    left = total - used
    pct = 0 if total <= 0 else min(100, round(used / total * 100))
    over = left < 0
    cls = " over" if over else ""
    note = (f'<div class="budget-over">Over budget by {-left}. '
            f'{over_note}</div>') if over and over_note else ""
    return (
        f'<div class="budget{cls}">'
        f'<div class="budget-top"><span>{label}</span>'
        f'<span class="budget-num">{left} left</span></div>'
        f'<div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>'
        f'<div class="budget-sub">{used} of {total} {unit}</div>'
        f'{note}'
        '</div>'
    )


def _ct_description_html(name: str) -> str:
    """An expandable "What it does" block for a Combat & Tactics style, discipline or
    talent — the same affordance the nonweapon proficiencies have.

    Shows a summary of the mechanical effect rather than the rulebook's prose (which
    spends most of its words on flavour and edge cases), then links out to the full
    rule for anyone who wants the rest."""
    summary = cr.ct_summary(name)
    if not summary:
        return ""
    page = cr.ct_page(name)
    link = (f'<p><a class="reroll" href="dnd:///newtab/{page}">'
            f'Read the full rule &rarr;</a></p>' if page else "")
    return (f'<details class="pr-desc"><summary>What it does</summary>'
            f'<div class="pr-desc-body"><p>{_esc(summary)}</p>{link}</div></details>')


def _ct_tooltip(name: str) -> str:
    """A one-line hover summary for a buy-list chip."""
    summary = " ".join(cr.ct_summary(name).split())
    if not summary:
        return ""
    return _esc(summary if len(summary) <= 280 else summary[:277].rstrip() + "…")


def _weapon_row(cm, weapon: str, rung: str, from_group: bool = False) -> str:
    """A trained weapon: its rung, the slots it costs, and the mastery steppers."""
    c = cm.character
    cost = c.weapon_prof_cost(weapon, rung)
    top = cr.next_weapon_rung(rung, c.char_class, c.level) is None

    down = (f'<a class="slot-btn" href="dnd:///cm/wpndown/{weapon}">&minus;</a>'
            if c.can_lower_weapon(weapon) else '<span class="slot-btn off">&minus;</span>')
    up = (f'<a class="slot-btn" href="dnd:///cm/wpnup/{weapon}">+</a>'
          if c.can_raise_weapon(weapon) else '<span class="slot-btn off">+</span>')

    detail = f'{cr.RUNG_LABELS[rung]} &middot; {_slot_cost_label(cost)} slot'
    detail += "s" if cost != 1 else ""
    if from_group:
        detail += ' &middot; <span class="hint">from a weapon group</span>'
    if top and cr.specialises(rung):
        detail += ' &middot; <span class="hint">top of the ladder</span>'
    # A fighter may move his specialisation here, at CT's escalating price.
    if rung == "proficient" and c.specialised_weapon() not in (None, weapon):
        respec = c.respecialisation_cost(weapon)
        if c.can_respecialise(weapon):
            detail += (f' &middot; <a class="reroll" href="dnd:///cm/respec/{weapon}">'
                       f'specialise here ({respec} slot{"s" if respec != 1 else ""})</a>')
        elif respec is not None:
            detail += (f' &middot; <span class="hint">moving specialisation here '
                       f'costs {respec} slots</span>')
    groups = cr.weapon_tight_groups(weapon)
    if groups:
        detail += f' &middot; {_esc(", ".join(groups))}'

    # A group-granted proficiency has no entry of its own to remove.
    rm = ('<span class="pr-rm" title="Granted by a weapon group">•</span>' if from_group
          else f'<a class="pr-rm" href="dnd:///cm/rmweapon/{weapon}" title="Remove">✕</a>')
    return (
        '<div class="prof-row">'
        f'{rm}'
        f'<div class="pr-main"><span class="pr-name">{_esc(weapon)}</span>'
        f'<span class="pr-detail">{detail}</span></div>'
        f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
        '</div>')


def _weapon_group_block(cm) -> str:
    """Buy a whole tight group for 2 slots; every weapon in it becomes proficient."""
    c = cm.character
    cost = cr.WEAPON_GROUP_SLOT_COST

    bought = ""
    for group in c.weapon_groups:
        members = ", ".join(cr.weapon_group_members(group))
        rm = (f'<a class="pr-rm" href="dnd:///cm/rmgroup/{group}" title="Remove">✕</a>'
              if c.can_remove_weapon_group(group)
              else '<span class="pr-rm" title="Removing would overdraw your slots">✕</span>')
        bought += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{_esc(group)}</span>'
            f'<span class="pr-detail">{_esc(members)}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cost}</span></div></div>')

    opts = ""
    for group in cr.tight_groups_with_members():
        if group in c.weapon_groups:
            continue
        dis = "" if c.can_add_weapon_group(group) else " dis"
        tip = _esc(", ".join(cr.weapon_group_members(group)))
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addgroup/{group}" title="{tip}">'
                 f'<span class="opt-name">{_esc(group)}</span>'
                 f'<span class="opt-cost">{cost}</span></a>')

    return (
        f'<div class="grp-label" style="margin-top:16px">Weapon groups</div>'
        f'<div class="hint">{cost} slots buys proficiency in every weapon of one tight '
        'group. Hover a group for its weapons.</div>'
        + (f'<div class="chosen-list">{bought}</div>' if bought else "")
        + f'<div class="opt-grid">{opts}</div>')


def _shield_armor_block(cm) -> str:
    """Shield and armor proficiencies — one weapon slot each."""
    c = cm.character
    rows = ""
    for name in c.shield_profs:
        detail = (f'Shield &middot; AC +{cr.shield_ac_bonus(name, True)} '
                  f'(was +{cr.shield_ac_bonus(name, False)}) &middot; blocks '
                  f'{cr.shield_attackers_blocked(name)}')
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmshieldprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">{detail}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cr.SHIELD_PROF_SLOT_COST}</span>'
            '</div></div>')
    for name in c.armor_profs:
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmarmorprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">Armor &middot; counts '
            f'{c.item_weight(name):g} lb instead of '
            f'{(cr.item(name) or {}).get("weight", 0):g}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cr.ARMOR_PROF_SLOT_COST}</span>'
            '</div></div>')

    opts = ""
    for name in cr.SHIELD_TYPES:
        if name in c.shield_profs:
            continue
        dis = "" if c.can_add_shield_prof(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addshieldprof/{name}">'
                 f'<span class="opt-name">{_esc(name)}</span>'
                 f'<span class="opt-cost">{cr.SHIELD_PROF_SLOT_COST}</span></a>')
    for name in cr.armor_items():
        if name in c.armor_profs:
            continue
        dis = "" if c.can_add_armor_prof(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addarmorprof/{name}">'
                 f'<span class="opt-name">{_esc(name)}</span>'
                 f'<span class="opt-cost">{cr.ARMOR_PROF_SLOT_COST}</span></a>')

    return (
        '<div class="grp-label" style="margin-top:16px">Shield &amp; armor proficiency</div>'
        '<div class="hint">One slot each. A shield proficiency raises its AC bonus and '
        'how many attackers it blocks; an armor proficiency halves that armor\'s '
        'encumbrance.</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + f'<div class="opt-grid">{opts}</div>')


def _fighting_styles_block(cm) -> str:
    """Warriors know every style free; nonwarriors buy one. Specialising costs a slot
    (and priests/rogues may specialise in only one style)."""
    c = cm.character
    if not c.char_class:
        return ""
    free = cr.knows_styles_free(c.char_class)

    rows = ""
    for style in cr.FIGHTING_STYLES:
        known = c.knows_style(style)
        spec = c.style_specialisation(style)
        if not known:
            continue
        cost = c.style_cost(style)
        down = (f'<a class="slot-btn" href="dnd:///cm/styledown/{style}">&minus;</a>'
                if c.can_despecialise_style(style) else '<span class="slot-btn off">&minus;</span>')
        up = (f'<a class="slot-btn" href="dnd:///cm/styleup/{style}">+</a>'
              if c.can_specialise_style(style) else '<span class="slot-btn off">+</span>')

        detail = "Known (free)" if free and spec == 0 else "Known"
        if spec:
            detail = f'Specialised &times;{spec}' if spec > 1 else "Specialised"
            if cr.style_free_specialisation(style, c.char_class):
                detail += ' &middot; <span class="hint">first slot free for rangers</span>'
        if style == "Two-Weapon":
            primary, off = c.two_weapon_penalty()
            detail += f' &middot; to-hit {primary:+d} / {off:+d}'
        rm = (f'<a class="pr-rm" href="dnd:///cm/forgetstyle/{style}" title="Unlearn">✕</a>'
              if c.can_forget_style(style) else '<span class="pr-rm">•</span>')
        rows += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{_esc(style)}</span>'
            f'<span class="pr-detail">{detail}</span>{_ct_description_html(style)}</div>'
            f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
            '</div>')

    opts = ""
    for style in cr.FIGHTING_STYLES:
        if c.knows_style(style):
            continue
        dis = "" if c.can_learn_style(style) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/learnstyle/{style}" '
                 f'title="{_ct_tooltip(style)}">'
                 f'<span class="opt-name">{_esc(style)}</span>'
                 f'<span class="opt-cost">{cr.STYLE_LEARN_SLOT_COST}</span></a>')

    if free:
        note = ("Warriors know every fighting style. Specialising costs one slot, and "
                "you may specialise in as many styles as you can afford.")
    elif cr.can_specialise_styles(c.char_class):
        note = ("One slot to learn a style, one more to specialise — and a "
                f"{_esc(c.char_class)} may specialise in only one style.")
    else:
        note = f"One slot to learn a style. A {_esc(c.char_class)} cannot specialise in one."

    return (
        '<div class="grp-label" style="margin-top:16px">Fighting styles</div>'
        f'<div class="hint">{note}</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + (f'<div class="opt-grid">{opts}</div>' if opts else ""))


def _unarmed_block(cm) -> str:
    """CT Ch5 unarmed disciplines, riding the same rung ladder as weapons."""
    c = cm.character
    if not c.char_class:
        return ""

    rows = ""
    for name in cr.UNARMED_DISCIPLINES:
        entry = cr.UNARMED_DISCIPLINES[name]
        rung = c.unarmed_rung(name)
        held = name in c.unarmed_profs
        if not held and rung == "nonproficient":
            continue                       # untrained martial art: it's in the buy list
        cost = cr.unarmed_prof_cost(rung) if held else 0
        down = (f'<a class="slot-btn" href="dnd:///cm/unarmeddown/{name}">&minus;</a>'
                if c.can_lower_unarmed(name) else '<span class="slot-btn off">&minus;</span>')
        up = (f'<a class="slot-btn" href="dnd:///cm/unarmedup/{name}">+</a>'
              if c.can_raise_unarmed(name) else '<span class="slot-btn off">+</span>')
        bits = [cr.RUNG_LABELS[rung]]
        if entry.rung_cap is None:
            bits.append("cannot be advanced")
        if held and not entry.nonwarrior_benefit and \
                cr.CLASSES[c.char_class].group != "Warrior":
            bits.append("nonwarriors gain no benefit")
        if entry.note:
            bits.append(entry.note)
        rm = (f'<a class="pr-rm" href="dnd:///cm/rmunarmed/{name}" title="Remove">✕</a>'
              if held else '<span class="pr-rm" title="Free">•</span>')
        rows += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">{_esc(" · ".join(bits))}</span>'
            f'{_ct_description_html(name)}</div>'
            f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
            '</div>')

    opts = ""
    for name in cr.UNARMED_DISCIPLINES:
        if name in c.unarmed_profs or not cr.unarmed_rung_ladder(name, c.char_class, c.level):
            continue
        if not cr.is_martial_art(name) and c.unarmed_rung(name) != "familiar":
            continue
        dis = "" if c.can_add_unarmed(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addunarmed/{name}" '
                 f'title="{_ct_tooltip(name)}">'
                 f'<span class="opt-name">{_esc(name)}</span>'
                 f'<span class="opt-cost">{cr.unarmed_prof_cost("proficient")}</span></a>')

    return (
        '<div class="grp-label" style="margin-top:16px">Unarmed combat</div>'
        '<div class="hint">Everyone is familiar with pummeling, wrestling and '
        'overbearing for free. Proficiency costs a weapon slot; expertise is open to '
        'any class, specialisation and mastery to single-class fighters. Martial arts '
        'styles are learned separately — they form no weapon group, so they grant no '
        'familiarity, and you may be expert or specialised in only one.</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + (f'<div class="opt-grid">{opts}</div>' if opts else ""))


def _talent_rows(cm, names) -> str:
    c = cm.character
    rows = ""
    for name in names:
        talent = cr.TALENTS.get(name)
        if not talent:
            continue
        source = c.special_talents[name]
        bits = [f'{talent.slots} {source} slot' + ("s" if talent.slots != 1 else "")]
        skill = c.talent_skill(name)
        if skill is not None:
            bits.append(f'{_ABBR.get(talent.ability, talent.ability)} check {skill}')
        # `initial_rating` is deliberately not shown: it's the Skills & Powers form of
        # the same check, and this campaign rolls the PHB one. Two numbers here would
        # only leave a player wondering which to roll against.
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmtalent/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">{" &middot; ".join(bits)}</span>'
            f'{_ct_description_html(name)}</div>'
            f'<div class="pr-slots"><span class="pr-sn">{talent.slots}</span></div></div>')
    return rows


def _talent_opts(cm, talents) -> str:
    c = cm.character
    opts = ""
    for talent in talents:
        if talent.name in c.special_talents:
            continue
        dis = "" if c.can_add_talent(talent.name) else " dis"
        meta = (f'<span class="opt-meta">{_ABBR.get(talent.ability, talent.ability)}</span>'
                if talent.ability else "")
        tip = _ct_tooltip(talent.name)
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addtalent/{talent.name}" '
                 f'title="{tip}">'
                 f'<span class="opt-name">{_esc(talent.name)}</span>{meta}'
                 f'<span class="opt-cost">{talent.slots}</span></a>')
        if talent.slot_source == "either":
            dis2 = "" if c.can_add_talent(talent.name, "nonweapon") else " dis"
            opts += (f'<a class="opt{dis2}" href="dnd:///cm/addtalentnwp/{talent.name}" '
                     f'title="Pay with a nonweapon slot instead">'
                     f'<span class="opt-name">{_esc(talent.name)} (NWP)</span>'
                     f'<span class="opt-cost">{talent.slots}</span></a>')
    return opts


def _talents_block(cm) -> str:
    """CT special talents, the martial-arts talents, and the two siege proficiencies."""
    c = cm.character
    if not c.char_class:
        return ""
    chosen = set(c.special_talents)

    out = (
        '<div class="grp-label" style="margin-top:16px">Special talents</div>'
        '<div class="hint">Bought with weapon slots. Alertness and Endurance may be '
        'paid for with a nonweapon slot instead (CT marks them with an asterisk).</div>')
    rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.SPECIAL_TALENTS])
    if rows:
        out += f'<div class="chosen-list">{rows}</div>'
    opts = _talent_opts(cm, cr.talents_for_class(c.char_class))
    out += (f'<div class="opt-grid">{opts}</div>' if opts else
            '<span class="hint">No talents available to this class.</span>')

    ma = cr.martial_arts_talents_for_class(c.char_class)
    if ma:
        out += '<div class="grp-label" style="margin-top:16px">Martial arts talents</div>'
        note = ('Only a martial artist can learn these. Either slot type pays.'
                if c.knows_a_martial_art() else
                'Requires proficiency in a martial arts style (see Unarmed combat above).')
        out += f'<div class="hint">{note}</div>'
        rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.MARTIAL_ARTS_TALENTS])
        if rows:
            out += f'<div class="chosen-list">{rows}</div>'
        out += f'<div class="opt-grid">{_talent_opts(cm, ma)}</div>'

    siege = cr.siege_proficiencies_for_class(c.char_class)
    if siege:
        out += ('<div class="grp-label" style="margin-top:16px">Siege proficiencies</div>'
                '<div class="hint">Warfare and war-machine skills, acquired like any '
                'nonweapon proficiency — they cost a nonweapon slot.</div>')
        rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.SIEGE_PROFICIENCIES])
        if rows:
            out += f'<div class="chosen-list">{rows}</div>'
        out += f'<div class="opt-grid">{_talent_opts(cm, siege)}</div>'
    return out


def _weapon_section(cm) -> str:
    c = cm.character
    total, used, left = c.weapon_slots_total(), c.weapon_slots_used(), c.weapon_slots_left()

    chosen = "".join(_weapon_row(cm, w, rung) for w, rung in c.weapon_profs.items())
    # Weapons a bought group grants: shown so they can still be specialised.
    for w in cr.WEAPONS:
        if w not in c.weapon_profs and c.group_covers(w):
            chosen += _weapon_row(cm, w, "proficient", from_group=True)
    chosen = chosen or '<span class="hint">No weapons chosen yet.</span>'

    # Ambidexterity is no longer special-cased here — it is a CT special talent and
    # lives in the talents block below.
    opts = ""
    for w in cr.WEAPONS:
        if w in c.weapon_profs or c.group_covers(w):
            continue                       # already trained, or granted by a group
        cost = c.weapon_prof_cost(w, "proficient")
        dis = "" if c.can_add_weapon(w) else " dis"
        # Flag the two things that change a weapon's price for this character.
        barred = cr.barred_weapon_penalty(w, c.char_class) if c.char_class else 0
        meta = ""
        if barred:
            meta = f'<span class="opt-meta" title="Barred to your class">+{barred}</span>'
        elif c.weapon_rung(w) == "familiar":
            meta = '<span class="opt-meta" title="Same weapon group as one you know">fam</span>'
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addweapon/{w}">'
                 f'<span class="opt-name">{w}</span>{meta}'
                 f'<span class="opt-cost">{_slot_cost_label(cost)}</span></a>')

    ladder = c.weapon_rung_ladder()
    ladder_txt = " &rarr; ".join(cr.RUNG_LABELS[r] for r in ladder) if ladder else ""
    guide = (f'<div class="hint">House rules: crossbows are free, bows cost 2 slots. '
             f'Mastery ladder for a {_esc(c.char_class or "character")}: {ladder_txt}. '
             'Weapons sharing a tight group make you <i>familiar</i> with the rest.'
             '</div>' if ladder else
             '<div class="hint">House rules: crossbows are free, bows cost 2 slots.</div>')

    return (
        '<section class="prof-sec">'
        '<h3 class="prof-h">Weapon Proficiencies</h3>'
        f'{_handedness_field(cm)}'
        f'{_budget_bar(used, total, "Weapon slots", over_note=_OVER_NOTE)}'
        f'{guide}'
        f'<div class="chosen-list">{chosen}</div>'
        f'<div class="opt-grid">{opts}</div>'
        f'{_weapon_group_block(cm)}'
        f'{_shield_armor_block(cm)}'
        f'{_fighting_styles_block(cm)}'
        f'{_unarmed_block(cm)}'
        f'{_talents_block(cm)}'
        '</section>'
    )


def _nonweapon_section(cm) -> str:
    c = cm.character
    total, used, left = c.nonweapon_slots_total(), c.nonweapon_slots_used(), c.nonweapon_slots_left()
    known = c.nonweapon_profs

    # ── chosen ────────────────────────────────────────────────────────────────
    chosen = ""
    for name, invested in known.items():
        p = cr.NONWEAPON_PROFICIENCIES[name]
        skill = c.proficiency_skill(name)
        if skill is not None:
            detail = f'{_ABBR.get(p.ability, p.ability)} &middot; check {skill} (d20+skill &ge; 21)'
        else:
            detail = "no check"
        minus = (f'<a class="slot-btn" href="dnd:///cm/profminus/{name}">&minus;</a>'
                 if invested > p.slots else '<span class="slot-btn off">&minus;</span>')
        plus = (f'<a class="slot-btn" href="dnd:///cm/profplus/{name}">+</a>'
                if left >= 1 else '<span class="slot-btn off">+</span>')
        chosen += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">{detail}</span>{_prof_description_html(p)}</div>'
            f'<div class="pr-slots">{minus}<span class="pr-sn">{invested}</span>{plus}</div>'
            '</div>'
        )
    if not chosen:
        chosen = '<span class="hint">No proficiencies chosen yet.</span>'

    # ── available: only skills this class can learn, split ready vs. locked ────
    pool = (cr.proficiencies_for_class(c.char_class) if c.char_class
            else cr.NONWEAPON_PROFICIENCIES.values())
    ready, locked = [], []
    for p in pool:
        if p.name in known:
            continue
        (ready if cr.proficiency_prereqs_met(p, known) else locked).append(p)
    ready.sort(key=lambda p: p.name)
    locked.sort(key=lambda p: p.name)

    def _chip(p, clickable: bool) -> str:
        name = f'<span class="opt-name">{_esc(p.name)}</span>'
        tip = _prof_tooltip(p)
        if clickable:
            cost = f'<span class="opt-cost">{p.slots}</span>' if p.slots != 1 else ""
            meta = f'<span class="opt-meta">{_prof_meta(p)}</span>'
            dis = "" if p.slots <= left else " dis"
            return (f'<a class="opt{dis}" title="{tip}" href="dnd:///cm/addprof/{p.name}">'
                    f'{name}{meta}{cost}</a>')
        need = _esc(", ".join(p.prereq))
        return (f'<span class="opt locked" title="{tip}">{name}'
                f'<span class="opt-need" title="Prerequisite">{need}</span></span>')

    avail_html = ""
    if ready:
        avail_html += ('<div class="grp-label">Available</div>'
                       f'<div class="opt-grid">{"".join(_chip(p, True) for p in ready)}</div>')
    if locked:
        avail_html += ('<div class="grp-label">Needs a prerequisite first</div>'
                       f'<div class="opt-grid">{"".join(_chip(p, False) for p in locked)}</div>')
    if not avail_html:
        avail_html = '<span class="hint">No further proficiencies available for this class.</span>'

    return (
        '<section class="prof-sec">'
        f'<h3 class="prof-h">Nonweapon Proficiencies '
        f'<span class="prof-src">from {_esc(cr.PROFICIENCY_BOOK)}</span></h3>'
        f'{_budget_bar(used, total, "Nonweapon slots", over_note=_OVER_NOTE)}'
        '<div class="hint">House rule: each extra slot on a proficiency adds +2 to its check. '
        'Only skills your class can learn are shown; hover a skill for its rules.</div>'
        f'<div class="chosen-list">{chosen}</div>'
        f'<div class="avail">{avail_html}</div>'
        '</section>'
    )


def _weapons_body(cm, saved=None) -> str:
    """The weapon-slot budget: weapons and their mastery rungs, weapon groups,
    shield/armor proficiency, fighting styles, unarmed disciplines and talents."""
    return f'<div class="prof-wrap">{_weapon_section(cm)}</div>'


#: The four adjustment tables are linked from the step's reference rail; only the
#: prose page that explains what each skill *does* is worth an inline link.
_THIEF_SKILLS_PAGE = "PHB/DD01505.htm"

_ARMOR_KIND_LABELS = {
    "none": "no armor",
    "leather": "leather",
    "elven_chain": "elven chain",
    "padded_studded": "padded, hide or studded leather",
    "chain_ring": "chain or ring mail",
}


def _thief_skill_breakdown(c, skill: str) -> str:
    """Where a skill's percentage came from, as a plain-text hover title."""
    dex = c.final_abilities().get("Dexterity") or 0
    parts = [f"base {cr.thief_skill_base(c.char_class, skill)}%"]
    for label, adj in (
        (str(c.race), cr.thief_racial_adjustment(c.race, skill)),
        (f"Dex {dex}", cr.thief_dex_adjustment(dex, skill)),
        (_ARMOR_KIND_LABELS[c.thief_armor_kind()], cr.thief_armor_adjustment(c.thief_armor_kind(), skill)),
    ):
        if adj:
            parts.append(f"{label} {adj:+d}%")
    spent = c.thief_points_in(skill)
    if spent:
        parts.append(f"{spent} points spent")
    return _esc(", ".join(parts))


def _thief_skills_block(cm) -> str:
    """Thief/Bard only: spread the discretionary percentage points (PHB Tables 26-29)."""
    c = cm.character
    if not c.has_thief_skills():
        return ""
    total, used, left = c.thief_points_total(), c.thief_points_used(), c.thief_points_left()
    cap = cr.thief_max_points_in_skill(c.char_class, c.level)
    step = THIEF_POINT_STEP

    rows = ""
    for skill in c.thief_skill_names():
        spent = c.thief_points_in(skill)
        score = c.thief_skill_score(skill)
        capped = score >= cr.THIEF_SKILL_MAX
        minus = (f'<a class="slot-btn" href="dnd:///cm/thiefdown/{skill}">&minus;</a>'
                 if c.can_remove_thief_point(skill, step) else '<span class="slot-btn off">&minus;</span>')
        plus = (f'<a class="slot-btn" href="dnd:///cm/thiefup/{skill}">+</a>'
                if c.can_add_thief_point(skill, step) else '<span class="slot-btn off">+</span>')
        note = " &middot; at the 95% ceiling" if capped else ""
        rows += (
            '<div class="prof-row">'
            f'<div class="pr-main"><span class="pr-name">{_esc(skill)}</span>'
            f'<span class="pr-detail" title="{_thief_skill_breakdown(c, skill)}">'
            f'{score}% &middot; {spent} of {cap} points{note}</span></div>'
            f'<div class="pr-slots">{minus}<span class="pr-sn">{spent}</span>{plus}</div>'
            '</div>'
        )

    armor = _ARMOR_KIND_LABELS[c.thief_armor_kind()]
    return (
        '<section class="prof-sec">'
        '<h3 class="prof-h">Thieving Skills '
        f'<span class="prof-src">PHB Tables 26&ndash;29</span></h3>'
        f'{_budget_bar(used, total, "Discretionary points", unit="points spent")}'
        f'<div class="hint">Points go in blocks of {step}, at most {cap} into any one skill, '
        f'and no skill may pass {cr.THIEF_SKILL_MAX}%. Scores already include your race, '
        f'your Dexterity, and the armor you are wearing (currently {armor}) &mdash; '
        'hover a score to see the arithmetic. '
        f'<a href="dnd:///{_THIEF_SKILLS_PAGE}">What each skill does &rarr;</a>'
        '</div>'
        f'<div class="chosen-list">{rows}</div>'
        '</section>'
    )


def _nonweapon_body(cm, saved=None) -> str:
    """The nonweapon-slot budget: the campaign's skills, plus a thief's percentage skills."""
    return f'<div class="prof-wrap">{_nonweapon_section(cm)}{_thief_skills_block(cm)}</div>'


# ── equipment step ───────────────────────────────────────────────────────────

def _money(cp: int) -> str:
    """Copper pieces as a compact g/s/c string, e.g. 12345 -> '123 gp 4 sp 5 cp'."""
    gp, rem = divmod(max(0, cp), 100)
    sp, c = divmod(rem, 10)
    parts = []
    if gp:
        parts.append(f"{gp} gp")
    if sp:
        parts.append(f"{sp} sp")
    if c or not parts:
        parts.append(f"{c} cp")
    return " ".join(parts)


def _cost_label(cp: int) -> str:
    """Short item price for a chip: gp/sp when it divides evenly, else cp."""
    if cp >= 100 and cp % 100 == 0:
        return f"{cp // 100}gp"
    if cp >= 10 and cp % 10 == 0:
        return f"{cp // 10}sp"
    return f"{cp}cp"


def _eq_item_detail(it: dict) -> str:
    bits = []
    if it.get("category") == "Armor" and it.get("ac_bonus"):
        bits.append(f'+{it["ac_bonus"]} AC')
    if it.get("category") == "Weapon" and it.get("damage"):
        bits.append(f'{_esc(it["damage"])} dmg')
    if it.get("weight"):
        bits.append(f'{it["weight"]:g} lb')
    return " &middot; ".join(bits) if bits else _esc(it.get("category", ""))


def _eq_item_plain(it: dict) -> str:
    """Plain-text stat line (no HTML entities) for an item's hover title=."""
    bits = []
    if it.get("category") == "Armor" and it.get("ac_bonus"):
        bits.append(f'+{it["ac_bonus"]} AC')
    if it.get("category") == "Weapon" and it.get("damage"):
        bits.append(f'{it["damage"]} dmg')
    if it.get("weight"):
        bits.append(f'{it["weight"]:g} lb')
    return " · ".join(bits) if bits else str(it.get("category", ""))


def _equipment_body(cm, saved=None) -> str:
    c = cm.character
    money, ac, weight = c.money_cp, c.armor_class(), c.total_weight()
    enc = c.encumbrance() or "—"

    roll_label = "🎲 Re-roll starting money" if (money or c.inventory) else "🎲 Roll starting money"
    money_bar = (
        '<div class="eq-money">'
        f'<div class="eq-coins">{_money(money)}</div>'
        f'<a class="btn small" href="dnd:///cm/money">{roll_label}</a>'
        '</div>')

    stats = (
        '<div class="eq-stats">'
        f'<div class="eq-stat"><span class="eq-k">Armor Class</span><span class="eq-v">{ac}</span></div>'
        f'<div class="eq-stat"><span class="eq-k">Weight</span><span class="eq-v">{weight:g} lb</span></div>'
        f'<div class="eq-stat"><span class="eq-k">Load</span><span class="eq-v">{enc}</span></div>'
        '</div>')

    owned = ""
    for name, qty in c.inventory.items():
        it = cr.item(name) or {}
        wear = ""
        if it.get("category") == "Armor":
            worn = name in c.worn
            wear = (f'<a class="wear {"on" if worn else ""}" href="dnd:///cm/wear/{name}">'
                    f'{"Worn ✓" if worn else "Wear"}</a>')
        qtytag = f' ×{qty}' if qty > 1 else ""
        # Hover an owned item for its stat line + notes (the buy chips already do
        # this; the owned rows didn't).
        tip = _esc("; ".join(x for x in (_eq_item_plain(it), it.get("notes")) if x))
        owned += (
            f'<div class="prof-row" title="{tip}">'
            f'<a class="pr-rm" href="dnd:///cm/sell/{name}" title="Sell / return">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}{qtytag}</span>'
            f'<span class="pr-detail">{_eq_item_detail(it)}</span></div>'
            f'{wear}</div>')
    owned = owned or '<span class="hint">Nothing bought yet.</span>'

    cat_html = ""
    for cat in cr.ITEM_CATEGORY_ORDER:
        items = cr.items_in_category(cat)
        if not items:
            continue
        chips = ""
        for it in items:
            dis = "" if it["cost_cp"] <= money else " dis"
            wt = f'{it["weight"]:g} lb' if it.get("weight") else ""
            meta = f'<span class="opt-meta">{wt}</span>' if wt else ""
            tip = _esc(it.get("notes") or "")
            chips += (f'<a class="opt{dis}" href="dnd:///cm/buy/{it["name"]}" title="{tip}">'
                      f'<span class="opt-name">{_esc(it["name"])}</span>{meta}'
                      f'<span class="opt-cost">{_cost_label(it["cost_cp"])}</span></a>')
        cat_html += f'<div class="grp-label">{cat}</div><div class="opt-grid">{chips}</div>'

    return (
        '<section class="prof-sec">'
        '<h3 class="prof-h">Equipment <span class="prof-src">buy with your starting coin</span></h3>'
        f'{money_bar}{stats}'
        '<div class="side-sub" style="margin-top:12px">Owned</div>'
        f'<div class="chosen-list">{owned}</div>'
        '<div class="hint">Prices in gp/sp/cp; hover an item for notes. Wear armor to add its AC.</div>'
        f'<div class="avail">{cat_html}</div>'
        '</section>')


# ── spells step ──────────────────────────────────────────────────────────────

def _spell_description_html(s) -> str:
    """A spell's full effect as an expandable block (mirrors _prof_description_html)."""
    desc = s.get("description") or ""
    if not desc.strip():
        return ""
    paras = "".join(f"<p>{_esc(par)}</p>" for par in desc.split("\n\n") if par.strip())
    return (f'<details class="pr-desc"><summary>What it does</summary>'
            f'<div class="pr-desc-body">{paras}</div></details>')


def _spell_level_section(cm, spell_level: int, catalog: dict) -> str:
    """One spell level's budget, chosen spells and available picks."""
    c = cm.character
    group = c.spellcasting_group()
    limit = c.spell_limit(spell_level)
    full = not c.can_add_spell(spell_level)
    chosen_names = set(c.spells)

    chosen = ""
    for name in sorted(c.spells_at(spell_level)):
        s = catalog.get(name, {"name": name})
        chosen += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmspell/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{_esc(name)}</span>'
            f'<span class="pr-detail">{_esc(s.get("school") or "")}</span>'
            f'{_spell_description_html(s)}</div>'
            '</div>')
    chosen = chosen or '<span class="hint">None chosen at this level.</span>'

    by_school: dict = {}
    for s in cm.spell_catalog:
        if s["name"] in chosen_names or int(s.get("level") or 1) != spell_level:
            continue
        by_school.setdefault(s.get("school") or "Other", []).append(s)
    avail = ""
    for school in sorted(by_school):
        chips = ""
        for s in sorted(by_school[school], key=lambda x: x["name"]):
            tip = _esc(" ".join((s.get("description") or "").split())[:280])
            dis = " dis" if full else ""
            chips += (f'<a class="opt{dis}" href="dnd:///cm/addspell/{s["name"]}" title="{tip}">'
                      f'<span class="opt-name">{_esc(s["name"])}</span></a>')
        avail += f'<div class="grp-label">{_esc(school)}</div><div class="opt-grid">{chips}</div>'
    avail = avail or '<span class="hint">No spell data loaded for this level.</span>'

    if limit is None:
        budget = ('<div class="hint">Intelligence 19+ — your spellbook may hold every '
                  'spell of this level.</div>')
    else:
        unit = "known" if group == "wizard" else "memorized"
        budget = _budget_bar(len(c.spells_at(spell_level)), limit,
                             f"{_ordinal(spell_level)}-level spells", unit=unit)
    full_note = ('<div class="hint">Limit reached at this level — remove one to choose '
                 'another.</div>' if full and limit else "")
    return (
        f'<div class="grp-label" style="margin-top:18px">{_ordinal(spell_level)} level</div>'
        f'{budget}'
        f'<div class="chosen-list">{chosen}</div>'
        f'{full_note}'
        f'<div class="avail">{avail}</div>')


def _spells_body(cm, saved=None) -> str:
    c = cm.character
    group = c.spellcasting_group()
    slots = c.spell_slots()
    if not group or not slots:
        # Either a non-caster, or a caster below the level its progression starts
        # (a ranger before 8th, a paladin before 9th, a bard at 1st).
        if group and c.char_class:
            why = (f'A {_esc(c.char_class)} gains no spells until a higher level — '
                   f'they cast nothing at {_ordinal(c.level)} level.')
        else:
            why = (f'A {_esc(c.char_class or "character")} doesn\'t cast spells — '
                   'skip ahead.')
        return (
            '<section class="prof-sec"><h3 class="prof-h">Spells</h3>'
            '<div class="placeholder"><div class="ph-ico">✦</div>'
            f'<div class="ph-title">No spells at {_ordinal(c.level)} level</div>'
            f'<p>{why}</p></div></section>')

    catalog = {s["name"]: s for s in cm.spell_catalog}
    guide = ("Your spellbook's size at each level is capped by Intelligence."
             if group == "wizard" else
             "Choose the priest spells you'll memorize; Wisdom grants bonus spells.")
    sections = "".join(_spell_level_section(cm, lvl, catalog) for lvl in sorted(slots))
    return (
        '<section class="prof-sec">'
        f'<h3 class="prof-h">Spells <span class="prof-src">{group} &middot; '
        f'{_ordinal(c.level)} level &middot; up to {_ordinal(max(slots))}-level spells'
        '</span></h3>'
        f'<div class="hint">{guide} Expand a chosen spell for its full effect.</div>'
        f'{sections}'
        '</section>')


# ── placeholder for not-yet-built steps ──────────────────────────────────────

def _placeholder_body(cm, saved=None) -> str:
    return (
        '<div class="placeholder">'
        f'<div class="ph-ico">🚧</div>'
        f'<div class="ph-title">{STEP_TITLES[cm.step]}</div>'
        '<p>This step is coming next — it reuses the same shell and the character '
        'model already computes everything it needs.</p>'
        '</div>'
    )


# ── Per-step references (folded in from the old static walkthrough) ───────────
# Each build step links out to the reference it draws on. Most point at the PHB
# rules/tables; the proficiency and spell steps point at the campaign's own
# in-app pages instead (the Codex of Worldly Craft and the Spell Compendium).
# Each entry is (label, dnd-path, kind) where kind is "phb" or "app".
_STEP_REFS = {
    "abilities": [
        ("Rolling Ability Scores", "PHB/DD01422.htm", "phb"),
        ("Alternative Methods", "PHB/DD01423.htm", "phb"),
        ("What the Numbers Mean", "PHB/DD01437.htm", "phb"),
    ],
    "race": [
        ("Racial Requirements", "PHB/DD01438.htm", "phb"),
        ("Min/Max Scores (Table 8)", "PHB/DD01440.htm", "phb"),
        ("Racial Ability Adjustments", "PHB/DD01441.htm", "phb"),
    ],
    "class": [
        ("Class Overview", "PHB/DD01456.htm", "phb"),
        ("Ability Minimums (Table 13)", "PHB/DD01458.htm", "phb"),
        ("Multi-/Dual-Class Rules", "PHB/DD01511.htm", "phb"),
    ],
    "alignment": [
        ("Alignment Overview", "PHB/DD01515.htm", "phb"),
        ("The Nine Alignments", "PHB/DD01518.htm", "phb"),
    ],
    "weapons": [
        ("Weapon Proficiencies", "PHB/DD01526.htm", "phb"),
        ("Proficiency Slots (Table 34)", "PHB/DD01524.htm", "phb"),
        ("Weapon Specialization", "PHB/DD01530.htm", "phb"),
        ("Specialization & Mastery", "CT/DD02618.htm", "ct"),      # Ch4
        ("Weapon Mastery", "CT/DD02629.htm", "ct"),
        ("Weapon Groups", "CT/DD02744.htm", "ct"),
        ("Barred Weapons", "CT/DD02624.htm", "ct"),
        ("Shield Proficiency", "CT/DD02627.htm", "ct"),
        ("Armor Proficiency", "CT/DD02628.htm", "ct"),
        ("Fighting Style Specialization", "CT/DD02645.htm", "ct"),
        ("Special Talents", "CT/DD02653.htm", "ct"),
        ("Unarmed Combat", "CT/DD02666.htm", "ct"),                # Ch5
        ("Martial Arts", "CT/DD02700.htm", "ct"),
        ("Martial Arts Talents", "CT/DD02705.htm", "ct"),
    ],
    "nonweapon": [
        ("The Codex of Worldly Craft", "proficiencies", "app"),   # campaign NWP book
        ("Nonweapon Proficiencies", "PHB/DD01533.htm", "phb"),
        ("Proficiency Slots (Table 34)", "PHB/DD01524.htm", "phb"),
        ("Proficiency Groups (Table 37)", "PHB/DD01538.htm", "phb"),
        ("Siege Proficiencies", "CT/DD02824.htm", "ct"),
        ("Thieving Skills", "PHB/DD01505.htm", "phb"),
        ("Thief Base Scores (Table 26)", "PHB/DD01501.htm", "phb"),
        ("Thief Racial Adj. (Table 27)", "PHB/DD01502.htm", "phb"),
        ("Thief Dexterity Adj. (Table 28)", "PHB/DD01503.htm", "phb"),
        ("Thief Armor Adj. (Table 29)", "PHB/DD01504.htm", "phb"),
    ],
    "equipment": [
        ("Economics of the Realm", "toc/ECO", "app"),             # campaign price/gear book
        ("Starting Gold (Table 43)", "PHB/DD01613.htm", "phb"),
    ],
    "spells": [
        ("Spell Compendium", "screen/spells", "app"),             # in-app spell browser
    ],
    "details": [
        ("Languages (Table 4)", "PHB/DD01432.htm", "phb"),
        ("Charisma (Table 6)", "PHB/DD01436.htm", "phb"),
        ("Other Details", "PHB/DD01452.htm", "phb"),
    ],
}

_REF_BADGE = {"phb": "PHB", "app": "APP", "ct": "C&amp;T"}


def _step_refs(step) -> str:
    """A compact reference panel of deep-links for the current step."""
    refs = _STEP_REFS.get(step)
    if not refs:
        return ""
    # Prefix with newtab/ so references open beside the builder, not over it.
    chips = "".join(
        f'<a class="phb-ref {kind}" href="dnd:///newtab/{url}">'
        f'<span class="phb-badge">{_REF_BADGE[kind]}</span>{_esc(label)}</a>'
        for label, url, kind in refs
    )
    return (f'<div class="phb-refs"><span class="phb-refs-label">References</span>'
            f'{chips}</div>')


def _side_rail(cm) -> str:
    """The persistent right rail shown on every build step except Review: the
    character overview (eligibility while setting scores, the running summary once
    a race/class exists) plus this step's References — pinned so both stay in view
    as you scroll the step."""
    panel = _eligibility_panel(cm) if cm.step == "abilities" else _summary_panel(cm)
    return (
        '<aside class="side-rail">'
        f'<div class="col-side">{panel}</div>'
        f'{_step_refs(cm.step)}'
        '</aside>'
    )


_BODIES = {
    "abilities": _abilities_body, "race": _race_body, "class": _class_body,
    "alignment": _alignment_body,
    "weapons": _weapons_body, "nonweapon": _nonweapon_body,
    "equipment": _equipment_body, "spells": _spells_body,
    "details": _details_body, "review": _review_body,
}


# ── the shell ────────────────────────────────────────────────────────────────

def _footer(cm) -> str:
    back = ('<a class="nav-btn" href="dnd:///cm/back">‹ Back</a>'
            if cm.can_go_back() else '<span class="nav-btn off">‹ Back</span>')

    if cm.can_advance():
        nxt = '<a class="nav-btn primary" href="dnd:///cm/next">Next ›</a>'
        hint = ""
    else:
        nxt = '<span class="nav-btn primary off">Next ›</span>'
        hint = f'<span class="foot-hint">{_next_hint(cm)}</span>'
    return f'<footer class="foot">{back}<div class="foot-mid">{hint}</div>{nxt}</footer>'


def _next_hint(cm) -> str:
    if cm.index >= len(STEPS) - 1:
        return "Your character is complete."
    c = cm.character
    if cm.step == "class" and c.char_class and c.rolls_exceptional_strength() \
            and c.exceptional_str is None:
        return "Roll d100 for exceptional Strength."
    return {
        "abilities": "Set every ability score (3–18).",
        "race": "Choose a race.",
        "class": "Choose a class.",
        "alignment": "Choose an alignment.",
        "details": "Enter a character name.",
    }.get(cm.step, "")


# Actions that always want the top of the page: they replace the character or move
# to a different step, so the reader's old position means nothing.
_SCROLL_TO_TOP_VERBS = frozenset({"restart", "load", "next", "back", "goto"})


def keeps_scroll(path: str, step_before: str, step_after: str) -> bool:
    """Whether a builder action should preserve the reader's scroll position.

    Picking a weapon or stepping a rung leaves you exactly where you were; changing
    step, loading a character or starting over should land you at the top."""
    if step_before != step_after:
        return False
    return path.split("/", 1)[0] not in _SCROLL_TO_TOP_VERBS


def generate_wrap(cm, saved=None) -> str:
    """The builder's content — everything inside `<div class="wrap">`.

    Split out from `generate()` so an in-place action can replace just this node in
    the live document (see `swap_wrap_js`) instead of reloading the whole page."""
    body = _BODIES.get(cm.step, _placeholder_body)(cm, saved)
    step = (f'<section class="step"><h2 class="step-h">{STEP_TITLES[cm.step]}</h2>'
            f'{body}</section>')
    # Every step but Review gets the pinned side rail (overview + references);
    # Review keeps its own full-width finished sheet.
    if cm.step == "review":
        step_block = step
    else:
        step_block = f'<div class="step-layout">{step}{_side_rail(cm)}</div>'
    return f"""<div class="wrap">
  <header class="head">
    <div class="tag">2nd Edition · Character Builder</div>
    <h1>Create a Character</h1>
  </header>
  {_rail(cm)}
  {step_block}
  {_footer(cm)}
</div>"""


def swap_wrap_js(wrap_html: str, scroll_to_top: bool) -> str:
    """JS that replaces the live document's `.wrap` node with fresh markup.

    Re-rendering with `setHtml` tears the document down and rebuilds it, so the view
    blanks and repaints — the flicker no amount of scroll juggling can hide. Swapping
    one node inside the *existing* document leaves the scroll offset alone, keeps the
    page's `cm()` helpers defined, and never blanks.

    Returns `false` when the current document isn't the builder, so the caller can
    fall back to a full render."""
    payload = json.dumps(wrap_html)
    scroll = "window.scrollTo(0,0);" if scroll_to_top else ""
    return ("(function(){var w=document.querySelector('.wrap');"
            f"if(!w){{return false;}}w.outerHTML={payload};{scroll}return true;}})();")


def generate(cm, saved=None) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Charactermancer</title>
<style>{_CSS}</style>
</head>
<body>
{generate_wrap(cm, saved)}
<script>
  function cm(path) {{ if (path.endsWith('/')) return; window.location.href = 'dnd:///cm/' + path; }}
  function cmText(verb, v) {{ window.location.href = 'dnd:///cm/' + verb + '/' + encodeURIComponent(v); }}
</script>
</body>
</html>"""


_CSS = f"""
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1a1c26; color: #c8cad8;
         font-family: "Segoe UI", system-ui, -apple-system, sans-serif; font-size: 13px; }}
  .wrap {{ max-width: 940px; margin: 0 auto; padding: 30px 34px 40px; }}
  .head {{ margin-bottom: 22px; }}
  .tag {{ display: inline-block; background: {ACCENT}18; color: {ACCENT}; font-size: 10.5px;
         font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
         padding: 3px 10px; border-radius: 4px; margin-bottom: 10px; }}
  h1 {{ font-size: 2em; font-weight: 800; color: #e6e9f6; }}

  /* progress rail (grid, not flex-gap) */
  .rail {{ display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 6px;
          margin-bottom: 26px; }}
  /* Stack the number above the label so all step numbers align on one row even
     when labels wrap (the columns are narrow with 9 steps). Flex column is fine
     in QtWebEngine; only flex `gap` is not, so spacing is a margin. */
  .rail-step {{ display: flex; flex-direction: column; align-items: center; text-decoration: none;
               padding: 8px 6px; border-radius: 7px; background: #20232f; border: 1px solid #2a2e3e;
               text-align: center; color: #8891b0; }}
  a.rail-step:hover {{ border-color: {ACCENT}66; }}
  .rail-step.done {{ color: #9fb08a; }}
  .rail-step.cur {{ background: {ACCENT}1c; border-color: {ACCENT}; color: #e6e9f6; }}
  .rn {{ display: inline-block; min-width: 18px; height: 18px; line-height: 18px; border-radius: 50%;
        background: #2f3444; color: #c8cad8; font-size: 10px; font-weight: 800; margin-bottom: 5px; }}
  .rail-step.cur .rn {{ background: {ACCENT}; color: #1a1c26; }}
  .rail-step.done .rn {{ background: #6f8a54; color: #12140d; }}
  .rl {{ font-size: 11px; font-weight: 600; letter-spacing: .02em; line-height: 1.25; }}

  .step {{ background: #1e202c; border: 1px solid #2a2e3e; border-radius: 12px;
          padding: 22px 24px; margin-bottom: 20px; }}
  .step-h {{ font-size: 1.15em; font-weight: 700; color: #e6e9f6; margin-bottom: 16px;
            padding-bottom: 12px; border-bottom: 1px solid #2a2e3e; }}

  /* abilities */
  .modes {{ display: inline-grid; grid-auto-flow: column; gap: 6px; margin-bottom: 16px; }}
  .mode {{ text-decoration: none; padding: 6px 14px; border-radius: 7px; font-weight: 600;
          font-size: 12px; background: #23263a; border: 1px solid #383c52; color: #c8cad8; }}
  .mode.on {{ background: {ACCENT}22; border-color: {ACCENT}; color: #e6e9f6; }}
  .roll-area {{ margin-bottom: 18px; }}
  .btn {{ display: inline-block; text-decoration: none; background: {ACCENT}; color: #1a1c26;
         font-weight: 700; font-size: 12.5px; padding: 9px 18px; border-radius: 8px; }}
  .btn:hover {{ filter: brightness(1.08); }}
  .pool {{ display: grid; grid-auto-flow: column; grid-auto-columns: max-content; gap: 8px;
          margin: 14px 0 4px; }}
  .die {{ width: 34px; height: 34px; line-height: 34px; text-align: center; border-radius: 7px;
         background: #262a40; border: 1px solid #3a3f58; color: #e6e9f6; font-weight: 800;
         font-size: 14px; }}
  .hint {{ color: #6b7290; font-size: 11.5px; font-style: italic; margin-top: 6px; line-height: 1.5; }}

  /* Shell-level step + pinned side rail (overview + references). The body owns
     only the main column; the rail is shared across every step but Review. */
  .step-layout {{ display: grid; grid-template-columns: 1fr 260px; gap: 20px;
                 align-items: start; margin-bottom: 20px; }}
  @media (max-width: 820px) {{ .step-layout {{ grid-template-columns: 1fr; }} }}
  .step-layout > .step {{ margin-bottom: 0; }}
  .side-rail {{ position: sticky; top: 16px; display: grid; gap: 14px; }}
  .ab-grid {{ display: grid; gap: 8px; }}
  .ab-row {{ display: grid; grid-template-columns: 96px 74px 1fr; align-items: center; gap: 12px;
            background: #23263a; border: 1px solid #2f3346; border-radius: 8px; padding: 8px 12px; }}
  .ab-name {{ font-weight: 700; color: #e0e2f0; font-size: 12.5px; }}
  .ab-sum {{ color: #8b93b8; font-size: 11px; }}
  select {{ background: #1a1c26; color: #e6e9f6; border: 1px solid #3a3f58; border-radius: 6px;
           padding: 5px 6px; font-size: 13px; outline: none; }}
  select:focus {{ border-color: {ACCENT}; }}

  .col-side {{ background: #191b25; border: 1px solid #2a2e3e; border-radius: 10px; padding: 14px 16px; }}
  .side-title {{ font-size: 10.5px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
                color: {ACCENT}; margin-bottom: 10px; }}
  .side-sub {{ font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
              color: #7b83a6; margin: 12px 0 6px; }}
  .chips {{ display: flex; flex-wrap: wrap; }}
  .chip {{ background: #262a40; border: 1px solid #363b54; border-radius: 20px; padding: 2px 10px;
          font-size: 11px; color: #cdd2e6; margin: 0 5px 5px 0; }}
  .warn {{ background: #3a2326; border: 1px solid #6b3b40; color: #e7b0b4; border-radius: 6px;
          padding: 6px 10px; font-size: 11px; margin-bottom: 10px; }}

  /* pick cards (race / class) */
  .pick-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 11px; }}
  .pick-card {{ display: block; text-decoration: none; background: #23263a; border: 1px solid #2f3346;
               border-radius: 10px; padding: 13px 14px; color: #c8cad8; }}
  a.pick-card:hover {{ border-color: {ACCENT}66; background: #262a40; }}
  .pick-card.sel {{ border-color: {ACCENT}; background: {ACCENT}16; }}
  .pick-card.dis {{ opacity: .45; }}
  .pc-name {{ font-weight: 800; font-size: 14px; color: #e6e9f6; margin-bottom: 5px; }}
  .pc-grp {{ font-size: 9.5px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
            color: {ACCENT}; background: {ACCENT}1c; border-radius: 4px; padding: 1px 6px;
            margin-left: 4px; vertical-align: middle; }}
  .pc-line {{ font-size: 11.5px; color: #b7bcd4; margin-bottom: 3px; }}
  .pc-sub {{ font-size: 9.5px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
            color: #7b83a6; margin: 8px 0 3px; }}
  .pc-classes {{ font-size: 11px; color: #9aa0c0; line-height: 1.6; }}
  .pc-note {{ font-size: 10.5px; color: #838aad; font-style: italic; margin-top: 8px; line-height: 1.45; }}
  .pc-bad {{ font-size: 10.5px; color: #d98a8a; margin-top: 8px; }}

  /* summary panel */
  .sm-abgrid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; margin-bottom: 12px; }}
  .sm-ab {{ display: flex; justify-content: space-between; font-size: 12px;
           border-bottom: 1px solid #23263a; padding: 2px 0; }}
  .sm-ab span:first-child {{ color: #8b93b8; }}
  .sm-ab span:last-child {{ color: #e6e9f6; font-weight: 700; }}
  .adj {{ color: {ACCENT}; font-weight: 600; font-size: 10px; }}
  .sm-picks {{ margin-bottom: 4px; }}
  .sm-pick {{ display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; }}
  .sm-pick span:first-child {{ color: #8b93b8; }}
  .sm-pick span:last-child {{ color: #e0e2f0; font-weight: 600; }}
  .dstats {{ display: grid; gap: 3px; margin-bottom: 6px; }}
  .ds {{ display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; }}
  .ds span:first-child {{ color: #8b93b8; }}
  .ds span:last-child {{ color: #e6e9f6; font-weight: 700; }}
  .saves {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; margin-bottom: 8px; }}
  .sv {{ text-align: center; background: #23263a; border: 1px solid #2f3346; border-radius: 6px;
        padding: 4px 2px; }}
  .sv span {{ display: block; }}
  .sv span:first-child {{ font-size: 8.5px; color: #7b83a6; text-transform: uppercase; letter-spacing: .04em; }}
  .sv span:last-child {{ font-size: 13px; font-weight: 800; color: #e6e9f6; }}
  .badge {{ display: inline-block; background: #2c3a24; border: 1px solid #4a6b34; color: #a7d488;
           font-size: 10px; font-weight: 700; border-radius: 5px; padding: 2px 8px; }}

  .pick-card.align .pc-line {{ color: #9aa0c0; }}

  /* exceptional-Strength callout */
  .callout {{ background: {ACCENT}12; border: 1px solid {ACCENT}40; border-radius: 9px;
             padding: 11px 14px; margin-top: 16px; font-size: 12.5px; color: #d8dcec;
             line-height: 1.5; }}
  .callout.warn2 {{ background: #33291a; border-color: #6b531f; }}
  .callout b {{ color: #e6e9f6; }}
  .btn.small {{ padding: 5px 12px; font-size: 11.5px; margin-left: 6px; }}
  .reroll {{ color: {ACCENT}; text-decoration: none; font-size: 11px; margin-left: 6px; }}
  .reroll:hover {{ text-decoration: underline; }}

  /* details form */
  .field {{ margin-bottom: 18px; max-width: 420px; }}
  .field label {{ display: block; font-size: 11px; font-weight: 700; letter-spacing: .05em;
                 text-transform: uppercase; color: #8b93b8; margin-bottom: 6px; }}
  .req {{ color: {ACCENT}; }}
  .tf {{ width: 100%; background: #1a1c26; color: #e6e9f6; border: 1px solid #3a3f58;
        border-radius: 7px; padding: 9px 12px; font-size: 14px; outline: none; }}
  .tf:focus {{ border-color: {ACCENT}; }}
  .hand-row {{ display: flex; align-items: center; }}
  .hand-row .btn {{ margin-right: 12px; }}
  .hand-res {{ color: #e6e9f6; font-weight: 700; }}

  /* review sheet */
  .sheet {{ background: #191b25; border: 1px solid #2a2e3e; border-radius: 12px;
           padding: 20px 22px; margin-bottom: 16px; }}
  .sheet-head {{ border-bottom: 1px solid #2a2e3e; padding-bottom: 12px; margin-bottom: 14px; }}
  .sheet-name {{ font-size: 1.5em; font-weight: 800; color: #e6e9f6; }}
  .sheet-sub {{ font-size: 12.5px; color: {ACCENT}; font-weight: 600; margin-top: 2px; }}
  .rv-abgrid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 16px; }}
  .rv-ab {{ background: #23263a; border: 1px solid #2f3346; border-radius: 8px; padding: 8px 10px; }}
  .rv-abn {{ font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
            color: #8b93b8; }}
  .rv-abv {{ font-size: 18px; font-weight: 800; color: #e6e9f6; margin-left: 6px; }}
  .rv-abs {{ display: block; font-size: 10.5px; color: #838aad; margin-top: 2px; }}
  .rv-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
  @media (max-width: 640px) {{ .rv-cols {{ grid-template-columns: 1fr; }} .rv-abgrid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .rv-h {{ font-size: 10.5px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase;
          color: {ACCENT}; margin-bottom: 8px; }}
  .rv-actions {{ display: flex; align-items: center; margin-bottom: 18px; }}
  .rv-actions .btn {{ margin-right: 12px; }}
  .rv-actions .nav-btn {{ margin-left: auto; }}
  .saved-ok {{ color: #a7d488; font-weight: 700; font-size: 12px; margin-right: 12px; }}

  /* saved-character list */
  .saved-box {{ background: #191b25; border: 1px solid #2a2e3e; border-radius: 10px;
               padding: 12px 14px; }}
  .saved-box.compact {{ margin-top: 18px; }}
  .sc-row {{ display: flex; align-items: center; border-top: 1px solid #23263a; }}
  .sc-row:first-of-type {{ border-top: none; }}
  .sc-load {{ flex: 1; text-decoration: none; color: #dfe2f0; font-weight: 600; font-size: 13px;
             padding: 8px 4px; }}
  .sc-load:hover {{ color: {ACCENT}; }}
  .sc-meta {{ color: #7b83a6; font-weight: 400; font-size: 11px; margin-left: 8px; }}
  .sc-del {{ text-decoration: none; color: #6b7290; font-size: 13px; padding: 6px 8px; border-radius: 5px; }}
  .sc-del:hover {{ color: #d98a8a; background: #2a1e22; }}

  /* proficiencies step */
  .prof-wrap {{ display: grid; gap: 22px; }}
  .prof-sec {{ }}
  .prof-h {{ font-size: 1.05em; font-weight: 700; color: #e6e9f6; margin-bottom: 12px; }}
  .budget {{ margin-bottom: 8px; }}
  .budget-top {{ display: flex; justify-content: space-between; align-items: baseline;
                font-size: 12px; color: #c8cad8; margin-bottom: 5px; }}
  .budget-num {{ color: {ACCENT}; font-weight: 800; }}
  .bar {{ height: 7px; background: #23263a; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: {ACCENT}; border-radius: 4px; transition: width .15s; }}
  .budget-sub {{ font-size: 10.5px; color: #7b83a6; margin-top: 4px; }}
  .budget.over .budget-num {{ color: #e06c75; }}
  .budget.over .bar-fill {{ background: #e06c75; }}
  .budget-over {{ font-size: 11px; color: #e06c75; margin-top: 5px; }}
  .chosen {{ display: flex; flex-wrap: wrap; margin: 10px 0; }}
  .chip-x {{ display: inline-flex; align-items: center; text-decoration: none; background: {ACCENT}18;
            border: 1px solid {ACCENT}55; color: #e6e9f6; border-radius: 20px; padding: 3px 10px;
            font-size: 11.5px; font-weight: 600; margin: 0 6px 6px 0; }}
  .chip-x:hover {{ background: #3a2326; border-color: #6b3b40; }}
  .cx-cost {{ background: #1a1c26; color: #9aa0c0; border-radius: 8px; padding: 0 6px; font-size: 9.5px;
             margin: 0 6px; }}
  .opt-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px;
              margin-top: 6px; }}
  /* NOTE: no flex `gap` here — the bundled QtWebEngine Chromium ignores it. Space
     the children with margin-left instead (grid `gap` is fine, flex `gap` is not). */
  .opt {{ display: flex; align-items: center; text-decoration: none;
         background: #23263a; border: 1px solid #2f3346; border-radius: 7px; padding: 6px 10px;
         color: #c8cad8; font-size: 11.5px; }}
  a.opt:hover {{ border-color: {ACCENT}66; background: #262a40; }}
  .opt.dis {{ opacity: .4; pointer-events: none; }}
  /* name grows so the ability/cost numbers align to the right edge of each chip */
  .opt-name {{ flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis;
              white-space: nowrap; }}
  .opt-cost {{ flex: 0 0 auto; margin-left: 6px; background: {ACCENT}22; color: {ACCENT};
              border-radius: 8px; padding: 0 6px; font-size: 9.5px; font-weight: 700; }}
  .opt-meta {{ flex: 0 0 auto; margin-left: 6px; color: #7b83a6; font-size: 10px; }}
  .grp-label {{ font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
               color: #7b83a6; margin: 14px 0 4px; }}
  .chosen-list {{ display: grid; gap: 6px; margin: 10px 0; }}
  .prof-row {{ display: flex; align-items: center; background: #23263a; border: 1px solid #2f3346;
              border-radius: 8px; padding: 6px 10px; }}
  .pr-rm {{ text-decoration: none; color: #6b7290; font-size: 12px; margin-right: 10px; }}
  .pr-rm:hover {{ color: #d98a8a; }}
  .pr-main {{ flex: 1; }}
  .pr-name {{ font-weight: 700; color: #e0e2f0; font-size: 12.5px; margin-right: 8px; }}
  .pr-detail {{ color: #8b93b8; font-size: 11px; }}
  .pr-slots {{ display: flex; align-items: center; }}
  .slot-btn {{ text-decoration: none; width: 20px; height: 20px; line-height: 18px; text-align: center;
              border: 1px solid #3a3f58; border-radius: 5px; color: #e6e9f6; font-weight: 700;
              font-size: 13px; }}
  a.slot-btn:hover {{ border-color: {ACCENT}; background: {ACCENT}18; }}
  .slot-btn.off {{ opacity: .3; }}
  .pr-sn {{ min-width: 22px; text-align: center; font-weight: 800; color: {ACCENT}; }}
  .prof-src {{ font-size: 11px; font-weight: 500; font-style: italic; color: #7b83a6;
              letter-spacing: normal; text-transform: none; }}
  .pr-desc {{ margin-top: 5px; }}
  .pr-desc > summary {{ cursor: pointer; color: {ACCENT}; font-size: 10.5px; list-style: none; }}
  .pr-desc > summary::-webkit-details-marker {{ display: none; }}
  .pr-desc-body {{ color: #a8adc4; font-size: 11px; line-height: 1.5; margin-top: 4px;
                  max-height: 260px; overflow-y: auto; padding-right: 6px; }}
  .pr-desc-body p {{ margin: 0 0 6px; }}
  .opt.locked {{ opacity: .7; cursor: default; }}
  .opt-need {{ flex: 0 0 auto; margin-left: 6px; color: #c9a66b; font-size: 9px; white-space: nowrap; }}
  /* equipment step (no flex `gap` — QtWebEngine ignores it; use margins) */
  .eq-money {{ display: flex; align-items: center; justify-content: space-between;
              background: #1b1e2b; border: 1px solid #2f3346; border-radius: 8px;
              padding: 10px 14px; margin: 6px 0 10px; }}
  .eq-coins {{ font-weight: 800; color: {ACCENT}; font-size: 15px; }}
  .eq-stats {{ display: flex; margin: 4px 0 6px; }}
  .eq-stat {{ flex: 1; background: #1b1e2b; border: 1px solid #2f3346; border-radius: 8px;
             padding: 8px 10px; margin-right: 8px; text-align: center; }}
  .eq-stat:last-child {{ margin-right: 0; }}
  .eq-k {{ display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .06em;
          color: #7b83a6; }}
  .eq-v {{ display: block; font-weight: 800; color: #e6e9f6; font-size: 16px; margin-top: 2px; }}
  .wear {{ flex: 0 0 auto; text-decoration: none; font-size: 10px; color: #8fb7d6;
          border: 1px solid #33455a; border-radius: 6px; padding: 2px 8px; margin-left: 8px; }}
  .wear.on {{ color: {ACCENT}; border-color: {ACCENT}66; background: {ACCENT}18; }}

  .placeholder {{ text-align: center; padding: 36px 10px; }}
  .ph-ico {{ font-size: 34px; margin-bottom: 10px; }}
  .ph-title {{ font-size: 1.1em; font-weight: 700; color: #e6e9f6; margin-bottom: 8px; }}
  .placeholder p {{ color: #8b93b8; max-width: 440px; margin: 0 auto; line-height: 1.6; }}

  /* footer nav (flex with margins, no gap) */
  .foot {{ display: flex; align-items: center; }}
  .foot-mid {{ flex: 1; text-align: center; }}
  .foot-hint {{ color: #6b7290; font-size: 11.5px; font-style: italic; }}
  .nav-btn {{ text-decoration: none; padding: 9px 20px; border-radius: 8px; font-weight: 700;
             font-size: 12.5px; background: #23263a; border: 1px solid #383c52; color: #c8cad8; }}
  .nav-btn:hover {{ border-color: {ACCENT}66; }}
  .nav-btn.primary {{ background: {ACCENT}; border-color: {ACCENT}; color: #1a1c26; }}
  .nav-btn.off {{ opacity: .38; pointer-events: none; }}

  /* PHB reference links (folded in from the old walkthrough) — now a boxed panel
     that lives in the pinned side rail alongside the character overview. */
  .phb-refs {{ background: #191b25; border: 1px solid #2a2e3e; border-radius: 10px;
              padding: 12px 14px; }}
  .phb-refs-label {{ display: block; color: #5a6080; font-size: 10px; font-weight: 700;
                     letter-spacing: .09em; text-transform: uppercase; margin-bottom: 8px; }}
  .phb-ref {{ display: inline-flex; align-items: center; margin: 0 7px 7px 0;
              background: #1c1f32; border: 1px solid {ACCENT}55; border-radius: 6px;
              padding: 5px 10px 5px 6px; color: #c2aa68; text-decoration: none;
              font-size: 11px; font-weight: 600; line-height: 1; white-space: nowrap; }}
  .phb-ref:hover {{ background: {ACCENT}18; border-color: {ACCENT}; color: {ACCENT}; }}
  .phb-ref .phb-badge {{ margin-right: 7px; background: #7a6020; color: #f0dca0;
                         font-size: 8px; font-weight: 800; border-radius: 3px; padding: 3px 4px;
                         line-height: 1; letter-spacing: .06em; }}
  /* in-app references (Codex of Worldly Craft, Spell Compendium) — blue, not gold */
  .phb-ref.app {{ border-color: #35506b; color: #9fc0dc; }}
  .phb-ref.app:hover {{ background: #5b9bd518; border-color: #5b9bd5; color: #cfe4f6; }}
  .phb-ref.app .phb-badge {{ background: #2f4a63; color: #cfe4f6; }}
  /* Combat & Tactics — crimson, so a C&T rule never reads as core PHB */
  .phb-ref.ct {{ border-color: #6b3540; color: #dc9fa8; }}
  .phb-ref.ct:hover {{ background: #d55b6b18; border-color: #d55b6b; color: #f6cfd5; }}
  .phb-ref.ct .phb-badge {{ background: #632f3a; color: #f6cfd5; }}
"""

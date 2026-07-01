"""actionsscreen_html.py — Generates the Player Actions quick-reference HTML."""
from html import escape as e

from screen_common import page

CAT_COLORS = {
    "offense":  "#e05555",
    "defense":  "#5b9bd5",
    "forced":   "#e07b2a",
    "movement": "#4db870",
    "other":    "#a76bcc",
}

CAT_LABELS = {
    "offense":  "Offense",
    "defense":  "Defense",
    "forced":   "Forced Movement",
    "movement": "Movement",
    "other":    "Other Actions",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _rules(items):
    """Render a list of rule strings as styled bullet rows."""
    rows = "".join(f'<div class="rule-row">{e(item)}</div>' for item in items)
    return f'<div class="rule-list">{rows}</div>'


def _tbl(headers, rows, right_cols=()):
    head = "".join(
        f'<th class="r">{e(h)}</th>' if i in right_cols else f"<th>{e(h)}</th>"
        for i, h in enumerate(headers)
    )
    body = ""
    for row in rows:
        cells = "".join(
            f'<td class="r">{e(str(v))}</td>' if i in right_cols else f"<td>{e(str(v))}</td>"
            for i, v in enumerate(row)
        )
        body += f"<tr>{cells}</tr>\n"
    return f'<div class="tscroll"><table><thead><tr>{head}</tr></thead><tbody>\n{body}</tbody></table></div>'


def _note(text):
    return f'<p class="note">{e(text)}</p>'


def _card(title, cat, content, span=1):
    col = CAT_COLORS[cat]
    span_cls = f" span-{span}" if span > 1 else ""
    return (
        f'<div class="card {cat}{span_cls}" data-cat="{cat}" data-title="{e(title.lower())}">'
        f'<div class="card-head" style="border-left:3px solid {col}">'
        f'<span class="cat-dot" style="background:{col}"></span>'
        f'<span class="card-title">{e(title)}</span></div>'
        f'<div class="card-body">{content}</div></div>\n'
    )


# ── Offense ────────────────────────────────────────────────────────────────────

def _melee_attack():
    return _card("Attack — Melee", "offense", _rules([
        "Move up to half speed before OR after attacking (not both)",
        "Charge: move up to 150% speed before attacking",
        "Charging: +2 to hit, −1 AC for the round, lose Dex bonus to AC",
    ]))


def _non_lethal():
    return _card("Attack — Non-Lethal", "offense", _rules([
        "Must use an appropriate weapon (blunt, pommel, etc.)",
        "−4 to hit penalty",
        "Inflict half the rolled damage",
        "¼ of total damage is real; the remainder is temporary",
    ]))


def _sap():
    return _card("Sap (Knockout)", "offense", _rules([
        "Provokes an attack of opportunity",
        "−8 to hit if target is wearing a helmet",
        "5% chance to knock out per point of damage dealt (max 40%)",
        "Double KO chances if target is surprised, restrained, or held",
        "Can only target creatures your own size or smaller whose head you can reach",
    ]))


def _missile_attack():
    return _card("Attack — Missile", "offense", _rules([
        "Full rate of fire if you do not move this round",
        "Half rate of fire if you move up to half speed",
        "Firing into melee: −4 to hit OR randomly determine the target among all combatants",
    ]))


def _spell_casting():
    return _card("Spell Casting", "offense", _rules([
        "No movement except a 5-foot step (taken before or after casting)",
        "Any hit or failed concentration check interrupts the spell",
        "Spell is lost if interrupted — the slot is still expended",
    ]))


# ── Defense ───────────────────────────────────────────────────────────────────

def _guard():
    return _card("Guard / Hold Your Ground", "defense", _rules([
        "Move up to half speed before holding your position",
        "Strike first when an enemy enters your reach (regardless of initiative)",
        "Limited to 1 attack (2 if dual wielding) while guarding",
    ]))


def _parry():
    return _card("Parry", "defense", _rules([
        "Gain an AC bonus equal to half your level",
        "Warriors gain an additional +1 to the parry bonus",
        "No movement except a single 5-foot step",
        "You make no attacks while parrying",
    ]))


def _withdraw():
    return _card("Withdraw", "defense", _rules([
        "Move up to half speed away from enemies",
        "Does not provoke attacks of opportunity as long as you move away",
        "Turning and running (full speed) DOES provoke AoOs",
    ]))


# ── Forced Movement ───────────────────────────────────────────────────────────

def _shove():
    return _card("Shove", "forced", _rules([
        "Make an attack roll vs. the target's touch AC",
        "On a hit, both combatants make opposed Strength vs. Strength or Dexterity checks",
        "Success: target is pushed back 5 feet",
        "If unarmed, the attempt provokes an AoO at +4 to hit and damage against you",
    ]))


def _knockdown():
    return _card("Knock Down / Overbear / Dog Pile", "forced", _rules([
        "Defender gets attacks of opportunity before the attempt resolves",
        "Attack vs. touch AC using the best attack bonus in the group",
        "+1 to hit per additional attacker joining the pile",
        "On a hit: opposed STR checks — use the highest Strength in the attacking group",
        "±4 per size category difference between attacker and defender",
        "+1 to attacker's check per additional attacker",
        "−4 to attacker's check if defender has more than 2 legs",
    ]))


# ── Movement ──────────────────────────────────────────────────────────────────

def _movement_table():
    rows = [
        ["Combat",  "10× MV (ft)",  "None — full tactical options available"],
        ["Walk",    "10× MV (yd)",  "−1 AC, no Dex bonus to AC; −1 to own surprise, +1 to enemy surprise; cannot notice traps or secrets"],
        ["Jog",     "20× MV (yd)",  "As Walk. Sustainable for Con rounds; Constitution check each round after that"],
        ["Run",     "30× MV (yd)",  "As Jog. Strength check to begin running; Con check each round with cumulative −1 penalty"],
        ["Sprint",  "40× MV (yd)",  "As Run. Strength check at −4 to begin; Con check each round with cumulative −2 penalty"],
    ]
    note = _note("MV = base movement rate (e.g., MV 12 = 12 ft/rd combat, 12 yd/rd walk). "
                 "Failed Con check ends that tier of speed; the character drops to the next lower tier.")
    return _card("Movement Speeds", "movement", _tbl(["Speed", "Distance/Round", "Penalties & Notes"], rows) + note, span=3)


# ── Other ──────────────────────────────────────────────────────────────────────

def _cover_blade():
    return _card("Cover with Bow / Hold Blade to Target", "other", _rules([
        "Ready an attack with +2 to hit and a critical hit on a roll of 16+",
        "Target must be stunned, dazed, pinned, unconscious, surprised, or otherwise unable to resist",
        "Melee weapons automatically win initiative in this situation",
        "Missile weapons roll initiative normally with no modifier",
    ]))


def _ready_action():
    return _card("Ready an Action", "other", _rules([
        "Declare before initiative: ready 1 attack (2 if dual wielding), one item usage, or one movement",
        "You may move before readying, but doing so limits what movement you can ready",
        "The readied action triggers on a specified condition before your normal turn",
        "If the condition never occurs, the action is lost",
    ]))


def _use_magic_item():
    return _card("Use a Magic Item", "other", _rules([
        "No movement other than a 5-foot step",
        "May provoke an attack of opportunity if the item must be retrieved from an inaccessible location",
        "Wands, rods, staves, and rings generally activate as a free action unless stated otherwise",
    ]))


# ── Assemble ───────────────────────────────────────────────────────────────────

def generate() -> str:
    cat_buttons = "".join(
        f'<button class="cat-btn" data-cat="{k}" onclick="filterCat(\'{k}\')" '
        f'style="border-bottom:3px solid {v}">{label}</button>'
        for k, v in CAT_COLORS.items()
        for label in [CAT_LABELS[k]]
    )

    sections = [
        # Offense
        _melee_attack(), _non_lethal(), _sap(),
        _missile_attack(), _spell_casting(),
        # Defense
        _guard(), _parry(), _withdraw(),
        # Forced Movement
        _shove(), _knockdown(),
        # Movement
        _movement_table(),
        # Other
        _cover_blade(), _ready_action(), _use_magic_item(),
    ]

    # Screen-specific styling on top of screen_common.COMMON_CSS.
    css_extra = """
      td { line-height: 1.5; }
      td:first-child { font-weight: 600; white-space: nowrap; }
      td:nth-child(2) { white-space: nowrap; }
      .rule-list { display: flex; flex-direction: column; gap: 4px; }
      .rule-row { display: flex; gap: 8px; align-items: baseline;
                  padding: 5px 8px; border-radius: 4px;
                  font-size: 12px; line-height: 1.55; color: #c0c4d8; }
      .rule-row::before { content: "▸"; color: #44506a; flex-shrink: 0; font-size: 10px; }
      .rule-row:nth-child(odd) { background: #1e2138; }
    """

    grid_html = '<div class="grid">\n' + "".join(sections) + '</div>'
    return page(
        "Actions Screen — AD&D 2nd Edition",
        css_extra, cat_buttons, grid_html,
        "Search actions, rules, penalties…",
    )

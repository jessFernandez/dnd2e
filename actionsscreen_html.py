"""actionsscreen_html.py — the Player Actions quick-reference screen.

A fast-lookup combat reference: every action is a collapsible row showing its
name and a one-line gist; click (or search) to expand the full rules. Grouped by
category, with a sticky search box + category filter. Typing in the search box
auto-expands the matching rows so you can read the rules without a second click.

Self-contained (own skeleton/CSS/JS): unlike the DM screen it is a list, not a
masonry card grid, so it does not use screen_common. All spacing is margin-based
because QtWebEngine (the app's bundled Chromium) silently ignores flexbox `gap`.
"""
from html import escape as e

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

# Each action: (category, title, one-line gist, [full rules]).
ACTIONS = [
    ("offense", "Attack — Melee", "Move ½ speed before OR after — or charge", [
        "Move up to half speed before OR after attacking (not both)",
        "Charge: move up to 150% speed before attacking",
        "Charging: +2 to hit, −1 AC for the round, lose Dex bonus to AC",
    ]),
    ("offense", "Attack — Non-Lethal", "−4 to hit, deal half damage", [
        "Must use an appropriate weapon (blunt, pommel, etc.)",
        "−4 to hit penalty",
        "Inflict half the rolled damage",
        "¼ of total damage is real; the remainder is temporary",
    ]),
    ("offense", "Sap (Knockout)", "Chance to knock out on a head hit", [
        "Provokes an attack of opportunity",
        "−8 to hit if target is wearing a helmet",
        "5% chance to knock out per point of damage dealt (max 40%)",
        "Double KO chances if target is surprised, restrained, or held",
        "Can only target creatures your own size or smaller whose head you can reach",
    ]),
    ("offense", "Attack — Missile", "Rate of fire depends on how far you move", [
        "Full rate of fire if you do not move this round",
        "Half rate of fire if you move up to half speed",
        "Firing into melee: −4 to hit OR randomly determine the target among all combatants",
    ]),
    ("offense", "Spell Casting", "No movement but a 5-ft step; interruptible", [
        "No movement except a 5-foot step (taken before or after casting)",
        "Any hit or failed concentration check interrupts the spell",
        "Spell is lost if interrupted — the slot is still expended",
    ]),

    ("defense", "Guard / Hold Your Ground", "Strike first when an enemy closes", [
        "Move up to half speed before holding your position",
        "Strike first when an enemy enters your reach (regardless of initiative)",
        "Limited to 1 attack (2 if dual wielding) while guarding",
    ]),
    ("defense", "Parry", "+½ your level to AC; make no attacks", [
        "Gain an AC bonus equal to half your level",
        "Warriors gain an additional +1 to the parry bonus",
        "No movement except a single 5-foot step",
        "You make no attacks while parrying",
    ]),
    ("defense", "Withdraw", "Back away ½ speed without provoking AoOs", [
        "Move up to half speed away from enemies",
        "Does not provoke attacks of opportunity as long as you move away",
        "Turning and running (full speed) DOES provoke AoOs",
    ]),

    ("forced", "Shove", "Push a foe back 5 feet", [
        "Make an attack roll vs. the target's touch AC",
        "On a hit, both combatants make opposed Strength vs. Strength or Dexterity checks",
        "Success: target is pushed back 5 feet",
        "If unarmed, the attempt provokes an AoO at +4 to hit and damage against you",
    ]),
    ("forced", "Knock Down / Overbear / Dog Pile", "Gang up to knock a target prone", [
        "Defender gets attacks of opportunity before the attempt resolves",
        "Attack vs. touch AC using the best attack bonus in the group",
        "+1 to hit per additional attacker joining the pile",
        "On a hit: opposed STR checks — use the highest Strength in the attacking group",
        "±4 per size category difference between attacker and defender",
        "+1 to attacker's check per additional attacker",
        "−4 to attacker's check if defender has more than 2 legs",
    ]),

    ("other", "Cover with Bow / Hold Blade to Target", "Readied strike vs. a helpless foe", [
        "Ready an attack with +2 to hit and a critical hit on a roll of 16+",
        "Target must be stunned, dazed, pinned, unconscious, surprised, or otherwise unable to resist",
        "Melee weapons automatically win initiative in this situation",
        "Missile weapons roll initiative normally with no modifier",
    ]),
    ("other", "Ready an Action", "Trigger an action on a chosen condition", [
        "Declare before initiative: ready 1 attack (2 if dual wielding), one item usage, or one movement",
        "You may move before readying, but doing so limits what movement you can ready",
        "The readied action triggers on a specified condition before your normal turn",
        "If the condition never occurs, the action is lost",
    ]),
    ("other", "Use a Magic Item", "Activate an item; no move but a 5-ft step", [
        "No movement other than a 5-foot step",
        "May provoke an attack of opportunity if the item must be retrieved from an inaccessible location",
        "Wands, rods, staves, and rings generally activate as a free action unless stated otherwise",
    ]),
]

# The Movement action is a small table rather than a bullet list.
_MOVE_ROWS = [
    ("Combat", "10× MV (ft)", "None — full tactical options available"),
    ("Walk",   "10× MV (yd)", "−1 AC, no Dex bonus to AC; −1 to own surprise, +1 to enemy surprise; cannot notice traps or secrets"),
    ("Jog",    "20× MV (yd)", "As Walk. Sustainable for Con rounds; Constitution check each round after that"),
    ("Run",    "30× MV (yd)", "As Jog. Strength check to begin running; Con check each round with cumulative −1 penalty"),
    ("Sprint", "40× MV (yd)", "As Run. Strength check at −4 to begin; Con check each round with cumulative −2 penalty"),
]
_MOVE_NOTE = ("MV = base movement rate (e.g., MV 12 = 12 ft/rd combat, 12 yd/rd walk). "
              "A failed Con check ends that tier of speed; the character drops to the next lower tier.")


# ── Rendering ────────────────────────────────────────────────────────────────

def _summary(title, gist):
    return (
        f'<summary>'
        f'<span class="chev">▸</span>'
        f'<span class="act-name">{e(title)}</span>'
        f'<span class="act-gist">{e(gist)}</span>'
        f'</summary>'
    )


def _action(cat, title, gist, rules):
    lis = "".join(f"<li>{e(r)}</li>" for r in rules)
    return (
        f'<details class="act" data-cat="{cat}" data-title="{e(title.lower())}" '
        f'style="--c:{CAT_COLORS[cat]}">'
        f'{_summary(title, gist)}'
        f'<div class="act-body"><ul class="rules">{lis}</ul></div>'
        f'</details>'
    )


def _movement_action():
    body_rows = "".join(
        f'<tr><td class="mv-speed">{e(s)}</td><td class="mv-dist">{e(d)}</td>'
        f'<td>{e(n)}</td></tr>'
        for s, d, n in _MOVE_ROWS
    )
    table = (
        '<div class="tscroll"><table>'
        '<thead><tr><th>Speed</th><th>Distance / Round</th><th>Penalties &amp; Notes</th></tr></thead>'
        f'<tbody>{body_rows}</tbody></table></div>'
        f'<p class="note">{e(_MOVE_NOTE)}</p>'
    )
    return (
        f'<details class="act" data-cat="movement" data-title="movement speeds" '
        f'style="--c:{CAT_COLORS["movement"]}">'
        f'{_summary("Movement Speeds", "Combat · Walk · Jog · Run · Sprint")}'
        f'<div class="act-body">{table}</div>'
        f'</details>'
    )


def _sections():
    """One titled section per category, in CAT_COLORS order."""
    by_cat: dict = {}
    for cat, title, gist, rules in ACTIONS:
        by_cat.setdefault(cat, []).append(_action(cat, title, gist, rules))
    by_cat.setdefault("movement", []).insert(0, _movement_action())

    out = []
    for cat in CAT_COLORS:
        items = by_cat.get(cat)
        if not items:
            continue
        out.append(
            f'<section class="cat-section" data-cat="{cat}" style="--c:{CAT_COLORS[cat]}">'
            f'<div class="cat-header"><span class="cat-name">{e(CAT_LABELS[cat])}</span>'
            f'<span class="cat-count">{len(items)}</span></div>'
            f'<div class="act-list">{"".join(items)}</div>'
            f'</section>'
        )
    return "".join(out)


def _cat_buttons():
    return "".join(
        f'<button class="cat-btn" data-cat="{k}" onclick="filterCat(\'{k}\')" '
        f'style="border-bottom:3px solid {v}">{e(CAT_LABELS[k])}</button>'
        for k, v in CAT_COLORS.items()
    )


_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a1c26; font-family: "Segoe UI", system-ui, sans-serif;
         font-size: 12px; color: #c8cad8; }

  /* ── Sticky search + category filter ── */
  .top-bar { position: sticky; top: 0; z-index: 100; background: #13151f;
             border-bottom: 1px solid #2a2d3e; padding: 10px 14px; }
  .search-row { display: flex; align-items: center; margin-bottom: 8px; }
  #search { flex: 1; background: #23263a; border: 1px solid #383c52; border-radius: 6px;
            color: #e0e2f0; padding: 8px 12px; font-size: 13px; outline: none; }
  #search:focus { border-color: #c9a84c; }
  #clear-btn { margin-left: 8px; background: #23263a; border: 1px solid #383c52;
               border-radius: 6px; color: #9ca3c0; padding: 7px 12px; cursor: pointer; font-size: 12px; }
  #clear-btn:hover { background: #2d3048; }
  .cat-row { display: flex; flex-wrap: wrap; }
  .cat-btn, #all-btn { background: #23263a; border: 1px solid #383c52; border-radius: 5px;
                       color: #c8cad8; padding: 4px 10px; cursor: pointer; font-size: 11px;
                       font-weight: 600; letter-spacing: .04em; transition: background .1s;
                       margin: 0 6px 0 0; }
  #all-btn { border-bottom: 3px solid #8891b5; }
  .cat-btn:hover, .cat-btn.active,
  #all-btn:hover, #all-btn.active { background: #2d3048; }

  /* ── Category sections ── */
  .screen { padding: 14px 0 32px; }
  .cat-section { margin: 0 14px 22px; }
  .cat-header { display: flex; align-items: center; margin: 0 0 10px; padding-bottom: 7px;
                border-bottom: 2px solid var(--c); }
  .cat-header::before { content: ""; width: 9px; height: 9px; border-radius: 2px;
                        background: var(--c); flex-shrink: 0; margin-right: 9px; }
  .cat-name { font-size: 12.5px; font-weight: 800; letter-spacing: .09em;
              text-transform: uppercase; color: #e6e9f6; }
  .cat-count { margin-left: auto; font-size: 10.5px; font-weight: 700; color: #8891b5;
               background: #1c1f32; border: 1px solid #2a2e45; border-radius: 9px; padding: 1px 8px; }

  /* ── Collapsible action rows ── */
  .act { background: #21243a; border: 1px solid #2a2e45; border-left: 3px solid var(--c);
         border-radius: 7px; margin-bottom: 7px; overflow: hidden; }
  .act[open] { background: #23263c; }
  summary { display: flex; align-items: baseline; padding: 9px 12px; cursor: pointer;
            list-style: none; user-select: none; }
  summary::-webkit-details-marker { display: none; }
  summary:hover { background: #262a40; }
  .chev { color: var(--c); font-size: 10px; flex-shrink: 0; margin-right: 10px;
          transform: translateY(-1px); transition: transform .15s ease; }
  .act[open] .chev { transform: translateY(-1px) rotate(90deg); }
  .act-name { font-size: 13px; font-weight: 700; color: #e6e9f6; flex-shrink: 0; }
  .act-gist { margin-left: 12px; color: #8891b5; font-size: 11.5px; font-style: italic;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .act[open] .act-gist { color: #6b7290; }

  .act-body { padding: 2px 14px 12px 34px; }
  .rules { list-style: none; }
  .rules li { position: relative; padding: 4px 0 4px 15px; font-size: 12px; line-height: 1.55;
              color: #c4c8dc; }
  .rules li::before { content: "▸"; position: absolute; left: 0; top: 4px;
                      color: #44506a; font-size: 10px; }

  /* Movement table (only used inside the Movement row) */
  .tscroll { overflow-x: auto; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
  th { background: #17192a; color: #a0a8cc; font-size: 10px; font-weight: 700; letter-spacing: .06em;
       text-transform: uppercase; padding: 5px 8px; text-align: left; white-space: nowrap;
       border-bottom: 1px solid #2a2e45; }
  td { padding: 6px 8px; border-bottom: 1px solid #23263a; color: #c0c4d8; vertical-align: top; line-height: 1.5; }
  tr:hover td { background: #262a40; }
  td.mv-speed { font-weight: 700; color: #e0e2f0; white-space: nowrap; }
  td.mv-dist { white-space: nowrap; color: #b6d8c2; }
  .note { color: #5a6080; font-size: 10.5px; font-style: italic; margin-top: 8px; line-height: 1.5; }

  .empty { color: #5a6080; font-style: italic; text-align: center; padding: 40px 0; display: none; }
"""

_SCRIPT = """
  const search = document.getElementById('search');
  const sections = Array.from(document.querySelectorAll('.cat-section'));
  const empty = document.getElementById('empty');
  let activeCat = 'all';

  function apply() {
    const q = search.value.trim().toLowerCase();
    let anyAll = false;
    for (const sec of sections) {
      const catOK = (activeCat === 'all' || activeCat === sec.dataset.cat);
      let any = false;
      for (const act of sec.querySelectorAll('.act')) {
        const match = catOK && (!q
          || act.dataset.title.includes(q)
          || act.textContent.toLowerCase().includes(q));
        act.style.display = match ? '' : 'none';
        act.open = !!q && match;          // searching expands matches so rules are visible
        if (match) any = true;
      }
      sec.style.display = any ? '' : 'none';
      if (any) anyAll = true;
    }
    empty.style.display = anyAll ? 'none' : 'block';
  }

  function filterCat(cat) {
    activeCat = cat;
    document.querySelectorAll('.cat-btn, #all-btn').forEach(b => b.classList.remove('active'));
    const el = cat === 'all'
      ? document.getElementById('all-btn')
      : document.querySelector(`.cat-btn[data-cat="${cat}"]`);
    if (el) el.classList.add('active');
    apply();
  }

  search.addEventListener('input', apply);
  document.getElementById('clear-btn').addEventListener('click', () => {
    search.value = ''; apply(); search.focus();
  });
  document.getElementById('all-btn').classList.add('active');
"""


def generate() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Actions Screen — AD&D 2nd Edition</title>
<style>{_CSS}</style>
</head>
<body>
<div class="top-bar">
  <div class="search-row">
    <input id="search" type="text" placeholder="Search actions, rules, penalties…" autocomplete="off">
    <button id="clear-btn">Clear</button>
  </div>
  <div class="cat-row">
    <button id="all-btn" onclick="filterCat('all')">All</button>
    {_cat_buttons()}
  </div>
</div>
<div class="screen">
{_sections()}
<div class="empty" id="empty">No actions match your search.</div>
</div>
<script>{_SCRIPT}</script>
</body>
</html>"""

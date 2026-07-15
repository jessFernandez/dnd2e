"""dmscreen_html.py — Generates the DM Quick Reference Screen HTML."""
from html import escape as e

import char_rules as cr
from screen_common import page, render_sections

CAT_COLORS = {
    "combat":      "#e05555",
    "encounter":   "#e07b2a",
    "hazards":     "#a76bcc",
    "exploration": "#4db870",
    "abilities":   "#5b9bd5",
    "classes":     "#3dbfa8",
}

CAT_LABELS = {
    "combat":      "Combat",
    "encounter":   "Encounter",
    "hazards":     "Hazards",
    "exploration": "Exploration",
    "abilities":   "Abilities",
    "classes":     "Classes & Spells",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _t(headers, rows, right_cols=()):
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


# ── Combat ────────────────────────────────────────────────────────────────────

def _opportunity_attacks():
    return _card("Opportunity Attacks", "combat", _t(
        ["Character", "AoO / Round"],
        [["Warriors", "3 + 1/5 levels"],
         ["Others",   "1 + 1/5 levels"],
         ["Monsters", "3 + 1/5 HD"]],
    ))


def _morale():
    rows = [
        ["Allies: Outnumber opponents 3:1", "+2"],
        ["Allies: Spellcaster ally", "+2"],
        ["Allies: Leader of different alignment", "-1"],
        ["Allies: Lost 25% of hp or group", "-2"],
        ["Allies: Lost 50% of hp or group", "-4"],
        ["Allies: Most powerful ally killed", "-4"],
        ["Allies: Abandoned by friends", "-6"],
        ["Enemies: Fighting hated enemy", "+4"],
        ["Enemies: Opposes spellcasters", "-2"],
        ["Enemies: No enemy slain", "-2"],
        ["Enemies: Outnumbered 3:1", "-4"],
        ["Enemies: Unable to affect opponent", "-8"],
        ["Misc: Defending home", "+3"],
        ["Misc: NPC has been favored", "+2"],
        ["Misc: Defensive terrain advantage", "+1"],
        ["Misc: Each extra check in a round", "-1"],
        ["Misc: Was surprised", "-2"],
        ["Misc: NPC has been treated poorly", "-4"],
    ]
    return _card("Morale Modifiers", "combat", _t(["Situation", "Adj"], rows, right_cols=(1,)))


def _hit_dice_immunity():
    return _card("Hit Dice vs. Immunity", "combat", _t(
        ["Hit Dice", "Hits as if using"],
        [["4+1 or more", "+1 weapon"],
         ["6+2 or more", "+2 weapon"],
         ["8+3 or more", "+3 weapon"],
         ["10+4 or more", "+4 weapon"]],
    ))


def _weapon_vs_armor():
    rows = [
        ["Banded mail",     "+2", "0",  "+1"],
        ["Brigandine",      "+1", "+1", "0"],
        ["Chain mail",      "+2", "0",  "-2"],
        ["Field plate",     "+3", "+1", "0"],
        ["Full plate",      "+4", "+3", "0"],
        ["Leather armor",   "0",  "-2", "0"],
        ["Plate mail",      "+3", "0",  "0"],
        ["Ring mail",       "+1", "+1", "0"],
        ["Scale mail",      "0",  "+1", "0"],
        ["Splint mail",     "0",  "+1", "+2"],
        ["Studded leather", "+2", "+1", "0"],
    ]
    return _card("Weapon Type vs. Armor", "combat",
                 _t(["Armor Type", "Slash", "Pierce", "Bludg."], rows, right_cols=(1,2,3)), span=2)


def _combat_modifiers():
    rows = [
        ["Attacker on higher ground", "+1"],
        ["Back attack", "+2"],
        ["Flank attack", "+1"],
        ["Charging", "+2"],
        ["Low light", "-1"],
        ["Starlight", "-3"],
        ["No light / Invisible", "-4"],
        ["Target off balance", "+2"],
        ["Target sleeping or held", "Auto"],
        ["Target sitting or kneeling", "+2"],
        ["Target stunned or prone", "+4"],
        ["(Missile) Target sitting/kneeling", "-2"],
        ["(Missile) Target prone", "-4"],
        ["(Missile) Medium Range", "-2"],
        ["(Missile) Long Range", "-5"],
    ]
    return _card("Combat Attack Modifiers", "combat", _t(["Situation", "Adj"], rows, right_cols=(1,)))


def _ac_modifiers():
    rows = [
        ["Total darkness", "-4"],
        ["Starlight or dense fog", "-2"],
        ["Moonlight or moderate fog", "-1"],
        ["Charged this round", "-1"],
        ["Was surprised", "-1"],
    ]
    return _card("AC Modifiers", "combat", _t(["Situation", "Adj"], rows, right_cols=(1,)))


def _cover():
    return _card("Cover & Concealment", "combat", _t(
        ["Hidden %", "Cover", "Conceal"],
        [["25%", "-2", "-1"],
         ["50%", "-4", "-2"],
         ["75%", "-7", "-3"],
         ["90%", "-10", "-4"]],
        right_cols=(1, 2),
    ))


def _initiative_actions():
    # Size rows are sourced from char_rules so the DM Screen and the monster sheet
    # can't disagree; S and M share a value, shown as one "Small/Medium" row.
    m = cr.SIZE_INITIATIVE_MODIFIER
    def _sign(v):
        return "0" if v == 0 else f"+{v}"
    rows = [
        ["Movement: Tiny", _sign(m["T"])],
        ["Movement: Small/Medium", _sign(m["M"])],
        ["Movement: Large", _sign(m["L"])],
        ["Movement: Huge", _sign(m["H"])],
        ["Movement: Gargantuan", _sign(m["G"])],
        ["Breath weapon", "+1"],
        ["Rod", "+1"],
        ["Staff", "+2"],
        ["Ring, wand, misc. magic", "+3"],
        ["Innate spell ability", "+3"],
        ["Potion", "+4"],
    ]
    return _card("Initiative Modifiers", "combat", _t(["Action", "Adj"], rows, right_cols=(1,)))


def _initiative_situations():
    rows = [
        ["Hasted", "-2"],
        ["Set to receive charge", "-2"],
        ["On higher ground", "-1"],
        ["Preoccupied / Focused", "+2"],
        ["Slowed", "+2"],
        ["Wading, slippery footing", "+2"],
        ["Hindered (tangled, climbing)", "+3"],
        ["Wading in deep water", "+4"],
        ["Foreign environment / drunk", "+6"],
    ]
    return _card("Initiative: Situations", "combat", _t(["Situation", "Adj"], rows, right_cols=(1,)))


def _warrior_attacks():
    return _card("Warrior Melee Attacks", "combat", _t(
        ["Warrior Level", "Attacks/Round"],
        [["1–6", "1 / round"],
         ["7–12", "3/2 rounds"],
         ["13+", "2 / round"]],
    ))


def _specialist_attacks():
    rows = [
        ["1–6",  "3/2", "1/1", "1/2", "3/1", "4/1", "3/2"],
        ["7–12", "2/1", "3/2", "1/1", "4/1", "5/1", "2/1"],
        ["13+",  "5/2", "2/1", "3/2", "5/1", "6/1", "5/2"],
    ]
    return _card("Specialist Attacks/Round", "combat", _t(
        ["Level", "Melee", "Lt X-bow", "Hvy X-bow", "Dagger", "Dart", "Other Missile"],
        rows,
    ), span=2)


def _thac0_by_level():
    levels = list(range(1, 21))
    data = {
        "Warrior": [20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1],
        "Priest":  [20,20,19,18,18,17,16,16,15,14,14,13,12,12,11,10,10,9,8,8],
        "Rogue":   [20,20,19,19,18,18,17,17,16,16,15,15,14,14,13,13,12,12,11,11],
        "Wizard":  [20,20,20,19,19,19,18,18,18,17,17,17,16,16,16,15,15,15,14,14],
    }
    return _card("THAC0 by Level", "combat", _t(
        ["Lvl", "Warrior", "Priest", "Rogue", "Wizard"],
        [[str(i+1)] + [str(data[cls][i]) for cls in data] for i in range(20)],
        right_cols=(1,2,3,4),
    ), span=2)


def _monster_thac0():
    pairs = [
        ("½–", 20), ("1–1", 20), ("1", 19), ("2", 19), ("3", 17), ("4", 17),
        ("5", 15), ("6", 15), ("7", 13), ("8", 13), ("9", 11), ("10", 11),
        ("11", 9), ("12", 9), ("13", 7), ("14", 7), ("15", 5), ("16", 5),
        ("17", 4), ("18", 4), ("19–20", 3),
    ]
    return _card("Monster THAC0 by HD", "combat", _t(
        ["HD", "THAC0"],
        [[hd, str(thac0)] for hd, thac0 in pairs],
        right_cols=(1,),
    ))


def _turning_undead():
    headers = ["Undead Type / HD", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10–11", "12–13", "14+"]
    rows = [
        ["Skeleton or 1 HD", "10","7","4","T","T","D","D","D*","D*","D*","D*","D*"],
        ["Zombie",           "13","10","7","4","T","T","D","D","D*","D*","D*","D*"],
        ["Ghoul or 2 HD",    "16","13","10","7","4","T","T","D","D","D*","D*","D*"],
        ["Shadow or 3–4 HD", "19","16","13","10","7","4","T","T","D","D","D*","D*"],
        ["Wight or 5 HD",    "20","19","16","13","10","7","4","T","T","D","D","D*"],
        ["Ghast",            "–","20","19","16","13","10","7","4","T","T","D","D"],
        ["Wraith or 6 HD",   "–","–","20","19","16","13","10","7","4","T","T","D"],
        ["Mummy or 7 HD",    "–","–","–","20","19","16","13","10","7","4","T","T"],
        ["Spectre or 8 HD",  "–","–","–","–","20","19","16","13","10","7","4","T"],
        ["Vampire or 9 HD",  "–","–","–","–","–","20","19","16","13","10","7","4"],
        ["Ghost or 10 HD",   "–","–","–","–","–","–","20","19","16","13","10","7"],
        ["Lich or 11+ HD",   "–","–","–","–","–","–","–","20","19","16","13","10"],
        ["Special",          "–","–","–","–","–","–","–","–","20","19","16","13"],
    ]
    note = '<p class="note">T = Turned automatically · D = Destroyed · D* = Destroyed + 2d6 turned · Cleric level shown as column header</p>'
    return _card("Turning Undead", "combat", _t(headers, rows) + note, span=3)


# ── Encounter ─────────────────────────────────────────────────────────────────

def _encounter_distance():
    rows = [
        ["Both groups surprised",      "3d6 ft."],
        ["One group surprised",        "4d6 ft."],
        ["Smoke or heavy fog",         "6d6 ft."],
        ["Jungle or dense forest",     "1d10 × 10 ft."],
        ["Light forest",               "2d6 × 10 ft."],
        ["Scrub, brush, or bush",      "2d12 × 10 ft."],
        ["Grassland, little cover",    "5d10 × 10 ft."],
        ["Nighttime or dungeon",       "Limit of sight"],
    ]
    return _card("Encounter Distance", "encounter", _t(["Terrain", "Range"], rows))


def _surprise():
    rows = [
        ["Extremely still",          "+2"],
        ["Rain",                     "-1"],
        ["Poor lighting",            "-1"],
        ["Heavy fog",                "-2"],
        ["Darkness",                 "-4"],
        ["PC Party: Suspicious",     "+2"],
        ["PC Party: Anticipating",   "+2"],
        ["PC Party: Fleeing",        "-2"],
        ["PC Party: Panicked",       "-2"],
        ["Other: Distinctive odor",  "+2"],
        ["Other: Every 10 members",  "+1"],
        ["Other: Camouflaged",       "–1 to –3"],
        ["Other: Silenced",          "-2"],
        ["Other: Invisible",         "-2"],
    ]
    return _card("Surprise Modifiers", "encounter", _t(["Situation", "Adj"], rows, right_cols=(1,)))


def _reactions():
    rows = [
        ["≤ 2", "Friendly",    "Friendly",    "Friendly",    "Flight"],
        ["3–5", "Friendly",    "Friendly",    "Friendly",    "Flight"],
        ["6–7", "Friendly",    "Indifferent", "Cautious",    "Cautious"],
        ["8",   "Indifferent", "Indifferent", "Cautious",    "Cautious"],
        ["9",   "Indifferent", "Indifferent", "Cautious",    "Threatening"],
        ["10–11","Indifferent","Indifferent", "Threatening", "Threatening"],
        ["12–15","Cautious",   "Cautious",    "Threatening", "Hostile"],
        ["16",  "Cautious",    "Cautious",    "Hostile",     "Hostile"],
        ["17–18","Threatening","Threatening", "Hostile",     "Hostile"],
        ["19+", "Hostile",     "Hostile",     "Hostile",     "Hostile"],
    ]
    return _card("Encounter Reactions (2d10)", "encounter",
                 _t(["Roll", "Friendly", "Indifferent", "Threatening", "Hostile"], rows), span=2)


def _wilderness_encounters():
    rows = [
        ["Plains",    "30%","5%","–","–","–"],
        ["Forest",    "75%","35%","10%","–","–"],
        ["Desert",    "30%","5%","–","–","–"],
        ["Hills",     "50%","10%","–","–","–"],
        ["Mountain",  "65%","20%","5%","–","–"],
        ["Swamp",     "95%","75%","45%","20%","5%"],
        ["Jungle",    "85%","45%","15%","–","–"],
        ["Ocean",     "20%","–","–","–","–"],
        ["Arctic",    "20%","–","–","–","–"],
    ]
    note = '<p class="note">Columns = number of encounters per check. Checks occur: dawn, midday, dusk, midnight, random.</p>'
    return _card("Wilderness Encounter Chance", "encounter",
                 _t(["Terrain", "1 enc.", "2 enc.", "3 enc.", "4 enc.", "5 enc."], rows,
                    right_cols=(1,2,3,4,5)) + note, span=2)


# ── Hazards ───────────────────────────────────────────────────────────────────

def _monster_strength():
    rows = [
        ["3",    "2","4","6","13","15","18"],
        ["4",    "3","5","7","14","17","18/01"],
        ["5",    "4","6","8","15","18","18/51"],
        ["6",    "5","7","9","16","18/01","18/76"],
        ["7",    "6","8","10","17","18/51","18/91"],
        ["8",    "7","9","11","18","18/76","18/00"],
        ["9–12", "8","10","12","18/01","18/91","19"],
        ["13",   "10","11","13","18/51","18/00","20"],
        ["14",   "11","12","14","18/76","19","21"],
        ["15",   "12","13","15","18/91","20","22"],
        ["16",   "13","14","16","18/00","21","23"],
        ["17",   "14","15","17","19","22","24"],
        ["18",   "15","16","18","20","23","25"],
    ]
    note = '<p class="note">Score = monster\'s listed strength. T/S/M/L/H/G = creature size.</p>'
    return _card("Monster Strength Scores", "hazards",
                 _t(["Score", "T", "S", "M", "L", "H", "G"], rows, right_cols=(1,2,3,4,5,6)) + note, span=2)


def _poison():
    rows = [
        ["A","Injected","10–30 min","15/0"],
        ["B","Injected","2–12 min","20/d3"],
        ["C","Injected","2–5 min","25/2d4"],
        ["D","Injected","1–2 min","30/2d6"],
        ["E","Injected","Immediate","Death/20"],
        ["F","Injected","Immediate","Death/0"],
        ["G","Ingested","2–12 hours","20/10"],
        ["H","Ingested","1–4 hours","20/10"],
        ["I","Ingested","1–2 min","30/15"],
        ["J","Ingested","1–4 min","Death/20"],
        ["K","Contact","2–8 min","5/0"],
        ["L","Contact","2–8 min","10/0"],
        ["M","Contact","1–4 min","20/5"],
        ["N","Contact","1 min","Death/25"],
        ["O","Injected","2–24 min","Paralytic"],
        ["P","Injected","1–3 hours","Debilitative"],
    ]
    note = '<p class="note">Strength = save target / damage on success (0 = none)</p>'
    return _card("Poison Strength", "hazards",
                 _t(["Class","Method","Onset","Strength"], rows) + note)


def _char_saves():
    rows = [
        ["Priest",  "1–3",   "10","14","13","16","15"],
        ["Priest",  "4–6",   "9","13","12","15","14"],
        ["Priest",  "7–9",   "7","11","10","13","12"],
        ["Priest",  "10–12", "6","10","9","12","11"],
        ["Priest",  "13–15", "5","9","8","11","10"],
        ["Priest",  "16–18", "4","8","7","10","9"],
        ["Priest",  "19+",   "2","6","5","8","7"],
        ["Rogue",   "1–4",   "13","14","12","16","15"],
        ["Rogue",   "5–8",   "12","12","11","15","13"],
        ["Rogue",   "9–12",  "11","10","10","14","11"],
        ["Rogue",   "13–16", "10","8","9","13","9"],
        ["Rogue",   "17–20", "9","6","8","12","7"],
        ["Rogue",   "21+",   "8","4","7","11","5"],
        ["Warrior", "0",     "16","18","17","20","19"],
        ["Warrior", "1–2",   "14","16","15","17","17"],
        ["Warrior", "3–4",   "13","15","14","16","16"],
        ["Warrior", "5–6",   "11","13","12","13","14"],
        ["Warrior", "7–8",   "10","12","11","12","13"],
        ["Warrior", "9–10",  "8","10","9","9","11"],
        ["Warrior", "11–12", "7","9","8","8","10"],
        ["Warrior", "13–14", "5","7","6","5","8"],
        ["Warrior", "15–16", "4","6","5","4","7"],
        ["Warrior", "17+",   "3","5","4","4","6"],
        ["Wizard",  "1–5",   "14","11","13","15","12"],
        ["Wizard",  "6–10",  "13","9","11","13","10"],
        ["Wizard",  "11–15", "11","7","9","11","8"],
        ["Wizard",  "16–20", "10","5","7","9","6"],
        ["Wizard",  "21+",   "8","3","5","7","4"],
    ]
    note = '<p class="note">PPD = Paralysis/Poison/Death · RSW = Rod/Staff/Wand · PP = Petrification/Polymorph · BW = Breath Weapon · Spell</p>'
    return _card("Character Saving Throws", "hazards",
                 _t(["Class","Level","PPD","RSW","PP","BW","Spell"], rows, right_cols=(2,3,4,5,6)) + note, span=2)


def _item_saves():
    rows = [
        ["Bone/Ivory",   "11","16","19","6","9","3","2","8","2"],
        ["Cloth",        "12","–","19","–","16","13","2","18","2"],
        ["Glass",        "5","20","19","14","7","4","6","17","2"],
        ["Leather",      "10","3","19","2","6","4","3","13","2"],
        ["Metal",        "13","7","17","3","6","2","2","12","2"],
        ["Oils",         "16","–","19","–","19","17","5","19","16"],
        ["Paper",        "16","7","19","–","19","19","2","19","2"],
        ["Potions",      "15","–","19","–","17","14","13","18","15"],
        ["Rock",         "3","17","18","8","3","2","2","14","2"],
        ["Rope",         "12","2","19","–","10","6","2","9","2"],
        ["Wood, thick",  "8","10","19","2","7","5","2","12","2"],
        ["Wood, thin",   "9","13","19","2","11","9","2","10","2"],
    ]
    return _card("Item Saving Throws", "hazards",
                 _t(["Item","Acid","Cr.Blow","Disint.","Fall","M.Fire","N.Fire","Cold","Bolt","Elect."],
                    rows, right_cols=tuple(range(1,10))), span=3)


def _item_hp():
    rows = [
        ["Ceramic Vessel",     "1–9",   "B/S"],
        ["Chain",              "4–32",  "S"],
        ["Glass Bottle",       "1–2",   "B"],
        ["Glass Pane",         "1",     "All"],
        ["Leather, Common",    "2–8",   "S/P"],
        ["Leather, Thick",     "3–12",  "S/P"],
        ["Rope",               "2–4",   "S"],
        ["Wood Chair",         "2–9",   "B/S"],
        ["Wooden Door, Thick", "30–50", "B/S"],
        ["Wooden Door, Med",   "10–30", "B/S"],
        ["Wooden Pole",        "2–12",  "B/S"],
        ["Wooden Table",       "10–20", "B/S"],
    ]
    return _card("Item Hit Points", "hazards",
                 _t(["Item", "HP", "Damage Mode"], rows, right_cols=(1,)))


# ── Exploration ───────────────────────────────────────────────────────────────

def _tracking():
    rows = [
        ["Soft or muddy ground",             "+4"],
        ["Thick brush / vines / reeds",      "+3"],
        ["Occasional signs, dust",           "+2"],
        ["Normal ground or wood floor",      "0"],
        ["Rocky ground or shallow water",    "–10"],
        ["Every 2 creatures in group",       "+1"],
        ["Every 12 hours since trail made",  "–1"],
        ["Every hour of rain/snow/sleet",    "–5"],
        ["Poor lighting (moon/starlight)",   "–6"],
        ["Tracked party hides trail",        "–5"],
        ["Non-ranger tracker",               "–6"],
    ]
    return _card("Tracking Modifiers", "exploration", _t(["Situation","Adj"], rows, right_cols=(1,)))


def _lock_quality():
    rows = [
        ["Wretched",  "+30%", "—"],
        ["Poor",      "+15%", "10 gp"],
        ["Good",      "0%",   "100 gp"],
        ["Excellent", "–20%", "500 gp"],
        ["Superior",  "–40%", "~3,000 gp"],
        ["Masterful", "–60%", "~30,000 gp"],
    ]
    note = '<p class="note">Modifier applied to Open Locks thief skill.</p>'
    return _card("Lock Quality", "exploration", _t(["Quality","Modifier","Cost"], rows) + note)


def _visibility():
    rows = [
        ["Clear sky",           "1,500","1,000","500","100","10"],
        ["Mist or light rain",  "1,000","500","250","30","10"],
        ["Twilight",            "500","300","150","30","10"],
        ["Night, full moon",    "100","50","30","10","5"],
        ["Fog, light / snow",   "500","200","100","30","10"],
        ["Fog, moderate",       "100","50","25","15","10"],
        ["Night, no moon",      "50","20","10","5","3"],
        ["Fog, dense / blizzard","10","10","5","5","3"],
    ]
    return _card("Visibility Ranges (yards)", "exploration",
                 _t(["Conditions","Movement","Spotted","Type ID","Full ID","Detail"],
                    rows, right_cols=(1,2,3,4,5)), span=2)


def _hear_noise():
    return _card("Chance to Hear Noise", "exploration", _t(
        ["Race", "Chance"],
        [["Dwarf","15% (3 in 20)"], ["Elf","20% (4 in 20)"],
         ["Gnome","25% (5 in 20)"], ["Half-elf","15% (3 in 20)"],
         ["Halfling","20% (4 in 20)"], ["Human","15% (3 in 20)"]],
    ))


def _detect_doors():
    note = '<p class="note">Elves & Half-Elves only. Passive (without searching).</p>'
    return _card("Detect Doors", "exploration", _t(
        ["Method","Hidden Door","Secret Door"],
        [["Passive (elf)","1 in 6","—"],
         ["Searching (elf)","3 in 6","2 in 6"]],
    ) + note)


def _getting_lost():
    rows = [
        ["Level, open ground", "10%"],
        ["Rolling ground",     "20%"],
        ["Lightly wooded",     "30%"],
        ["Wooded hills",       "40%"],
        ["Thick forest",       "70%"],
        ["Jungle",             "80%"],
        ["Mountainous",        "50%"],
        ["Swamp",              "60%"],
        ["Open sea",           "20%"],
    ]
    mods = [
        ["Landmark sighted",     "–15%"],
        ["Poor trail",           "–10%"],
        ["Featureless",          "+50%"],
        ["Raining",              "+10%"],
        ["Fog or mist",          "+30%"],
        ["Overcast sky",         "+30%"],
        ["Darkness",             "+70%"],
        ["Navigation check (sea)","–20%"],
        ["Navigator (land)",     "–30%"],
        ["Direction Sense prof.","–5%"],
    ]
    content = (
        '<p class="section-label">Base Chance by Terrain</p>' +
        _t(["Terrain", "Base %"], rows, right_cols=(1,)) +
        '<p class="section-label" style="margin-top:10px">Modifiers</p>' +
        _t(["Condition", "Modifier"], mods, right_cols=(1,))
    )
    return _card("Getting Hopelessly Lost", "exploration", content, span=2)


def _climbing_rates():
    rate_rows = [
        ["Tree / scaffolding", "4×", "3×", "2×"],
        ["Sloping wall",       "3×", "2×", "1×"],
        ["Rope and wall",      "2×", "1×", "½"],
        ["Rough w/ledges",     "1×", "½",  "⅓"],
        ["Rough*",             "1×", "⅓",  "¼"],
        ["Smooth, cracked*",   "½",  "⅓",  "¼"],
        ["Very smooth*",       "¼",  "–",  "–"],
        ["Ice wall*",          "–",  "–",  "¼"],
    ]
    note = '<p class="note">* Requires proficiency to attempt. Base rate: Thief = 2× MV, Unskilled = MV.</p>'
    return _card("Rates of Climbing", "exploration",
                 _t(["Surface", "Dry", "Slightly Slippery", "Slippery"], rate_rows) + note)


def _climbing_success():
    mods = [
        ["Rope and wall",               "+55%"],
        ["Abundant handholds (trees)",  "+40%"],
        ["Sloped inward",               "+25%"],
        ["Slightly slippery",           "–25%"],
        ["Slippery (icy/slimy)",        "–40%"],
        ["Padded / Studded leather",    "–5%"],
        ["Scale / chain mail",          "–15%"],
        ["Banded / splint mail",        "–25%"],
        ["Plate (all types)",           "–50%"],
        ["Mountaineering prof.",        "+10%/slot"],
        ["Rope Use prof. w/ rope",      "+10%"],
        ["Per encumbrance level",       "–5%"],
        ["Wounded below ½ HP",          "–10%"],
        ["Dwarf",                       "–10%"],
        ["Gnome / Halfling",            "–15%"],
    ]
    note = '<p class="note">Base success: Thief = Climb Walls skill · Unskilled = 40%</p>'
    return _card("Climbing Success", "exploration",
                 _t(["Situation", "Modifier"], mods, right_cols=(1,)) + note)


def _overland_movement():
    terrain = [
        ["Clear / farmland",             "½"],
        ["Plains / grassland / heath",   "1"],
        ["Scrub / brushland",            "2"],
        ["Barren / wasteland / rocky",   "2"],
        ["Desert, sand",                 "3"],
        ["Forest, light",                "2"],
        ["Forest, medium",               "3"],
        ["Forest, heavy",                "4"],
        ["Jungle, medium",               "6"],
        ["Jungle, heavy",                "8"],
        ["Hills, rolling",               "2"],
        ["Hills, steep / mountains, low","4"],
        ["Mountains, medium",            "6"],
        ["Mountains, high",              "8"],
        ["Glacier / marsh",              "2–8"],
        ["Swamp",                        "8"],
    ]
    weather = [
        ["Duststorm / sandstorm", "×3"],
        ["Freezing cold",         "+1"],
        ["Gale-force winds",      "+2"],
        ["Heavy fog",             "+1"],
        ["Ice storm",             "+2"],
        ["Mud",                   "×2"],
        ["Rain, torrential",      "×3"],
        ["Rain, heavy",           "×2"],
        ["Rain, light",           "+1"],
        ["Scorching heat",        "+1"],
        ["Snow, blizzard",        "×4"],
        ["Snow, normal",          "×2"],
    ]
    content = (
        '<p class="section-label">Terrain Cost (movement rate points per hex/day)</p>' +
        _t(["Terrain Type", "Cost"], terrain, right_cols=(1,)) +
        '<p class="section-label" style="margin-top:10px">Weather Modifiers</p>' +
        _t(["Weather", "Modifier"], weather, right_cols=(1,)) +
        '<p class="note">Daily miles ≈ MV × 5 ÷ terrain cost. Human base MV 12 = 24 miles/day on clear ground.</p>'
    )
    return _card("Overland Movement", "exploration", content, span=2)


def _light_sources():
    rows = [
        ["Beacon lantern",  "240 ft.", "2 hrs./pint"],
        ["Bullseye lantern","60 ft.",  "6 hrs./pint"],
        ["Hooded lantern",  "30 ft.",  "6 hrs./pint"],
        ["Torch",           "15 ft.",  "30 min."],
        ["Candle",          "5 ft.",   "10 min./inch"],
        ["Bonfire",         "50 ft.",  "½ hr./armload"],
        ["Campfire",        "35 ft.",  "1 hr./armload"],
        ["Continual light", "60 ft.",  "Indefinite"],
        ["Light spell",     "20 ft.",  "Variable"],
    ]
    return _card("Light Sources", "exploration", _t(["Source", "Radius", "Burn Time"], rows))


# ── Ability Scores ────────────────────────────────────────────────────────────

def _strength():
    rows = [
        ["1",       "-5","-4","1","3","1","0%",""],
        ["2",       "-3","-2","1","5","1","0%",""],
        ["3",       "-3","-1","5","10","2","0%",""],
        ["4–5",     "-2","-1","10","25","3","0%",""],
        ["6–7",     "-1","–","20","55","4","0%",""],
        ["8–9",     "–","–","35","90","5","1%",""],
        ["10–11",   "–","–","40","115","6","2%",""],
        ["12–13",   "–","–","45","140","7","4%",""],
        ["14–15",   "–","–","55","170","8","7%",""],
        ["16",      "–","+1","70","195","9","10%",""],
        ["17",      "+1","+1","85","220","10","13%",""],
        ["18",      "+1","+2","110","225","11","16%",""],
        ["18/01–50","+1","+3","135","280","12","20%",""],
        ["18/51–75","+2","+3","160","305","13","25%",""],
        ["18/76–90","+2","+4","185","330","14","30%",""],
        ["18/91–99","+2","+5","235","380","15 (3)","35%",""],
        ["18/00",   "+3","+6","335","480","16 (6)","40%",""],
        ["19",      "+3","+7","485","640","16 (8)","50%","Hill"],
        ["20",      "+3","+8","535","700","17 (10)","60%","Stone"],
        ["21",      "+4","+9","635","810","17 (12)","70%","Frost"],
        ["22",      "+4","+10","785","970","18 (14)","80%","Fire"],
        ["23",      "+5","+11","935","1,130","18 (16)","90%","Cloud"],
        ["24",      "+6","+12","1,235","1,440","19 (17)","95%","Storm"],
        ["25",      "+7","+14","1,535","1,750","19 (18)","99%","Titan"],
    ]
    return _card("Strength", "abilities", _t(
        ["Score","Hit Prob.","Dmg Adj.","Wt Allow (lb)","Max Press (lb)","Open Doors","Bend Bars","Giant Type"],
        rows, right_cols=(1,2,3,4,5,6),
    ), span=3)


def _dexterity():
    rows = [
        ["1",    "-6","-6","+5"],
        ["2",    "-4","-4","+5"],
        ["3",    "-3","-3","+4"],
        ["4",    "-2","-2","+3"],
        ["5",    "-1","-1","-2"],
        ["6",    "0","0","+1"],
        ["7–14", "0","0","0"],
        ["15",   "0","0","-1"],
        ["16",   "+1","+1","-2"],
        ["17",   "+2","+2","-3"],
        ["18",   "+2","+2","-4"],
        ["19",   "+3","+3","-4"],
        ["20",   "+3","+3","-4"],
        ["21",   "+4","+4","-5"],
        ["22–23","+4","+4","-5"],
        ["24",   "+5","+5","-6"],
        ["25",   "+5","+5","-6"],
    ]
    return _card("Dexterity", "abilities",
                 _t(["Score","React. Adj.","Missile Adj.","Def. Adj."], rows, right_cols=(1,2,3)))


def _constitution():
    rows = [
        ["1",  "-3","25%","30%","-2","Nil"],
        ["2",  "-2","30%","35%","-1","Nil"],
        ["3",  "-2","35%","40%","0","Nil"],
        ["4",  "-1","40%","45%","0","Nil"],
        ["5",  "-1","45%","50%","0","Nil"],
        ["6",  "-1","50%","55%","0","Nil"],
        ["7",  "0","55%","60%","0","Nil"],
        ["8",  "0","60%","65%","0","Nil"],
        ["9",  "0","65%","70%","0","Nil"],
        ["10", "0","70%","75%","0","Nil"],
        ["11", "0","75%","80%","0","Nil"],
        ["12", "0","80%","85%","0","Nil"],
        ["13", "0","85%","90%","0","Nil"],
        ["14", "0","88%","92%","0","Nil"],
        ["15", "+1","90%","94%","0","Nil"],
        ["16", "+2","95%","96%","0","Nil"],
        ["17", "+2/+3","97%","98%","0","Nil"],
        ["18", "+2/+4","99%","100%","0","Nil"],
        ["19", "+2/+5","99%","100%","+1","Nil"],
        ["20", "+2/+5","99%","100%","+1","1/6 turns"],
        ["21", "+2/+6","99%","100%","+2","1/5 turns"],
        ["22", "+2/+6","99%","100%","+2","1/4 turns"],
        ["23", "+2/+6","99%","100%","+3","1/3 turns"],
        ["24", "+2/+7","99%","100%","+3","1/2 turns"],
        ["25", "+2/+7","100%","100%","+4","1/1 turns"],
    ]
    return _card("Constitution", "abilities",
                 _t(["Score","HP Adj.","Sys. Shock","Rez %","Poison Save","Regen"], rows,
                    right_cols=(1,2,3,4)), span=2)


def _intelligence():
    rows = [
        ["1",    "0","–","–","–","–"],
        ["2–8",  "1","–","–","–","–"],
        ["9",    "2","4th","35%","6","–"],
        ["10",   "2","5th","40%","7","–"],
        ["11",   "2","5th","45%","7","–"],
        ["12",   "3","6th","50%","7","–"],
        ["13",   "3","6th","55%","9","–"],
        ["14",   "4","7th","60%","9","–"],
        ["15",   "4","7th","65%","11","–"],
        ["16",   "5","8th","70%","11","–"],
        ["17",   "6","8th","75%","14","–"],
        ["18",   "7","9th","85%","18","–"],
        ["19",   "8","9th","95%","All","1st-level"],
        ["20",   "9","9th","96%","All","2nd-level"],
        ["21",   "10","9th","97%","All","3rd-level"],
        ["22",   "11","9th","98%","All","4th-level"],
        ["23",   "12","9th","99%","All","5th-level"],
        ["24",   "15","9th","100%","All","6th-level"],
        ["25",   "20","9th","100%","All","7th-level"],
    ]
    return _card("Intelligence", "abilities",
                 _t(["Score","# Langs","Max Spell Lvl","Learn %","Max/Lvl","Illusion Immunity"],
                    rows, right_cols=(1,3,4)), span=2)


def _wisdom():
    rows = [
        ["1",  "-6","–","80%","–"],
        ["2",  "-4","–","60%","–"],
        ["3",  "-3","–","50%","–"],
        ["4",  "-2","–","45%","–"],
        ["5",  "-1","–","40%","–"],
        ["6",  "-1","–","35%","–"],
        ["7",  "-1","–","30%","–"],
        ["8",  "0","–","25%","–"],
        ["9",  "0","–","20%","–"],
        ["10", "0","–","15%","–"],
        ["11", "0","–","10%","–"],
        ["12", "0","–","5%","–"],
        ["13", "0","1st","0%","–"],
        ["14", "0","1st","0%","–"],
        ["15", "+1","2nd","0%","–"],
        ["16", "+2","2nd","0%","–"],
        ["17", "+3","3rd","0%","–"],
        ["18", "+4","4th","0%","–"],
        ["19", "+4","1st,3rd","0%","Fear, Charm, Command, Friends, Hypnotism"],
        ["20", "+4","2nd,4th","0%","Forget, Hold Person, Ray of Enfeeblement, Scare"],
        ["21", "+4","3rd,5th","0%","Fear"],
        ["22", "+4","4th,5th","0%","Charm Monster, Confusion, Emotion, Suggestion"],
        ["23", "+4","1st,6th","0%","Chaos, Feeblemind, Hold Monster, Quest"],
        ["24", "+4","5th,6th","0%","Geas, Mass Suggestion, Rod of Rulership"],
        ["25", "+4","6th,7th","0%","Antipathy/Sympathy, Death Spell, Mass Charm"],
    ]
    return _card("Wisdom / Willpower", "abilities",
                 _t(["Score","Magic Def.","Bonus Spells","Spell Fail %","Spell Immunity"],
                    rows, right_cols=(1,3)), span=2)


def _charisma():
    rows = [
        ["1",  "0","-8","-7"],
        ["2",  "1","-7","-6"],
        ["3",  "1","-6","-5"],
        ["4",  "1","-5","-4"],
        ["5",  "2","-4","-3"],
        ["6",  "2","-3","-2"],
        ["7",  "3","-2","-1"],
        ["8",  "3","-1","0"],
        ["9–11","4","0","0"],
        ["12", "5","0","0"],
        ["13", "5","0","+1"],
        ["14", "6","+1","+2"],
        ["15", "7","+3","+3"],
        ["16", "8","+4","+5"],
        ["17", "10","+6","+6"],
        ["18", "15","+8","+7"],
        ["19", "20","+10","+8"],
        ["20", "25","+12","+9"],
        ["21", "30","+14","+10"],
        ["22", "35","+16","+11"],
        ["23", "40","+18","+12"],
        ["24", "45","+20","+13"],
        ["25", "50","+20","+14"],
    ]
    return _card("Charisma", "abilities",
                 _t(["Score","Max Hench.","Loyalty Base","React. Adj."], rows, right_cols=(1,2,3)))


# ── Classes & Spells ──────────────────────────────────────────────────────────

def _xp_levels():
    rows = [
        ["2",  "2,000","2,250","2,500","1,500","2,000","1,250"],
        ["3",  "4,000","4,500","5,000","3,000","4,000","2,500"],
        ["4",  "8,000","9,000","10,000","6,000","7,500","5,000"],
        ["5",  "16,000","18,000","20,000","13,000","12,500","10,000"],
        ["6",  "32,000","36,000","40,000","27,500","20,000","20,000"],
        ["7",  "64,000","75,000","60,000","55,000","35,000","40,000"],
        ["8",  "125,000","150,000","90,000","110,000","60,000","70,000"],
        ["9",  "250,000","300,000","135,000","225,000","90,000","110,000"],
        ["10", "500,000","600,000","250,000","450,000","125,000","160,000"],
        ["11", "750,000","900,000","375,000","675,000","200,000","220,000"],
        ["12", "1,000,000","1,200,000","750,000","900,000","300,000","440,000"],
        ["13", "1,250,000","1,500,000","1,125,000","1,125,000","750,000","660,000"],
        ["14", "1,500,000","1,800,000","1,500,000","1,350,000","1,500,000","880,000"],
        ["15", "1,750,000","2,100,000","1,875,000","1,575,000","3,000,000","1,100,000"],
        ["16", "2,000,000","2,400,000","2,250,000","1,800,000","3,500,000","1,320,000"],
        ["17", "2,250,000","2,700,000","2,625,000","2,025,000","500,000*","1,540,000"],
        ["18", "2,500,000","3,000,000","3,000,000","2,250,000","1,000,000","1,760,000"],
        ["19", "2,750,000","3,300,000","3,375,000","2,475,000","1,500,000","1,980,000"],
        ["20", "3,000,000","3,600,000","3,750,000","2,700,000","2,000,000","2,200,000"],
    ]
    return _card("Experience Levels (XP to reach level)", "classes",
                 _t(["Lvl","Fighter","Pal/Ranger","Wizard","Cleric","Druid","Thief/Bard"],
                    rows, right_cols=tuple(range(1,7))), span=2)


def _wizard_spells():
    rows = [
        ["1","1","–","–","–","–","–","–","–","–"],
        ["2","2","–","–","–","–","–","–","–","–"],
        ["3","2","1","–","–","–","–","–","–","–"],
        ["4","3","2","–","–","–","–","–","–","–"],
        ["5","4","2","1","–","–","–","–","–","–"],
        ["6","4","2","2","–","–","–","–","–","–"],
        ["7","4","3","2","1","–","–","–","–","–"],
        ["8","4","3","3","2","–","–","–","–","–"],
        ["9","4","3","3","2","1","–","–","–","–"],
        ["10","4","4","3","2","2","–","–","–","–"],
        ["11","4","4","4","3","3","–","–","–","–"],
        ["12","4","4","4","4","4","1","–","–","–"],
        ["13","5","5","5","4","4","2","–","–","–"],
        ["14","5","5","5","4","4","2","1","–","–"],
        ["15","5","5","5","5","5","2","1","–","–"],
        ["16","5","5","5","5","5","3","2","1","–"],
        ["17","5","5","5","5","5","3","3","2","–"],
        ["18","5","5","5","5","5","3","3","2","1"],
        ["19","5","5","5","5","5","3","3","3","1"],
        ["20","5","5","5","5","5","4","3","3","2"],
    ]
    return _card("Wizard Spell Progression", "classes",
                 _t(["Lvl","1","2","3","4","5","6","7","8","9"], rows, right_cols=tuple(range(1,10))), span=2)


def _cleric_spells():
    rows = [
        ["1","1","–","–","–","–","–","–"],
        ["2","2","–","–","–","–","–","–"],
        ["3","2","1","–","–","–","–","–"],
        ["4","3","2","–","–","–","–","–"],
        ["5","3","3","1","–","–","–","–"],
        ["6","3","3","2","–","–","–","–"],
        ["7","3","3","2","1","–","–","–"],
        ["8","3","3","3","2","–","–","–"],
        ["9","4","4","3","2","1","–","–"],
        ["10","4","4","3","3","2","–","–"],
        ["11","5","4","4","3","2","1","–"],
        ["12","6","5","5","3","2","2","–"],
        ["13","6","6","6","4","2","2","–"],
        ["14","6","6","6","5","3","2","1"],
        ["15","6","6","6","6","4","2","1"],
        ["16","7","7","7","6","4","3","1"],
        ["17","7","7","7","7","5","3","2"],
        ["18","8","8","8","8","6","4","2"],
        ["19","9","9","8","8","6","4","2"],
        ["20","9","9","9","8","7","5","2"],
    ]
    return _card("Cleric Spell Progression", "classes",
                 _t(["Lvl","1","2","3","4","5","6","7"], rows, right_cols=tuple(range(1,8))), span=2)


def _bard_spells():
    rows = [
        ["1","–","–","–","–","–","–"],
        ["2","1","–","–","–","–","–"],
        ["3","2","–","–","–","–","–"],
        ["4","2","1","–","–","–","–"],
        ["5","3","1","–","–","–","–"],
        ["6","3","2","–","–","–","–"],
        ["7","3","2","1","–","–","–"],
        ["8","3","3","1","–","–","–"],
        ["9","3","3","2","–","–","–"],
        ["10","3","3","2","1","–","–"],
        ["11","3","3","3","1","–","–"],
        ["12","3","3","3","2","–","–"],
        ["13","3","3","3","2","1","–"],
        ["14","3","3","3","3","1","–"],
        ["15","3","3","3","3","2","1"],
        ["16","4","3","3","3","2","1"],
        ["17","4","4","3","3","3","1"],
        ["18","4","4","4","3","3","2"],
        ["19","4","4","4","4","3","2"],
        ["20","4","4","4","4","4","3"],
    ]
    return _card("Bard Spell Progression", "classes",
                 _t(["Lvl","1","2","3","4","5","6"], rows, right_cols=tuple(range(1,7))), span=2)


def _paladin_spells():
    rows = [
        ["9","1","1","–","–","–"],
        ["10","2","2","–","–","–"],
        ["11","3","2","1","–","–"],
        ["12","4","2","2","–","–"],
        ["13","5","2","2","1","–"],
        ["14","6","3","2","1","–"],
        ["15","7","3","2","1","1"],
        ["16","8","3","3","2","1"],
        ["17","9","3","3","3","1"],
        ["18","9","3","3","3","1"],
        ["19","9","3","3","3","2"],
        ["20","9","3","3","3","2"],
    ]
    return _card("Paladin Spell Progression", "classes",
                 _t(["Level","Cast Lvl","1","2","3","4"], rows, right_cols=(1,2,3,4,5)))


def _ranger_abilities():
    rows = [
        ["1","10%","15%","–","–","–","–"],
        ["2","15%","21%","–","–","–","–"],
        ["3","20%","27%","–","–","–","–"],
        ["4","25%","33%","–","–","–","–"],
        ["5","31%","40%","–","–","–","–"],
        ["6","37%","47%","–","–","–","–"],
        ["7","43%","55%","–","–","–","–"],
        ["8","49%","62%","1","1","–","–"],
        ["9","56%","70%","2","2","–","–"],
        ["10","63%","78%","3","2","1","–"],
        ["11","70%","86%","4","2","2","–"],
        ["12","77%","94%","5","2","2","1"],
        ["13","85%","99%","6","3","2","1"],
        ["14","93%","99%","7","3","2","2"],
        ["15","99%","99%","8","3","3","2"],
        ["16","99%","99%","9","3","3","3"],
    ]
    return _card("Ranger Abilities & Spell Progression", "classes",
                 _t(["Lvl","Hide Shadow","Move Silent","Cast Lvl","Sp 1","Sp 2","Sp 3"],
                    rows, right_cols=(1,2,3,4,5,6)), span=2)


def _wizard_specialist():
    rows = [
        ["Abjurer",    "Abjuration",    "H",     "15 Wis", "Alteration & Illusion"],
        ["Conjurer",   "Conj./Summ.",   "H, ½E", "15 Con", "Gr. Divination & Invocation"],
        ["Diviner",    "Gr. Divination","H, ½E, E","16 Wis","Conj./Summoning"],
        ["Enchanter",  "Ench./Charm",   "H, ½E, E","16 Cha","Invoc./Evoc. & Necromancy"],
        ["Illusionist","Illusion",       "H, G",  "16 Dex", "Necro., Invoc., Abjuration"],
        ["Invoker",    "Invoc./Evoc.",  "H",     "16 Con", "Ench./Charm & Conj./Summ."],
        ["Necromancer","Necromancy",    "H",     "16 Wis", "Illusion & Ench./Charm"],
        ["Transmuter", "Alteration",    "H, ½E", "15 Dex", "Abjuration & Necromancy"],
    ]
    note = '<p class="note">H = Human · ½E = Half-elf · E = Elf · G = Gnome</p>'
    return _card("Wizard Specialist Requirements", "classes",
                 _t(["Specialist","School","Race","Min. Score","Opposition Schools"], rows) + note, span=2)


def _thief_skills():
    base = [["Base","15%","10%","5%","10%","5%","15%","60%","0%"]]
    racial = [
        ["Dwarf",    "–",    "+10%","+15%","–",    "–",    "–",    "–10%","–5%"],
        ["Elf",      "+5%",  "–5%", "–",   "+5%",  "+10%", "+5%",  "–",   "–"],
        ["Gnome",    "–",    "+5%", "+10%","+5%",  "+5%",  "+10%", "–15%","–"],
        ["Half-elf", "+10%", "–",   "–",   "–",    "+5%",  "–",    "–",   "–"],
        ["Halfling", "+5%",  "+5%", "+5%", "+10%", "+15%", "+5%",  "–15%","–5%"],
    ]
    dex_mods = [
        ["9",    "–15%","–10%","–10%","–20%","–10%","–","–","–"],
        ["10",   "–10%","–5%", "–10%","–15%","–5%", "–","–","–"],
        ["11",   "–5%", "–",   "–5%", "–10%","–",   "–","–","–"],
        ["12",   "–",   "–",   "–",   "–5%", "–",   "–","–","–"],
        ["13–15","–",   "–",   "–",   "–",   "–",   "–","–","–"],
        ["16",   "–",   "+5%", "–",   "–",   "–",   "–","–","–"],
        ["17",   "+5%", "+10%","–",   "+5%", "+5%", "–","–","–"],
        ["18",   "+10%","+15%","+5%", "+10%","+10%","–","–","–"],
        ["19",   "+15%","+20%","+10%","+15%","+15%","–","–","–"],
    ]
    hd = ["","Pick Pockets","Open Locks","Find/Remove Traps","Move Silently","Hide in Shadows","Detect Noise","Climb Walls","Read Languages"]
    content = (
        '<p class="section-label">Base Scores</p>' + _t(hd, base) +
        '<p class="section-label" style="margin-top:10px">Racial Adjustments</p>' + _t(hd, racial) +
        '<p class="section-label" style="margin-top:10px">Dexterity Adjustments</p>' + _t(["Dex"] + hd[1:], dex_mods)
    )
    return _card("Thief Skills", "classes", content, span=3)


# ── Assemble ──────────────────────────────────────────────────────────────────

def generate() -> str:
    cat_buttons = "".join(
        f'<button class="cat-btn" data-cat="{k}" onclick="filterCat(\'{k}\')" '
        f'style="border-bottom:3px solid {CAT_COLORS[k]}">{CAT_LABELS[k]}</button>'
        for k in CAT_COLORS
    )

    sections = [
        # Combat
        _opportunity_attacks(), _morale(), _hit_dice_immunity(),
        _combat_modifiers(), _ac_modifiers(), _cover(),
        _initiative_actions(), _initiative_situations(),
        _warrior_attacks(), _monster_thac0(),
        _weapon_vs_armor(),
        _thac0_by_level(), _specialist_attacks(),
        _turning_undead(),
        # Encounter
        _encounter_distance(), _surprise(),
        _reactions(), _wilderness_encounters(),
        # Hazards
        _poison(), _item_hp(),
        _monster_strength(),
        _char_saves(),
        _item_saves(),
        # Exploration
        _tracking(), _lock_quality(),
        _hear_noise(), _detect_doors(),
        _light_sources(),
        _visibility(),
        _climbing_rates(), _climbing_success(),
        _getting_lost(),
        _overland_movement(),
        # Abilities
        _dexterity(), _charisma(),
        _constitution(),
        _intelligence(), _wisdom(),
        _strength(),
        # Classes
        _paladin_spells(),
        _xp_levels(),
        _wizard_spells(), _cleric_spells(),
        _bard_spells(),
        _ranger_abilities(), _wizard_specialist(),
        _thief_skills(),
    ]

    # Screen-specific styling on top of screen_common.COMMON_CSS.
    css_extra = """
      .card-body { padding: 8px; overflow: hidden; }
      td { padding: 4px 7px; white-space: nowrap; }
      .note { margin-top: 6px; }
      .section-label { color: #6878a8; font-size: 10px; font-weight: 700;
                       letter-spacing: .07em; text-transform: uppercase; margin-top: 4px; }
    """

    body_html = render_sections(sections, list(CAT_COLORS), CAT_LABELS, CAT_COLORS)
    return page(
        "DM Screen — AD&D 2nd Edition",
        css_extra, cat_buttons, body_html,
        "Search tables, rules, conditions…",
    )

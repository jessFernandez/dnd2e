"""roll20_export.py — turn a finished Character into the JSON the Roll20 sheet imports.

Phase 3 of the Roll20 bridge. The campaign uses the fuller community 2e sheet
(TheAaronSheet-based), so this produces a clean intermediate JSON that the sheet's
bulk-import worker (roll20_sheet/import_addon.html) maps onto that sheet's actual
attributes and repeating sections. Because we own both ends of this JSON, the
sheet's own attribute names never leak in here — the import worker does the final
mapping (e.g. willpower, wname/whit, repeating_spells1…).

House-rule notes baked in: Wisdom is exported as **willpower** (the campaign's
term); Armor Class is ascending (base 10 + worn armor + Dex, computed on the sheet);
attack_base is the 20−THAC0 attack bonus.

Pure and Qt-free: unit-tested without a running app. `spell_details` (name -> dict
with school/range/casting_time) is optional enrichment the app supplies from the
spell DB; without it, spells export with just name + level.
"""
import re

import char_rules as cr
import monster

# char_rules save categories -> the sheet's five save keys.
_SAVE_KEYS = {
    "Paralyzation/Poison/Death": "save_ppd",
    "Rod/Staff/Wand": "save_rsw",
    "Petrification/Polymorph": "save_pp",
    "Breath Weapon": "save_bw",
    "Spell": "save_spell",
}

# Ability -> the stat token the sheet's proficiency rows reference. Wisdom is the
# campaign's "Willpower".
_STAT_TOKEN = {
    "Strength": "strength", "Dexterity": "dexterity", "Constitution": "constitution",
    "Intelligence": "intelligence", "Wisdom": "willpower", "Charisma": "charisma",
    "Perception": "perception",
}


def _split_money(cp: int) -> dict:
    """Copper total -> gp / sp / cp (1 gp = 100 cp, 1 sp = 10 cp)."""
    gp, rem = divmod(max(0, int(cp)), 100)
    sp, c = divmod(rem, 10)
    return {"gp": gp, "sp": sp, "cp": c}


def _casting_segments(text) -> int:
    """Leading integer of a casting-time string ('3', '1 rd', ...) for initiative."""
    m = re.match(r"\s*(\d+)", str(text or ""))
    return int(m.group(1)) if m else 0


def character_to_roll20(character, spell_details: dict = None) -> dict:
    """Build the import JSON for a finished character. `spell_details` maps a spell
    name to {school, range, casting_time} (supplied by the app from the spell DB)."""
    c = character
    spell_details = spell_details or {}
    final = c.final_abilities()
    saves = c.saving_throws() or {}

    out = {
        "character_name": c.name or "",
        "player_race": c.race or "",
        "player_class": c.char_class or "",
        "player_level": c.level,
        "xp": c.xp,
        "alignment": c.alignment or "",
        "gender": c.gender or "",
        "strength": final.get("Strength", 10),
        "dexterity": final.get("Dexterity", 10),
        "constitution": final.get("Constitution", 10),
        "intelligence": final.get("Intelligence", 10),
        "willpower": final.get("Wisdom", 10),          # campaign term for Wisdom
        "charisma": final.get("Charisma", 10),
        "perception": final.get("Perception", 10),
        "strength_exceptional": c.exceptional_str or 0,
        "hp_max": c.max_hp() or 0,
        "hp": c.max_hp() or 0,
        "attack_base": c.attack_bonus() or 0,          # 20 − THAC0
        "armor_base": 10,
        "move": c.movement(),                          # base rate by race (demihumans 6)
    }
    out.update(_split_money(c.money_cp))
    for cat, key in _SAVE_KEYS.items():
        out[key] = saves.get(cat, 20)

    # Weapons the character carries (from the equipment catalog: have damage/speed).
    weapons = []
    for name, qty in c.inventory.items():
        it = cr.item(name)
        if it and it.get("category") == "Weapon":
            weapons.append({
                "name": name, "tohit": 0, "damage": _norm_damage(it.get("damage")),
                "dambonus": 0, "speed": _int_or_zero(it.get("speed")),
                "type": it.get("type", ""), "range": it.get("range", ""),
            })
    out["weapons"] = weapons

    # Weapon proficiencies -> the sheet's WP section. Each carries the slots it cost
    # and its Combat & Tactics mastery rung, so the sheet's `wpsslots` column is real.
    out["weapon_profs"] = [
        {"name": name, "slots": c.weapon_prof_cost(name), "rung": rung}
        for name, rung in c.weapon_profs.items()
    ]

    out["thief_skills"] = _thief_skills(c)

    # Nonweapon proficiencies: the sheet computes total = stat + base, so base is the
    # part of our skill that isn't the ability score itself.
    nwp = []
    for name in c.nonweapon_profs:
        p = cr.NONWEAPON_PROFICIENCIES.get(name)
        if not p:
            continue
        skill = c.proficiency_skill(name)
        if p.ability and skill is not None:
            stat = _STAT_TOKEN.get(p.ability, "")
            base = skill - final.get(p.ability, 0)
        else:
            stat, base = "", 0
        nwp.append({"name": name, "stat": stat, "base": base})
    out["nwp"] = nwp

    # All carried gear (weight + cost drive the sheet's encumbrance/wealth). Weight
    # is the *encumbering* weight, so armor the character is proficient in counts
    # half (Combat & Tactics) — the sheet's encumbrance then matches the builder's.
    gear = []
    for name, qty in c.inventory.items():
        it = cr.item(name) or {}
        gear.append({
            "name": name, "qty": qty,
            "weight": c.item_weight(name), "cost": it.get("cost_cp") or 0,
        })
    out["gear"] = gear

    # Worn armor -> the sheet's Armor section, so its AC worker recomputes Armor
    # Class from equipped pieces (10 base + these + Dex, ascending). A shield gives
    # a bigger bonus to a proficient wielder.
    armor = []
    for name in c.worn:
        it = cr.item(name)
        if it and it.get("category") == "Armor":
            armor.append({"name": name, "aac": c.item_ac_bonus(name),
                          "amagic": 0, "adex": 0, "aequipped": 1})
    out["armor"] = armor

    # Known spells, enriched from the DB: full stat block, description, and V/S/M
    # components. The level comes from the character (that's what the builder
    # validated against its slots), and drives the sheet's repeating_spells<N>.
    spells = []
    for name, spell_level in c.spells.items():
        d = spell_details.get(name, {})
        comp = (d.get("components") or "").upper()
        spells.append({
            "level": spell_level, "name": name,
            "school": d.get("school", ""), "range": d.get("range", ""),
            "castingTime": _casting_segments(d.get("casting_time")),
            "save": d.get("save", ""), "aoe": d.get("aoe", ""),
            "duration": d.get("duration", ""), "damage": d.get("damage", ""),
            "materials": d.get("materials", ""), "description": d.get("description", ""),
            "verbal": 1 if "V" in comp else 0,
            "somatic": 1 if "S" in comp else 0,
            "material": 1 if "M" in comp else 0,
        })
    out["spells"] = spells
    return out


# ── monster export (v2: mapped onto the PC sheet) ─────────────────────────────

def monster_to_roll20(m, spell_details: dict = None, spell_index=None) -> dict:
    """Build the import JSON for a monster, mapped onto the community 2e sheet (v2
    reuses the PC layout). Uses the **selected HD/age tier's** numbers (monster_tiers),
    the house-rule attack bonus (20−THAC0) and ascending AC — the same char_rules
    conversions the sheet reads, so they can't disagree — warrior-by-HD saves, the
    attack/damage line as weapon rows (each rolling at the size-derived initiative
    speed factor), and the spell-like abilities monster_spells matches as spells.

    ``spell_details`` maps a spell name to its DB row (level/school/…); ``spell_index``
    is a monster_spells index (both supplied by the app). Pure and Qt-free."""
    import monster_tiers
    m = monster_tiers.active_monster(m)                 # the selected tier's stat line
    spell_details = spell_details or {}
    hd = _hd_level(m.hit_dice)

    out = {
        "character_name": m.name or "",
        "player_class": "Monster",
        "player_level": hd,
        "xp": _leading_int(str(m.xp_value).replace(",", "")),
        "alignment": m.alignment or "",
        "hp_max": _hp_from_hd(m.hit_dice),
        "hp": _hp_from_hd(m.hit_dice),
        "attack_base": _leading_int(m.attack_bonus()),  # 20−THAC0, tiered
        "armor_base": _leading_int(m.ascending_ac(), 10),  # ascending AC (sheet AC = this)
        "move": _leading_int(m.movement, 12),
    }
    saves = cr.monster_saving_throws(hd)
    for cat, key in _SAVE_KEYS.items():
        out[key] = saves.get(cat, 20)

    out["weapons"] = _monster_weapons(m)
    out["spells"] = _monster_spells_rows(m, spell_index, spell_details)
    # sections the PC sheet has but a monster doesn't fill
    out["weapon_profs"], out["nwp"], out["gear"], out["armor"], out["thief_skills"] = [], [], [], [], []
    return out


def _leading_int(text, default: int = 0) -> int:
    """The first (optionally signed) integer in ``text``, else ``default``."""
    mm = re.search(r"-?\d+", str(text or ""))
    return int(mm.group()) if mm else default


#: A Hit Dice field written in **hit points** instead of dice — '1 hp', '1-4 hp',
#: '45-75 hp' — plus the '9 (40 hp)' form that gives both. The MM uses it for
#: creatures below a full die and for a few fixed-HP constructs.
_HP_FORM = re.compile(r"(?:(\d+)\s*-\s*)?(\d+)\s*hp\b", re.IGNORECASE)


def _hp_from_hd(hit_dice) -> int:
    """Hit points for a Hit Dice string. A field written in hit points ('1 hp',
    '1-4 hp', '9 (40 hp)') is taken at its word — the top of a range, since this seeds
    the sheet's *maximum*. Otherwise it's dice: d8 each (4.5, rounded half up) plus any
    bonus, so '5' -> 23 and '5+2' -> 25. Only a '+N' counts as a bonus — an 'N-M' Hit
    Dice string ('3-8') is a range/oddity, not a penalty, so its tail is ignored.
    Roll20 tracks the actual HP at the table; this just seeds a sensible maximum."""
    text = str(hit_dice or "")
    hp = _HP_FORM.search(text)
    if hp:
        return max(1, int(hp.group(2)))
    mm = re.match(r"\s*(\d+)\s*(\+\s*\d+)?", text)
    if not mm:
        return 0
    dice = int(mm.group(1))
    bonus = int(mm.group(2).replace(" ", "")) if mm.group(2) else 0
    return max(1, int(dice * 4.5 + 0.5) + bonus)      # round half *up*, not to even


def _hd_level(hit_dice) -> int:
    """The warrior level a monster saves at: its Hit Dice, or **0** for a creature of
    less than one full die — the MM writes those either as hit points ('1 hp',
    '1-4 hp') or as a die minus a penalty ('1-1'). A Hit Dice field that merely
    *mentions* hit points alongside its dice ('9 (40 hp)') is still a 9 HD monster."""
    text = str(hit_dice or "")
    if re.match(r"\s*1\s*-\s*1\b", text) or re.match(r"\s*1\s*/\s*\d", text):
        return 0
    if re.match(r"\s*\d+\s*(?:-\s*\d+\s*)?hp\b", text, re.IGNORECASE):   # hp, not dice
        hp = _hp_from_hd(text)
        return 0 if hp < 8 else hp // 8
    return _leading_int(text, 1)


def _range_to_dice(s: str) -> str:
    """A damage range as dice Roll20 can roll: '3-18' -> '3d6', '1-6' -> '1d6'; left
    alone when it doesn't divide cleanly ('2-5') or is already dice ('2d4'). The rule
    is monster.damage_to_dice — the same one the sheet renders (in its terse display
    form), so the export and the sheet can't disagree about a monster's damage."""
    return monster.damage_to_dice(str(s or "").strip())


#: The MM's "this attack, N times" notation — "1-6 (x 4)" on the Aboleth,
#: "3-18(x2)/2-12(x6)/7-28" on the Kraken. Spacing and case both vary.
_MULTIPLIER = re.compile(r"\(\s*x\s*(\d+)\s*\)", re.IGNORECASE)


def _attack_count(text: str) -> int:
    """How many times one '/'-separated attack is made: the "(x N)" multiplier, else 1."""
    mm = _MULTIPLIER.search(text or "")
    return int(mm.group(1)) if mm else 1


def _monster_weapons(m) -> list:
    """The monster's attack/damage line as weapon rows — one per '/'-separated attack
    (claw/claw/bite), rolling at the house-rule attack bonus and the size-derived
    initiative speed factor.

    Parentheses in that line mean one of two things, and conflating them was a bug:
    "1-6 (crush)" names the attack, while "1-6 (x 4)" says it happens four times.
    Treating the multiplier as a label exported the Aboleth with a single weapon
    called "x 4" and the Kraken with attacks called "x2" and "x6" — and threw the
    counts away, which are the part a DM needs. A multiplier now becomes N rows.
    """
    tohit = _leading_int(m.attack_bonus())
    speed = m.initiative_modifier() or 0
    dmg = (m.damage_attack or "").strip()
    parts = ([] if dmg.lower() in ("", "nil", "none", "see below")
             else [p.strip() for p in dmg.split("/") if p.strip()])

    # Expand first, name second. A creature with "3-18(x2)/2-12(x6)/7-28" makes nine
    # attacks, and numbering them 1-9 is what a DM counts — numbering within each
    # part would produce "Attack 1 1", which is neither the part nor the attack.
    expanded = []
    for part in parts:
        # A multiplier is not a name; anything else in parentheses still is.
        label = _paren_label(_MULTIPLIER.sub("", part)) or None
        damage = _norm_damage(_range_to_dice(_strip_paren(part)))
        expanded.extend([(label, damage)] * _attack_count(part))

    weapons = []
    for i, (label, damage) in enumerate(expanded, 1):
        # A named attack keeps its name even when it repeats — a creature with two
        # claws should show two rows called "claw", not "claw 1" and "claw 2".
        name = label or (f"Attack {i}" if len(expanded) > 1 else "Attack")
        weapons.append({
            "name": name, "tohit": tohit, "damage": damage,
            "dambonus": 0, "speed": speed, "type": "", "range": "",
        })
    if m.breath_weapon:                                 # the selected age tier's breath
        weapons.append({
            "name": "Breath Weapon", "tohit": 0,
            "damage": _norm_damage(_range_to_dice(_strip_paren(m.breath_weapon))),
            "dambonus": 0, "speed": speed, "type": "", "range": "",
        })
    return weapons


def _paren_label(text: str) -> str:
    mm = re.search(r"\(([^)]+)\)", text)
    return mm.group(1).strip() if mm else ""


def _strip_paren(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def _monster_spells_rows(m, spell_index, spell_details: dict) -> list:
    """The monster's spell-like abilities (matched by monster_spells) as spell rows,
    enriched from the compendium so they land in the sheet's spell section."""
    if not spell_index:
        return []
    import monster_spells
    rows = []
    for name, _slug in monster_spells.find_in(m, spell_index):
        d = spell_details.get(name, {})
        comp = (d.get("components") or "").upper()
        rows.append({
            "level": d.get("level") or 1, "name": name,
            "school": d.get("school", ""), "range": d.get("range", ""),
            "castingTime": _casting_segments(d.get("casting_time")),
            "save": d.get("save", ""), "aoe": d.get("aoe", ""),
            "duration": d.get("duration", ""), "damage": d.get("damage", ""),
            "materials": d.get("materials", ""), "description": d.get("description", ""),
            "verbal": 1 if "V" in comp else 0,
            "somatic": 1 if "S" in comp else 0,
            "material": 1 if "M" in comp else 0,
        })
    return rows


def _norm_damage(dmg) -> str:
    """'d8' -> '1d8' so Roll20 rolls it; passthrough for '1d6', '2d4', ''."""
    s = str(dmg or "").strip()
    return "1" + s if re.match(r"^d\d", s) else s


def _int_or_zero(v) -> int:
    m = re.match(r"\s*(\d+)", str(v or ""))
    return int(m.group(1)) if m else 0


#: Sheet suffixes for its "OG" (2e PHB) thief table: thiefO<key>{B,A,Ar,P} are
#: base / race+Dex adjustment / armor adjustment / discretionary points, and the
#: sheet's own `C` column sums them.
_THIEF_SHEET_KEYS = {
    "Pick Pockets": "PP",
    "Open Locks": "OL",
    "Find/Remove Traps": "FRT",
    "Move Silently": "MS",
    "Hide in Shadows": "HS",
    "Detect Noise": "DN",
    "Climb Walls": "CW",
    "Read Languages": "RL",
}


def _thief_skills(c) -> list:
    """The four columns of the sheet's thief table, one row per skill this class has.

    Empty for every class but Thief and Bard. The armor column is the adjustment
    for what the character is *currently wearing*; the sheet's own "Armor Equiped"
    dropdown would recompute it, so the import deliberately leaves that alone.
    """
    if not c.has_thief_skills():
        return []
    dex = c.final_abilities().get("Dexterity") or 0
    armor_kind = c.thief_armor_kind()
    rows = []
    for skill in c.thief_skill_names():
        rows.append({
            "key": _THIEF_SHEET_KEYS[skill],
            "name": skill,
            "base": cr.thief_skill_base(c.char_class, skill),
            "adj": (cr.thief_racial_adjustment(c.race, skill)
                    + cr.thief_dex_adjustment(dex, skill)),
            "armor": cr.thief_armor_adjustment(armor_kind, skill),
            "points": c.thief_points_in(skill),
        })
    return rows

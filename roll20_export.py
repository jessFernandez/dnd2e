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
        "player_level": 1,
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

    # Weapon proficiencies (the trained-with list) -> the sheet's WP section.
    out["weapon_profs"] = list(c.weapon_profs)

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

    # All carried gear (weight + cost drive the sheet's encumbrance/wealth).
    gear = []
    for name, qty in c.inventory.items():
        it = cr.item(name) or {}
        gear.append({
            "name": name, "qty": qty,
            "weight": it.get("weight") or 0, "cost": it.get("cost_cp") or 0,
        })
    out["gear"] = gear

    # Worn armor -> the sheet's Armor section, so its AC worker recomputes Armor
    # Class from equipped pieces (10 base + these + Dex, ascending).
    armor = []
    for name in c.worn:
        it = cr.item(name)
        if it and it.get("category") == "Armor":
            armor.append({"name": name, "aac": it.get("ac_bonus", 0),
                          "amagic": 0, "adex": 0, "aequipped": 1})
    out["armor"] = armor

    # Known spells (all 1st level at creation), enriched from the DB: full stat
    # block, description, and V/S/M components.
    spells = []
    for name in c.spells:
        d = spell_details.get(name, {})
        comp = (d.get("components") or "").upper()
        spells.append({
            "level": d.get("level", 1), "name": name,
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


def _norm_damage(dmg) -> str:
    """'d8' -> '1d8' so Roll20 rolls it; passthrough for '1d6', '2d4', ''."""
    s = str(dmg or "").strip()
    return "1" + s if re.match(r"^d\d", s) else s


def _int_or_zero(v) -> int:
    m = re.match(r"\s*(\d+)", str(v or ""))
    return int(m.group(1)) if m else 0

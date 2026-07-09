"""character.py — the in-progress character build (the charactermancer's state).

A `Character` is the mutable object the multi-step builder fills in: ability
scores, race, class, alignment, and (later steps) proficiencies and details.
Every *derived* value — race-adjusted abilities, HP, THAC0, saving throws, slot
budgets, and per-step validity — is computed by delegating to char_rules, so the
rules live in exactly one place and the builder can't disagree with the rulebook.

Pure and Qt-free: the controller (charactermancer.py) and UI sit on top of this,
but all the logic is here and unit-tested without a running app.

v1 scope: single-class characters, PHB core. Multi-/dual-class is phase 2 — the
`char_class` field is intentionally a single value to keep that boundary clear.
"""
import random
from dataclasses import dataclass, field

import char_rules as cr

# The nine alignments (used by the Alignment step; some classes restrict these).
ALIGNMENTS = (
    "Lawful Good", "Neutral Good", "Chaotic Good",
    "Lawful Neutral", "True Neutral", "Chaotic Neutral",
    "Lawful Evil", "Neutral Evil", "Chaotic Evil",
)

MIN_SCORE, MAX_SCORE = 3, 18   # rolled ability-score range at character creation


# ── Ability-score rolling (4d6 drop lowest) ─────────────────────────────────

def roll_4d6_drop_lowest(rng: random.Random = None) -> int:
    """One ability score: roll 4d6, discard the lowest die, sum the rest (3–18)."""
    rng = rng or random
    dice = sorted(rng.randint(1, 6) for _ in range(4))
    return sum(dice[1:])


def roll_ability_pool(rng: random.Random = None) -> list:
    """Six freshly rolled scores for the player to arrange across the abilities."""
    return [roll_4d6_drop_lowest(rng) for _ in range(6)]


# ── The character build ──────────────────────────────────────────────────────

@dataclass
class Character:
    house_rules: bool = True
    name: str = ""
    gender: str = ""
    # Assigned ability scores {ability: score}; empty until the player fills them.
    abilities: dict = field(default_factory=dict)
    # Freshly rolled values not yet assigned (the arrange pool); [] in manual mode.
    rolled_pool: list = field(default_factory=list)
    exceptional_str: int = None   # 1–100 percentile for a fighter's 18 Strength
    race: str = None
    char_class: str = None
    alignment: str = None
    # Advancement. `level` is authoritative (xp is tracked alongside it, not derived
    # from, so a DM can hand out levels). `hp_rolls` holds one hit-die roll per level
    # from 2nd up to the class's name level — see cr.hp_at_level. Keep them in sync
    # via set_level(); assigning `level` directly will leave hp_rolls short.
    level: int = 1
    xp: int = 0
    hp_rolls: list = field(default_factory=list)
    # Details-step fields (populated later in the flow).
    ambidextrous: bool = False
    handedness_roll: int = None
    age_level: int = 0            # house-rule aging: 0 = none, 1–3 (player-placed)
    # Proficiencies (spent at the Proficiencies step).
    weapon_profs: list = field(default_factory=list)      # weapon names
    nonweapon_profs: dict = field(default_factory=dict)   # name -> total slots invested
    bought_ambidexterity: bool = False                    # purchased 1-slot ambidexterity
    # Equipment (Equipment step) and known spells (Spells step).
    money_cp: int = 0                                     # copper pieces on hand
    inventory: dict = field(default_factory=dict)        # item name -> quantity
    worn: list = field(default_factory=list)             # equipped armor item names (⊆ inventory)
    spells: dict = field(default_factory=dict)           # spell name -> its spell level

    # ── ability scores ──────────────────────────────────────────────────────
    def ability_names(self) -> list:
        """The ability scores this character rolls — the standard six plus
        Perception when house rules are on."""
        return list(cr.house_abilities(self.house_rules))

    def roll_pool(self, rng: random.Random = None) -> list:
        """Roll one fresh score per ability (six, or seven with Perception)."""
        self.rolled_pool = [roll_4d6_drop_lowest(rng) for _ in self.ability_names()]
        return self.rolled_pool

    def assign_ability(self, ability: str, score: int):
        """Set one ability to a score (manual entry or arranging the pool)."""
        if ability not in self.ability_names():
            raise ValueError(f"unknown ability {ability!r}")
        self.abilities[ability] = int(score)

    def clear_abilities(self):
        self.abilities = {}
        self.exceptional_str = None

    def has_all_abilities(self) -> bool:
        return all(a in self.abilities for a in self.ability_names())

    def invalid_abilities(self) -> list:
        """(ability, score) pairs outside the legal 3–18 creation range."""
        return [(a, s) for a, s in self.abilities.items()
                if not (MIN_SCORE <= s <= MAX_SCORE)]

    def abilities_valid(self) -> bool:
        return self.has_all_abilities() and not self.invalid_abilities()

    def final_abilities(self) -> dict:
        """Ability scores with the chosen race's adjustments applied (Table 8)."""
        if self.race:
            return cr.apply_racial_adjustments(self.race, self.abilities)
        return dict(self.abilities)

    def rolls_exceptional_strength(self) -> bool:
        """A fighter (warrior group) with an 18 Strength rolls exceptional Strength —
        unless the race forbids it (halflings don't)."""
        if not self.char_class or self.final_abilities().get("Strength") != 18:
            return False
        if cr.CLASSES[self.char_class].group != "Warrior":
            return False
        return self.race != "Halfling"

    # ── race / class / alignment eligibility (delegates to char_rules) ───────
    def eligible_races(self) -> list:
        return cr.eligible_races(self.abilities) if self.has_all_abilities() else []

    def eligible_classes(self) -> list:
        if not self.has_all_abilities():
            return []
        return cr.eligible_classes(self.final_abilities(), race=self.race)

    def eligible_alignments(self) -> list:
        """Alignments allowed by the chosen class (all nine if unrestricted)."""
        if not self.char_class:
            return list(ALIGNMENTS)
        allowed = cr.CLASSES[self.char_class].allowed_alignments
        return list(allowed) if allowed else list(ALIGNMENTS)

    # ── derived statistics ──────────────────────────────────────────────────
    def max_level(self):
        if self.race and self.char_class:
            return cr.max_level(self.race, self.char_class)
        return None

    def max_hp(self, level: int = None):
        """Total HP at `level` (default: the character's own). Max hit die at 1st,
        then a stored roll + Con bonus per level, then flat HP past name level."""
        if not (self.char_class and "Constitution" in self.final_abilities()):
            return None
        return cr.hp_at_level(
            self.char_class, self._lvl(level), self.final_abilities()["Constitution"],
            self.hp_rolls, self.house_rules)

    def thac0(self, level: int = None):
        if not self.char_class:
            return None
        return cr.thac0(self.char_class, self._lvl(level), self.house_rules)

    def attack_bonus(self, level: int = None):
        if not self.char_class:
            return None
        return cr.attack_bonus(self.char_class, self._lvl(level), self.house_rules)

    def saving_throws(self, level: int = None):
        if not self.char_class:
            return None
        return cr.saving_throws(self.char_class, self._lvl(level))

    def attacks_per_round(self, level: int = None):
        """(attacks, rounds) — warriors reach 3/2 at 7th and 2/1 at 13th."""
        if not self.char_class:
            return None
        return cr.attacks_per_round(self.char_class, self._lvl(level))

    def weapon_slots(self, level: int = None):
        return cr.weapon_slots(self.char_class, self._lvl(level)) if self.char_class else None

    def nonweapon_slots(self, level: int = None):
        if not self.char_class:
            return None
        int_score = self.final_abilities().get("Intelligence")
        return cr.nonweapon_slots(self.char_class, self._lvl(level), int_score, self.house_rules)

    def _lvl(self, level) -> int:
        """Resolve an optional level argument against the character's own level."""
        return self.level if level is None else level

    def xp_bonus(self) -> bool:
        """Whether this build earns the +10% prime-requisite XP bonus."""
        if not self.char_class:
            return False
        return cr.xp_bonus_qualifies(self.char_class, self.final_abilities())

    def hit_die(self):
        return cr.hit_die(self.char_class, self.house_rules) if self.char_class else None

    # ── house-rule Perception + aging ────────────────────────────────────────
    def perception(self):
        """The Perception score, or None (not set / house rules off)."""
        return self.abilities.get(cr.PERCEPTION)

    def perception_mods(self):
        p = self.perception()
        return cr.perception_mods(p) if p is not None else None

    def aging_effects(self):
        """(physical_penalty, mental_bonus) totals for the chosen age level, which
        the player then places across their scores; None if no aging chosen."""
        return cr.aging_totals(self.age_level) if self.age_level else None

    # ── advancement ──────────────────────────────────────────────────────────
    def set_level(self, level: int, rng=None) -> int:
        """Set the character's level, clamped to the racial level limit, keeping
        `hp_rolls` in sync: levelling up rolls the new hit dice, levelling down
        discards the rolls above the new level (so going back up rerolls them).
        Returns the level actually set."""
        if level < 1:
            raise ValueError("level must be at least 1")
        cap = self.max_level()
        if cap is not None:
            level = min(level, cap)
        self.level = level

        if not self.char_class:
            return level
        needed = cr.hp_die_levels(self.char_class, level)
        rng = rng or random
        while len(self.hp_rolls) < needed:
            self.hp_rolls.append(rng.randint(1, self.hit_die()))
        del self.hp_rolls[needed:]
        return level

    def reroll_hp(self, rng=None) -> list:
        """Reroll every stored hit die (levels 2..name level)."""
        if not self.char_class:
            return self.hp_rolls
        rng = rng or random
        die = self.hit_die()
        self.hp_rolls = [rng.randint(1, die) for _ in self.hp_rolls]
        return self.hp_rolls

    def level_from_xp(self):
        """The level this character's XP would earn, ignoring the racial cap."""
        return cr.level_for_xp(self.char_class, self.xp) if self.char_class else None

    # ── proficiency slot budgets ─────────────────────────────────────────────
    def weapon_slots_total(self) -> int:
        return cr.weapon_slots(self.char_class, self.level) if self.char_class else 0

    def weapon_slots_used(self) -> int:
        used = sum(cr.weapon_slot_cost(w, self.house_rules) for w in self.weapon_profs)
        if self.bought_ambidexterity:
            used += cr.HOUSE_RULES.ambidexterity_slot_cost
        return used

    def weapon_slots_left(self) -> int:
        return self.weapon_slots_total() - self.weapon_slots_used()

    def nonweapon_slots_total(self) -> int:
        if not self.char_class:
            return 0
        int_score = self.final_abilities().get("Intelligence")
        return cr.nonweapon_slots(self.char_class, self.level, int_score, self.house_rules)

    def nonweapon_slots_used(self) -> int:
        return sum(self.nonweapon_profs.values())

    def nonweapon_slots_left(self) -> int:
        return self.nonweapon_slots_total() - self.nonweapon_slots_used()

    def can_buy_ambidexterity(self) -> bool:
        """Warriors and rogues may buy ambidexterity for one weapon slot (house
        rule) — unless they're already ambidextrous."""
        if not self.house_rules or not self.char_class or self.ambidextrous:
            return False
        return cr.CLASSES[self.char_class].group in ("Warrior", "Rogue")

    def proficiency_skill(self, name: str):
        """The effective skill for a taken nonweapon proficiency's check: relevant
        ability + the proficiency modifier + house-rule bonuses for extra slots.
        None for proficiencies with no ability check (they grant a special ability)."""
        p = cr.NONWEAPON_PROFICIENCIES.get(name)
        invested = self.nonweapon_profs.get(name)
        if not p or invested is None or not p.ability:
            return None
        score = self.final_abilities().get(p.ability)
        if score is None:
            return None
        extra = max(0, invested - p.slots)
        return score + p.modifier + extra * cr.proficiency_bonus_per_slot(self.house_rules)

    # ── equipment & spells ───────────────────────────────────────────────────
    def spellcasting_group(self):
        """'wizard', 'priest', or None — which spell list this class ever draws on.
        Bards cast wizard spells; paladins and rangers cast priest spells. Says
        nothing about *this* level — use spell_slots() for that."""
        if not self.char_class:
            return None
        return cr.spell_caster_group(self.char_class)

    def spell_slots(self) -> dict:
        """{spell_level: count} castable at the character's level; {} for a
        non-caster, and for a caster below the level its progression starts."""
        if not self.char_class:
            return {}
        final = self.final_abilities()
        return cr.spell_slots(self.char_class, self.level,
                              final.get("Wisdom"), final.get("Intelligence"))

    def max_spell_level(self) -> int:
        slots = self.spell_slots()
        return max(slots) if slots else 0

    def casts_spells(self) -> bool:
        """Whether the character has any spell slots at their current level."""
        return bool(self.spell_slots())

    def spells_at(self, spell_level: int) -> list:
        """Chosen spell names of one spell level."""
        return [n for n, lvl in self.spells.items() if lvl == spell_level]

    def spell_limit(self, spell_level: int = 1):
        """How many spells of `spell_level` may be chosen. Wizards (and bards) are
        capped by Intelligence's max-spells-per-level — the size of the spellbook at
        that level, None meaning 'All' at Int 19+. Priests (and paladins/rangers) are
        capped by the spells they can memorize. 0 when that spell level isn't
        castable yet; None for a non-caster (no cap concept)."""
        group = self.spellcasting_group()
        if group is None:
            return None
        slots = self.spell_slots()
        if spell_level not in slots:
            return 0                       # not castable at this class level
        if group == "wizard":
            intel = self.final_abilities().get("Intelligence")
            if intel is None:
                return 0
            cap = cr.intelligence_mods(intel).max_spells_per_level
            return None if cap >= 999 else cap
        return slots[spell_level]

    def spells_left(self, spell_level: int = 1):
        """Remaining picks at a spell level, or None when uncapped."""
        limit = self.spell_limit(spell_level)
        if limit is None:
            return None
        return max(0, limit - len(self.spells_at(spell_level)))

    def can_add_spell(self, spell_level: int = 1) -> bool:
        """Whether another spell of that level may be chosen."""
        left = self.spells_left(spell_level)
        return left is None or left > 0

    def movement(self) -> int:
        """Base movement rate (PHB). Demihumans (dwarf/gnome/halfling) are 6, the
        rest 12; defaults to 12 before a race is chosen."""
        return cr.RACES[self.race].movement if self.race in cr.RACES else 12

    def worn_ac_bonus(self) -> int:
        return sum((cr.item(n) or {}).get("ac_bonus", 0) for n in self.worn)

    def armor_class(self):
        """Ascending AC from worn armor + Dexterity (None until Dex is set)."""
        dex = self.final_abilities().get("Dexterity")
        return cr.armor_class(self.worn_ac_bonus(), dex, self.house_rules)

    def total_weight(self) -> float:
        """Total carried weight (lb) across the inventory."""
        total = 0.0
        for name, qty in self.inventory.items():
            it = cr.item(name)
            if it and it.get("weight"):
                total += it["weight"] * qty
        return round(total, 2)

    def encumbrance(self):
        strv = self.final_abilities().get("Strength")
        return cr.encumbrance_status(self.total_weight(), strv) if strv is not None else None

    # ── serialization (for save/load and handing off a finished sheet) ───────
    def to_dict(self) -> dict:
        return {
            "house_rules": self.house_rules, "name": self.name, "gender": self.gender,
            "abilities": dict(self.abilities), "exceptional_str": self.exceptional_str,
            "race": self.race, "char_class": self.char_class, "alignment": self.alignment,
            "level": self.level, "xp": self.xp, "hp_rolls": list(self.hp_rolls),
            "ambidextrous": self.ambidextrous, "handedness_roll": self.handedness_roll,
            "age_level": self.age_level,
            "weapon_profs": list(self.weapon_profs),
            "nonweapon_profs": dict(self.nonweapon_profs),
            "bought_ambidexterity": self.bought_ambidexterity,
            "money_cp": self.money_cp,
            "inventory": dict(self.inventory),
            "worn": list(self.worn),
            "spells": dict(self.spells),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        d = dict(data)
        d["abilities"] = dict(d.get("abilities") or {})
        d["weapon_profs"] = list(d.get("weapon_profs") or [])
        d["nonweapon_profs"] = dict(d.get("nonweapon_profs") or {})
        d["inventory"] = dict(d.get("inventory") or {})
        d["worn"] = list(d.get("worn") or [])
        # Spells were a flat name list before per-spell-level limits existed; every
        # one of them was necessarily a 1st-level spell, so migrate to {name: 1}.
        spells = d.get("spells") or {}
        d["spells"] = ({n: 1 for n in spells} if isinstance(spells, list)
                       else {n: int(lvl) for n, lvl in spells.items()})
        # Saves written before levelling existed carry no level/xp/hp_rolls; the
        # dataclass defaults (level 1, no xp, no rolls) are exactly right for them.
        d["level"] = int(d.get("level") or 1)
        d["xp"] = int(d.get("xp") or 0)
        d["hp_rolls"] = list(d.get("hp_rolls") or [])
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__ and k != "rolled_pool"})

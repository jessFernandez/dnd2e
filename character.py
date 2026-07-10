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
    # weapon name -> mastery rung ("proficient", "expert", "specialist", "master",
    # "high_master", "grand_master"). The rung is the state; slots are derived from
    # it (cr.weapon_prof_cost), because the house-rule costs mean slots-invested
    # alone can't tell a 2-slot bow proficiency from an expert with a dagger.
    weapon_profs: dict = field(default_factory=dict)
    # Tight weapon groups bought wholesale (CT: 2 slots for every weapon in one).
    weapon_groups: list = field(default_factory=list)
    # How many times a fighter has moved his specialisation to a new weapon. Each
    # move makes the next specialisation dearer (CT: 2 extra slots, then 3 each).
    respecialisations: int = 0
    # Slots spent on a specialisation that was later moved off. CT: the old weapon
    # "loses all benefits of specializing" but stays proficient — those slots are
    # gone, not refunded, so they must keep counting against the budget.
    sunk_slots: int = 0
    # Shield / armor proficiencies (1 weapon slot each): a better shield AC bonus,
    # and half encumbrance from that armor.
    shield_profs: list = field(default_factory=list)
    armor_profs: list = field(default_factory=list)
    # Fighting style -> slots of specialisation (0 = merely known). Warriors know
    # every style for free; nonwarriors pay a slot to learn one.
    fighting_styles: dict = field(default_factory=dict)
    # Unarmed discipline -> rung (CT Ch5): pummeling, wrestling, martial arts styles.
    unarmed_profs: dict = field(default_factory=dict)
    nonweapon_profs: dict = field(default_factory=dict)   # name -> total slots invested
    # Combat & Tactics special talents: name -> which budget paid for it,
    # "weapon" or "nonweapon" (only CT's asterisked talents may use the latter).
    # Ambidexterity lives here too — the campaign's house rule *is* the CT talent.
    special_talents: dict = field(default_factory=dict)
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
        used = sum(self.weapon_prof_cost(w) for w in self.weapon_profs)
        used += self.sunk_slots            # specialisations moved off, never refunded
        used += cr.WEAPON_GROUP_SLOT_COST * len(self.weapon_groups)
        used += cr.SHIELD_PROF_SLOT_COST * len(self.shield_profs)
        used += cr.ARMOR_PROF_SLOT_COST * len(self.armor_profs)
        used += sum(cr.style_slot_cost(s, n, self.char_class)
                    for s, n in self.fighting_styles.items())
        used += sum(cr.unarmed_prof_cost(r) for r in self.unarmed_profs.values())
        used += self.talent_slots_used("weapon")
        return used

    def weapon_slots_left(self) -> int:
        return self.weapon_slots_total() - self.weapon_slots_used()

    # ── weapon mastery ladder (Combat & Tactics) ─────────────────────────────
    def group_covers(self, weapon: str) -> bool:
        """Whether a bought weapon-group proficiency already covers this weapon."""
        return any(weapon in cr.weapon_group_members(g) for g in self.weapon_groups)

    def proficient_weapons(self) -> set:
        """Every weapon known at proficiency or better, from either route."""
        known = set(self.weapon_profs)
        for group in self.weapon_groups:
            known.update(cr.weapon_group_members(group))
        return known

    def weapon_prof_cost(self, weapon: str, rung: str = None,
                         respecialisations: int = None) -> int:
        """Slots invested in a weapon at a rung (its current one by default). When a
        weapon group already grants proficiency, only the rungs *above* it cost
        anything — the proficiency slot was paid for by the group."""
        rung = rung or self.weapon_profs.get(weapon, "proficient")
        respec = self.respecialisations if respecialisations is None else respecialisations
        cost = cr.weapon_prof_cost(weapon, rung, self.char_class, self.house_rules, respec)
        if self.group_covers(weapon):
            cost -= cr.weapon_prof_cost(weapon, "proficient", self.char_class,
                                        self.house_rules)
        return cost

    # ── moving a specialisation (CT: 2 extra slots, then 3 each) ─────────────
    def respecialisation_cost(self, weapon: str):
        """Slots to move the specialisation onto `weapon`. The old weapon's investment
        is *sunk* — CT says it "loses all benefits of specializing" but stays
        proficient — so the price is simply the new weapon's dearer specialisation:
        2 slots for the first move, 3 for every one after. None if nothing to move."""
        old = self.specialised_weapon()
        if old is None or old == weapon or not self.char_class:
            return None
        moved = self.respecialisations + 1
        return (self.weapon_prof_cost(weapon, "specialist", respecialisations=moved)
                - self.weapon_prof_cost(weapon))

    def can_respecialise(self, weapon: str) -> bool:
        """CT lets a fighter change which weapon he specialises in — at a price. The
        new weapon must already be proficient; the old one stays proficient forever
        but loses every benefit above it."""
        if "specialist" not in cr.weapon_rung_ladder(self.char_class or "", self.level):
            return False
        if self.weapon_rung(weapon) != "proficient":
            return False
        cost = self.respecialisation_cost(weapon)
        return cost is not None and cost <= self.weapon_slots_left()

    def weapon_rung(self, weapon: str) -> str:
        """The rung held with a weapon: an explicit one, else proficient via a bought
        weapon group, else familiar (it shares a tight group with something known),
        else nonproficient."""
        if weapon in self.weapon_profs:
            return self.weapon_profs[weapon]
        if self.group_covers(weapon):
            return "proficient"
        if cr.is_familiar(weapon, self.proficient_weapons()):
            return "familiar"
        return "nonproficient"

    # ── weapon group proficiencies ───────────────────────────────────────────
    def can_add_weapon_group(self, group: str) -> bool:
        if group in self.weapon_groups or not cr.weapon_group_members(group):
            return False
        return cr.WEAPON_GROUP_SLOT_COST <= self.weapon_slots_left()

    def can_remove_weapon_group(self, group: str) -> bool:
        """Removing a group makes any weapon it covered pay its own proficiency slot
        again; refuse if that would overdraw the budget."""
        if group not in self.weapon_groups:
            return False
        trial = [g for g in self.weapon_groups if g != group]
        saved, self.weapon_groups = self.weapon_groups, trial
        try:
            return self.weapon_slots_left() >= 0
        finally:
            self.weapon_groups = saved

    def weapon_rung_ladder(self) -> tuple:
        return cr.weapon_rung_ladder(self.char_class, self.level) if self.char_class else ()

    def specialised_weapon(self):
        """The one weapon a fighter has specialised in (or mastered), else None."""
        for weapon, rung in self.weapon_profs.items():
            if cr.specialises(rung):
                return weapon
        return None

    def can_raise_weapon(self, weapon: str) -> bool:
        """Whether the next rung with this weapon is reachable: it exists on the
        class's ladder at this level, the slots are there, and — for specialisation
        — no other weapon is already specialised. Works for weapons made proficient
        by a bought weapon group, too."""
        if not self.char_class:
            return False
        rung = self.weapon_rung(weapon)
        if rung not in cr.weapon_rung_ladder(self.char_class, self.level):
            return False            # nonproficient / familiar: buy proficiency first
        nxt = cr.next_weapon_rung(rung, self.char_class, self.level)
        if nxt is None:
            return False
        if cr.specialises(nxt):
            other = self.specialised_weapon()
            if other is not None and other != weapon:
                return False        # a fighter may only specialise in one weapon
        extra = self.weapon_prof_cost(weapon, nxt) - self.weapon_prof_cost(weapon, rung)
        return extra <= self.weapon_slots_left()

    def can_lower_weapon(self, weapon: str) -> bool:
        rung = self.weapon_profs.get(weapon)
        if not rung or not self.char_class:
            return False
        return cr.prev_weapon_rung(rung, self.char_class, self.level) is not None

    def nonweapon_slots_total(self) -> int:
        if not self.char_class:
            return 0
        int_score = self.final_abilities().get("Intelligence")
        return cr.nonweapon_slots(self.char_class, self.level, int_score, self.house_rules)

    def nonweapon_slots_used(self) -> int:
        return sum(self.nonweapon_profs.values()) + self.talent_slots_used("nonweapon")

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

    # ── unarmed disciplines (Combat & Tactics Ch5) ───────────────────────────
    def unarmed_rung(self, discipline: str) -> str:
        """The rung held in an unarmed discipline: an explicit one, else the free rung
        (familiar with pummeling/wrestling/overbearing; nothing with a martial art)."""
        if discipline in self.unarmed_profs:
            return self.unarmed_profs[discipline]
        return cr.unarmed_free_rung(discipline)

    def martial_art_styles_known(self) -> list:
        return [s for s in cr.MARTIAL_ARTS_STYLES if s in self.unarmed_profs]

    def knows_a_martial_art(self) -> bool:
        return bool(self.martial_art_styles_known())

    def _martial_art_at_or_above(self, rung: str):
        """The martial art already held at `rung` or better, if any. CT allows
        proficiency in several styles but expertise/specialisation in only one."""
        order = ("proficient", "expert", "specialist")
        want = order.index(rung)
        for style in self.martial_art_styles_known():
            if order.index(self.unarmed_profs[style]) >= want:
                return style
        return None

    def can_add_unarmed(self, discipline: str) -> bool:
        if discipline in self.unarmed_profs or not self.char_class:
            return False
        if not cr.unarmed_rung_ladder(discipline, self.char_class, self.level):
            return False       # overbearing, or a class that cannot advance it
        return cr.unarmed_prof_cost("proficient") <= self.weapon_slots_left()

    def can_raise_unarmed(self, discipline: str) -> bool:
        rung = self.unarmed_profs.get(discipline)
        if rung is None or not self.char_class:
            return False
        ladder = cr.unarmed_rung_ladder(discipline, self.char_class, self.level)
        if rung not in ladder or ladder.index(rung) + 1 >= len(ladder):
            return False
        nxt = ladder[ladder.index(rung) + 1]
        if cr.is_martial_art(discipline):
            other = self._martial_art_at_or_above(nxt)
            if other is not None and other != discipline:
                return False   # expert / specialist in only one style
        extra = cr.unarmed_prof_cost(nxt) - cr.unarmed_prof_cost(rung)
        return extra <= self.weapon_slots_left()

    def can_lower_unarmed(self, discipline: str) -> bool:
        rung = self.unarmed_profs.get(discipline)
        if rung is None or not self.char_class:
            return False
        ladder = cr.unarmed_rung_ladder(discipline, self.char_class, self.level)
        return rung in ladder and ladder.index(rung) > 0

    # ── special talents (Combat & Tactics) ───────────────────────────────────
    def talent_slots_used(self, source: str) -> int:
        """Slots one budget has spent on talents ('weapon' or 'nonweapon')."""
        return sum(cr.TALENTS[name].slots
                   for name, paid_from in self.special_talents.items()
                   if paid_from == source and name in cr.TALENTS)

    @property
    def bought_ambidexterity(self) -> bool:
        """Kept as an attribute because the campaign's house rule *is* CT's
        Ambidexterity talent; it's stored as one."""
        return "Ambidexterity" in self.special_talents

    @bought_ambidexterity.setter
    def bought_ambidexterity(self, value: bool):
        if value:
            self.special_talents["Ambidexterity"] = "weapon"
        else:
            self.special_talents.pop("Ambidexterity", None)

    def can_add_talent(self, name: str, source: str = None) -> bool:
        talent = cr.TALENTS.get(name)
        if talent is None or name in self.special_talents:
            return False
        if not cr.talent_allowed(name, self.char_class):
            return False
        source = source or self.default_talent_source(name)
        if talent.slot_source != "either" and source != talent.slot_source:
            return False       # only CT's asterisked talents may pick their budget
        if talent.requires_martial_art and not self.knows_a_martial_art():
            return False       # "Only a martial artist can learn the skills here"
        if name == "Ambidexterity" and not self.can_buy_ambidexterity():
            return False       # already ambidextrous, or house rules off
        left = (self.weapon_slots_left() if source == "weapon"
                else self.nonweapon_slots_left())
        return talent.slots <= left

    def default_talent_source(self, name: str) -> str:
        """Which budget a talent draws on unless the player picks the other one."""
        talent = cr.TALENTS.get(name)
        if talent is None or talent.slot_source == "either":
            return "weapon"
        return talent.slot_source

    def talent_skill(self, name: str):
        """A talent's proficiency check score, when it has one: the governing ability
        plus its modifier (the campaign's nonweapon-proficiency check model)."""
        talent = cr.TALENTS.get(name)
        if talent is None or not talent.ability:
            return None
        score = self.final_abilities().get(talent.ability)
        return None if score is None else score + talent.modifier

    # ── fighting styles (Combat & Tactics) ───────────────────────────────────
    def knows_style(self, style: str) -> bool:
        return cr.knows_styles_free(self.char_class) or style in self.fighting_styles

    def style_specialisation(self, style: str) -> int:
        """Slots of specialisation in a style — including a ranger's free two-weapon
        slot, which he holds without ever having bought it."""
        held = self.fighting_styles.get(style, 0)
        return max(held, cr.style_free_specialisation(style, self.char_class))

    def specialised_styles(self) -> list:
        return [s for s in cr.FIGHTING_STYLES if self.style_specialisation(s) > 0]

    def style_cost(self, style: str, spec_slots: int = None) -> int:
        spec = self.fighting_styles.get(style, 0) if spec_slots is None else spec_slots
        return cr.style_slot_cost(style, spec, self.char_class)

    def can_learn_style(self, style: str) -> bool:
        if not self.char_class or style not in cr.FIGHTING_STYLES:
            return False
        if self.knows_style(style):
            return False
        return cr.STYLE_LEARN_SLOT_COST <= self.weapon_slots_left()

    def can_forget_style(self, style: str) -> bool:
        """Only a nonwarrior's *bought* knowledge can be given back, and only while
        nothing is specialised in it."""
        return (style in self.fighting_styles and self.fighting_styles[style] == 0
                and not cr.knows_styles_free(self.char_class))

    def can_specialise_style(self, style: str) -> bool:
        if not self.knows_style(style) or not cr.can_specialise_styles(self.char_class):
            return False
        current = self.fighting_styles.get(style, 0)
        if current >= cr.max_style_specialisation(style):
            return False
        # Priests and rogues may specialise in only one style; warriors in any number.
        if not cr.knows_styles_free(self.char_class):
            others = [s for s in self.specialised_styles() if s != style]
            if others:
                return False
        extra = self.style_cost(style, current + 1) - self.style_cost(style, current)
        return extra <= self.weapon_slots_left()

    def can_despecialise_style(self, style: str) -> bool:
        return self.fighting_styles.get(style, 0) > 0

    def two_weapon_penalty(self) -> tuple:
        """(primary, off-hand) penalties for fighting with two weapons."""
        return cr.two_weapon_penalty(self.style_specialisation("Two-Weapon") > 0,
                                     self.ambidextrous or self.bought_ambidexterity)

    # ── shield / armor proficiency (Combat & Tactics) ────────────────────────
    def can_add_shield_prof(self, item_name: str) -> bool:
        return (cr.is_shield(item_name) and item_name not in self.shield_profs
                and cr.SHIELD_PROF_SLOT_COST <= self.weapon_slots_left())

    def can_add_armor_prof(self, item_name: str) -> bool:
        return (item_name in cr.armor_items() and item_name not in self.armor_profs
                and cr.ARMOR_PROF_SLOT_COST <= self.weapon_slots_left())

    def item_ac_bonus(self, item_name: str) -> int:
        """An item's AC contribution — a shield gives more to a proficient wielder."""
        if cr.is_shield(item_name):
            return cr.shield_ac_bonus(item_name, item_name in self.shield_profs)
        return (cr.item(item_name) or {}).get("ac_bonus", 0)

    def item_weight(self, item_name: str) -> float:
        """An item's encumbering weight: armor you're proficient in counts half."""
        weight = (cr.item(item_name) or {}).get("weight") or 0
        if item_name in self.armor_profs:
            weight *= cr.ARMOR_PROF_WEIGHT_FACTOR
        return weight

    def worn_ac_bonus(self) -> int:
        return sum(self.item_ac_bonus(n) for n in self.worn)

    def armor_class(self):
        """Ascending AC from worn armor + Dexterity (None until Dex is set)."""
        dex = self.final_abilities().get("Dexterity")
        return cr.armor_class(self.worn_ac_bonus(), dex, self.house_rules)

    def total_weight(self) -> float:
        """Total encumbering weight (lb). Armor you have an armor proficiency in
        counts half (CT/DD02628)."""
        total = 0.0
        for name, qty in self.inventory.items():
            total += self.item_weight(name) * qty
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
            "weapon_profs": dict(self.weapon_profs),
            "weapon_groups": list(self.weapon_groups),
            "respecialisations": self.respecialisations,
            "sunk_slots": self.sunk_slots,
            "shield_profs": list(self.shield_profs),
            "armor_profs": list(self.armor_profs),
            "fighting_styles": dict(self.fighting_styles),
            "nonweapon_profs": dict(self.nonweapon_profs),
            "special_talents": dict(self.special_talents),
            "unarmed_profs": dict(self.unarmed_profs),
            "money_cp": self.money_cp,
            "inventory": dict(self.inventory),
            "worn": list(self.worn),
            "spells": dict(self.spells),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        d = dict(data)
        d["abilities"] = dict(d.get("abilities") or {})
        # Weapon proficiencies were a flat name list before the mastery ladder; each
        # of those was plain proficiency.
        wprofs = d.get("weapon_profs") or {}
        d["weapon_profs"] = ({w: "proficient" for w in wprofs} if isinstance(wprofs, list)
                             else dict(wprofs))
        d["weapon_groups"] = list(d.get("weapon_groups") or [])
        d["respecialisations"] = int(d.get("respecialisations") or 0)
        d["sunk_slots"] = int(d.get("sunk_slots") or 0)
        d["shield_profs"] = list(d.get("shield_profs") or [])
        d["armor_profs"] = list(d.get("armor_profs") or [])
        d["fighting_styles"] = {k: int(v) for k, v in (d.get("fighting_styles") or {}).items()}
        # Ambidexterity used to be a lone bool; it is CT's special talent, so a
        # legacy save that bought it migrates into the talent dict.
        talents = dict(d.get("special_talents") or {})
        if d.pop("bought_ambidexterity", False) and "Ambidexterity" not in talents:
            talents["Ambidexterity"] = "weapon"
        d["special_talents"] = talents
        d["unarmed_profs"] = dict(d.get("unarmed_profs") or {})
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

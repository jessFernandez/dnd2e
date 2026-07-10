"""charactermancer.py — the character-builder flow controller (the step machine).

Sits between the Character state (character.py) and the UI (charactermancer_html.py
+ app.py wiring). It owns:

  * the ordered steps and which one is current,
  * per-step completeness gating (you can't advance past an incomplete step),
  * downstream invalidation (changing abilities that make your race illegal clears
    the race/class/alignment so the build can never hold a contradiction), and
  * `dispatch(path)` — turning a `dnd:///cm/<path>` link action into a state change.

Pure and Qt-free: app.py intercepts the `cm/` links and calls `dispatch`, then
re-renders. All the branching lives here and is unit-tested without a running app.
"""
import random

import char_rules as cr
from character import Character

# Ordered steps and their display titles.
# The two proficiency budgets are separate steps: Combat & Tactics turned the weapon
# side into weapons, groups, shield/armor, fighting styles, unarmed disciplines and
# talents, which is far too much to share a page with the nonweapon skills.
STEPS = ("abilities", "race", "class", "alignment", "weapons", "nonweapon",
         "equipment", "spells", "details", "review")
STEP_TITLES = {
    "abilities": "Ability Scores",
    "race": "Race",
    "class": "Class",
    "alignment": "Alignment",
    "weapons": "Weapon Proficiencies",
    "nonweapon": "Nonweapon Proficiencies",
    "equipment": "Equipment",
    "spells": "Spells",
    "details": "Details",
    "review": "Review",
}


class Charactermancer:
    def __init__(self, character: Character = None, rng: random.Random = None):
        self.character = character or Character()
        self.index = 0
        self.ability_mode = "roll"      # "roll" | "manual" — pure UI state for the first step
        self.saved_id = None            # DB row id once this build has been saved (set by app.py)
        self._rng = rng                 # injectable for deterministic tests
        self.spell_catalog = []         # level-1 spells for this class (injected by app.py)

    @property
    def _roll(self) -> random.Random:
        """The RNG every roll goes through: the injected one, else the `random`
        module. Centralised so no call site has to repeat the fallback."""
        return self._rng or random

    # ── step position ────────────────────────────────────────────────────────
    @property
    def step(self) -> str:
        return STEPS[self.index]

    @property
    def title(self) -> str:
        return STEP_TITLES[self.step]

    def is_complete(self, step: str = None) -> bool:
        """Whether a step has enough valid input to move past it."""
        step = step or self.step
        c = self.character
        if step == "abilities":
            return c.abilities_valid()
        if step == "race":
            return bool(c.race) and c.race in c.eligible_races()
        if step == "class":
            if not (c.char_class and c.char_class in c.eligible_classes()):
                return False
            # a warrior with an 18 Strength must roll exceptional Strength first
            if c.rolls_exceptional_strength() and c.exceptional_str is None:
                return False
            return True
        if step == "alignment":
            return bool(c.alignment) and c.alignment in c.eligible_alignments()
        if step == "details":
            return bool(c.name.strip())
        # the two proficiency steps (optional) and review are always passable
        return True

    def can_advance(self) -> bool:
        return self.index < len(STEPS) - 1 and self.is_complete()

    def can_go_back(self) -> bool:
        return self.index > 0

    def advance(self) -> bool:
        if not self.can_advance():
            return False
        self.index += 1
        return True

    def back(self) -> bool:
        if not self.can_go_back():
            return False
        self.index -= 1
        return True

    def goto(self, step: str) -> bool:
        """Jump to a named step (used by the progress rail). Only allows landing on
        a step whose predecessors are all complete."""
        if step not in STEPS:
            return False
        target = STEPS.index(step)
        if any(not self.is_complete(STEPS[i]) for i in range(target)):
            return False
        self.index = target
        return True

    # ── state mutations ──────────────────────────────────────────────────────
    def set_mode(self, mode: str):
        if mode in ("roll", "manual"):
            self.ability_mode = mode

    def roll(self):
        """Roll a fresh pool and lay it out high-to-low as a starting arrangement;
        the player then rearranges via the per-ability selectors."""
        pool = self.character.roll_pool(self._roll)
        for ability, score in zip(self.character.ability_names(), sorted(pool, reverse=True)):
            self.character.assign_ability(ability, score)
        self._revalidate()

    def set_ability(self, ability: str, score: int):
        if ability in self.character.ability_names():
            self.character.assign_ability(ability, score)
            self._revalidate()

    def clear_abilities(self):
        self.character.clear_abilities()
        self._revalidate()

    def set_race(self, race: str):
        if race in cr.RACES:
            self.character.race = race
            self._revalidate()
            self._resync_level()

    def set_class(self, class_name: str):
        if class_name in cr.CLASSES:
            self.character.char_class = class_name
            self._revalidate()
            self._resync_level()

    def _resync_level(self):
        """Race and class both move the racial level cap and the number of hit dice
        a level needs, so re-apply the level after either changes. Must run *after*
        _revalidate(), which clears a class the new race can't take — otherwise
        max_level() would raise on the illegal pair. A no-op for the level-1 builds
        the builder makes today."""
        if self.character.char_class:
            self.character.set_level(self.character.level, rng=self._roll)

    # ── advancement ───────────────────────────────────────────────────────────
    def set_level(self, level: int) -> bool:
        """Set the character's level (clamped to the racial cap by Character)."""
        if not self.character.char_class or level < 1:
            return False
        self.character.set_level(level, rng=self._roll)
        return True

    def reroll_hp(self):
        self.character.reroll_hp(rng=self._roll)

    def set_alignment(self, alignment: str):
        self.character.alignment = alignment

    def set_name(self, name: str):
        self.character.name = name

    def set_gender(self, gender: str):
        self.character.gender = gender

    def set_age_level(self, level: int):
        """House-rule aging: 0 = none, 1–3 apply cumulative penalties/bonuses the
        player then places across their scores."""
        if 0 <= level <= 3:
            self.character.age_level = level

    def roll_exceptional_strength(self):
        """Warriors with an 18 Strength roll d100 to set the 18/xx band (1–100)."""
        if self.character.rolls_exceptional_strength():
            self.character.exceptional_str = self._roll.randint(1, 100)

    def roll_handedness(self):
        """House rule: roll a d10 for handedness; a 10 means ambidextrous. Rangers
        are ambidextrous regardless."""
        roll = self._roll.randint(1, 10)
        self.character.handedness_roll = roll
        self.character.ambidextrous = cr.is_ambidextrous(
            self.character.race, self.character.char_class, roll, self.character.house_rules)

    def _revalidate(self):
        """Clear downstream choices that a change just made illegal, so the build
        can never hold a contradictory race/class/alignment."""
        c = self.character
        if c.race and c.has_all_abilities() and c.race not in c.eligible_races():
            c.race = None
        if c.char_class and c.char_class not in c.eligible_classes():
            c.char_class = None
        if c.alignment and c.alignment not in c.eligible_alignments():
            c.alignment = None
        # drop a rolled exceptional-Strength percentile that no longer applies
        # (Strength changed off 18, or the class is no longer a warrior)
        if c.exceptional_str is not None and not c.rolls_exceptional_strength():
            c.exceptional_str = None
        # drop chosen nonweapon proficiencies the (possibly changed) class can no
        # longer take, cascading to anything that depended on them
        if c.char_class:
            for name in [n for n in c.nonweapon_profs
                         if not cr.proficiency_available(n, c.char_class)]:
                self.remove_proficiency(name)

    # ── proficiencies ────────────────────────────────────────────────────────
    def add_weapon(self, weapon: str):
        """Become proficient with a weapon. Cost includes the house-rule slot price
        and any barred-weapon penalty for this class. A weapon a bought group already
        covers is free and needs no entry."""
        c = self.character
        if not c.char_class or weapon not in cr.WEAPONS or weapon in c.weapon_profs:
            return
        if c.group_covers(weapon):
            return
        if c.weapon_prof_cost(weapon, "proficient") <= c.weapon_slots_left():
            c.weapon_profs[weapon] = "proficient"

    def remove_weapon(self, weapon: str):
        self.character.weapon_profs.pop(weapon, None)

    def raise_weapon(self, weapon: str):
        """Climb one rung of the mastery ladder with a weapon."""
        c = self.character
        if c.can_raise_weapon(weapon):
            c.weapon_profs[weapon] = cr.next_weapon_rung(
                c.weapon_rung(weapon), c.char_class, c.level)

    def respecialise(self, weapon: str):
        """Move the fighter's specialisation onto another proficient weapon. The old
        weapon keeps its proficiency but loses mastery; each move costs more."""
        c = self.character
        if not c.can_respecialise(weapon):
            return
        old = c.specialised_weapon()
        # Whatever was spent above proficiency on the old weapon is gone for good.
        c.sunk_slots += c.weapon_prof_cost(old) - c.weapon_prof_cost(old, "proficient")
        c.respecialisations += 1
        if c.group_covers(old):
            c.weapon_profs.pop(old, None)     # the group still grants proficiency
        else:
            c.weapon_profs[old] = "proficient"
        c.weapon_profs[weapon] = "specialist"

    def lower_weapon(self, weapon: str):
        """Step back down one rung, refunding its extra slot. Dropping to proficiency
        on a group-covered weapon drops the entry entirely — the group grants it."""
        c = self.character
        if not c.can_lower_weapon(weapon):
            return
        prev = cr.prev_weapon_rung(c.weapon_profs[weapon], c.char_class, c.level)
        if prev == "proficient" and c.group_covers(weapon):
            c.weapon_profs.pop(weapon)
        else:
            c.weapon_profs[weapon] = prev

    # ── weapon group proficiencies (CT: 2 slots for a whole tight group) ─────
    def add_weapon_group(self, group: str):
        c = self.character
        if not c.char_class or not c.can_add_weapon_group(group):
            return
        c.weapon_groups.append(group)
        # Plain proficiencies the group now grants are redundant — refund them.
        for weapon in list(c.weapon_profs):
            if c.weapon_profs[weapon] == "proficient" and c.group_covers(weapon):
                c.weapon_profs.pop(weapon)

    def remove_weapon_group(self, group: str):
        c = self.character
        if c.can_remove_weapon_group(group):
            c.weapon_groups.remove(group)

    # ── shield / armor proficiencies (1 weapon slot each) ────────────────────
    def add_shield_prof(self, item_name: str):
        if self.character.can_add_shield_prof(item_name):
            self.character.shield_profs.append(item_name)

    def remove_shield_prof(self, item_name: str):
        if item_name in self.character.shield_profs:
            self.character.shield_profs.remove(item_name)

    def add_armor_prof(self, item_name: str):
        if self.character.can_add_armor_prof(item_name):
            self.character.armor_profs.append(item_name)

    def remove_armor_prof(self, item_name: str):
        if item_name in self.character.armor_profs:
            self.character.armor_profs.remove(item_name)

    # ── fighting styles ──────────────────────────────────────────────────────
    def learn_style(self, style: str):
        if self.character.can_learn_style(style):
            self.character.fighting_styles[style] = 0

    def forget_style(self, style: str):
        if self.character.can_forget_style(style):
            self.character.fighting_styles.pop(style)

    def specialise_style(self, style: str):
        c = self.character
        if c.can_specialise_style(style):
            c.fighting_styles[style] = c.fighting_styles.get(style, 0) + 1

    def despecialise_style(self, style: str):
        c = self.character
        if not c.can_despecialise_style(style):
            return
        c.fighting_styles[style] -= 1
        # A warrior knows every style anyway, so an empty entry is just noise.
        if c.fighting_styles[style] == 0 and cr.knows_styles_free(c.char_class):
            c.fighting_styles.pop(style)

    def toggle_ambidexterity(self):
        """Ambidexterity is CT's special talent; the house rule prices it the same."""
        c = self.character
        if c.bought_ambidexterity:
            self.remove_talent("Ambidexterity")
        else:
            self.add_talent("Ambidexterity")

    # ── unarmed disciplines (CT Ch5) ─────────────────────────────────────────
    def add_unarmed(self, discipline: str):
        c = self.character
        if c.can_add_unarmed(discipline):
            c.unarmed_profs[discipline] = "proficient"

    def remove_unarmed(self, discipline: str):
        c = self.character
        if c.unarmed_profs.pop(discipline, None) is None:
            return
        # "Only a martial artist can learn the skills presented here" — dropping the
        # last style takes its talents with it.
        if cr.is_martial_art(discipline) and not c.knows_a_martial_art():
            for name in [n for n in c.special_talents
                         if cr.TALENTS[n].requires_martial_art]:
                c.special_talents.pop(name)

    def raise_unarmed(self, discipline: str):
        c = self.character
        if not c.can_raise_unarmed(discipline):
            return
        ladder = cr.unarmed_rung_ladder(discipline, c.char_class, c.level)
        c.unarmed_profs[discipline] = ladder[ladder.index(c.unarmed_profs[discipline]) + 1]

    def lower_unarmed(self, discipline: str):
        c = self.character
        if not c.can_lower_unarmed(discipline):
            return
        ladder = cr.unarmed_rung_ladder(discipline, c.char_class, c.level)
        c.unarmed_profs[discipline] = ladder[ladder.index(c.unarmed_profs[discipline]) - 1]

    # ── special talents ──────────────────────────────────────────────────────
    def add_talent(self, name: str, source: str = None):
        c = self.character
        source = source or c.default_talent_source(name)
        if c.can_add_talent(name, source):
            c.special_talents[name] = source

    def remove_talent(self, name: str):
        self.character.special_talents.pop(name, None)

    def add_proficiency(self, name: str):
        c = self.character
        p = cr.NONWEAPON_PROFICIENCIES.get(name)
        if not p or name in c.nonweapon_profs:
            return
        # gate on class availability and prerequisites, then on the slot budget
        if c.char_class and not cr.proficiency_available(p, c.char_class):
            return
        if not cr.proficiency_prereqs_met(p, c.nonweapon_profs):
            return
        if p.slots <= c.nonweapon_slots_left():
            c.nonweapon_profs[name] = p.slots

    def remove_proficiency(self, name: str):
        c = self.character
        if name not in c.nonweapon_profs:
            return
        # cascade: drop any skills that required this one so the build never holds
        # a proficiency whose prerequisite is gone
        for dep in cr.proficiency_dependents(name, list(c.nonweapon_profs)):
            self.remove_proficiency(dep)
        c.nonweapon_profs.pop(name, None)

    def add_proficiency_slot(self, name: str):
        """Spend an extra slot on a known proficiency (+2 to its check, house rule)."""
        c = self.character
        if name in c.nonweapon_profs and c.nonweapon_slots_left() >= 1:
            c.nonweapon_profs[name] += 1

    def remove_proficiency_slot(self, name: str):
        c = self.character
        p = cr.NONWEAPON_PROFICIENCIES.get(name)
        if p and c.nonweapon_profs.get(name, 0) > p.slots:
            c.nonweapon_profs[name] -= 1

    # ── equipment ─────────────────────────────────────────────────────────────
    def roll_money(self):
        """Roll (or re-roll) the class's starting purse, in copper pieces."""
        if self.character.char_class:
            self.character.money_cp = cr.roll_starting_money(
                self.character.char_class, self._roll)

    def buy_item(self, name: str):
        """Buy one of a catalog item if it's affordable (deducts its cp cost)."""
        c = self.character
        it = cr.item(name)
        if it and it["cost_cp"] <= c.money_cp:
            c.money_cp -= it["cost_cp"]
            c.inventory[name] = c.inventory.get(name, 0) + 1

    def sell_item(self, name: str):
        """Return one owned item to the shop, refunding its cp cost (a clean undo)."""
        c = self.character
        if c.inventory.get(name, 0) <= 0:
            return
        it = cr.item(name)
        c.inventory[name] -= 1
        if c.inventory[name] <= 0:
            del c.inventory[name]
            if name in c.worn:
                c.worn.remove(name)          # can't wear what you no longer own
        if it:
            c.money_cp += it["cost_cp"]

    def toggle_worn(self, name: str):
        """Equip/unequip a piece of owned armor (contributes its AC bonus)."""
        c = self.character
        it = cr.item(name)
        if not it or it.get("category") != "Armor" or name not in c.inventory:
            return
        if name in c.worn:
            c.worn.remove(name)
        else:
            c.worn.append(name)

    # ── spells ────────────────────────────────────────────────────────────────
    def _catalog_names(self) -> set:
        return {s["name"] for s in self.spell_catalog}

    def spell_level_of(self, name: str):
        """The spell level of a catalog spell, or None if it isn't in the catalog."""
        for s in self.spell_catalog:
            if s["name"] == name:
                return int(s.get("level") or 1)
        return None

    def chosen_by_level(self) -> dict:
        """{spell_level: [names]} of the spells already chosen, in catalog order."""
        out = {}
        for name, lvl in self.character.spells.items():
            out.setdefault(lvl, []).append(name)
        return out

    def add_spell(self, name: str):
        """Add a spell, respecting the budget for *its own* spell level (wizards are
        capped by Intelligence, priests by memorizable slots)."""
        spell_level = self.spell_level_of(name)
        if spell_level is None or name in self.character.spells:
            return
        if self.character.can_add_spell(spell_level):
            self.character.spells[name] = spell_level

    def remove_spell(self, name: str):
        self.character.spells.pop(name, None)

    # ── action dispatch (from dnd:///cm/<path> links) ─────────────────────────
    def dispatch(self, path: str) -> bool:
        """Apply a `cm/` link action. `path` is everything after `cm/`, already
        URL-unquoted by the caller. Parsed as `verb/tail` so a tail (an ability
        name, weapon, or proficiency) may itself contain '/' (e.g. Reading/Writing).
        Returns True if the action was handled."""
        verb, _, tail = path.partition("/")
        if not verb:
            return False

        if verb == "next":
            return self.advance()
        if verb == "back":
            return self.back()
        if verb == "goto" and tail:
            return self.goto(tail)
        if verb == "mode" and tail:
            self.set_mode(tail); return True
        if verb == "roll":
            self.roll(); return True
        if verb == "clear":
            self.clear_abilities(); return True
        if verb == "assign" and tail:
            ability, _, score = tail.partition("/")
            if not score:
                return False
            try:
                self.set_ability(ability, int(score))
            except ValueError:
                return False
            return True
        if verb == "race" and tail:
            self.set_race(tail); return True
        if verb == "class" and tail:
            self.set_class(tail); return True
        if verb == "align" and tail:
            self.set_alignment(tail); return True
        if verb == "name":
            self.set_name(tail); return True
        if verb == "gender":
            self.set_gender(tail); return True
        if verb == "level" and tail:
            try:
                return self.set_level(int(tail))
            except ValueError:
                return False
        if verb == "rerollhp":
            self.reroll_hp(); return True
        if verb == "handedness":
            self.roll_handedness(); return True
        if verb == "exstr":
            self.roll_exceptional_strength(); return True
        if verb == "age" and tail:
            try:
                self.set_age_level(int(tail))
            except ValueError:
                return False
            return True
        if verb == "addweapon" and tail:
            self.add_weapon(tail); return True
        if verb == "rmweapon" and tail:
            self.remove_weapon(tail); return True
        if verb == "wpnup" and tail:
            self.raise_weapon(tail); return True
        if verb == "wpndown" and tail:
            self.lower_weapon(tail); return True
        if verb == "respec" and tail:
            self.respecialise(tail); return True
        if verb == "addgroup" and tail:
            self.add_weapon_group(tail); return True
        if verb == "rmgroup" and tail:
            self.remove_weapon_group(tail); return True
        if verb == "addshieldprof" and tail:
            self.add_shield_prof(tail); return True
        if verb == "rmshieldprof" and tail:
            self.remove_shield_prof(tail); return True
        if verb == "addarmorprof" and tail:
            self.add_armor_prof(tail); return True
        if verb == "rmarmorprof" and tail:
            self.remove_armor_prof(tail); return True
        if verb == "learnstyle" and tail:
            self.learn_style(tail); return True
        if verb == "forgetstyle" and tail:
            self.forget_style(tail); return True
        if verb == "styleup" and tail:
            self.specialise_style(tail); return True
        if verb == "styledown" and tail:
            self.despecialise_style(tail); return True
        if verb == "addunarmed" and tail:
            self.add_unarmed(tail); return True
        if verb == "rmunarmed" and tail:
            self.remove_unarmed(tail); return True
        if verb == "unarmedup" and tail:
            self.raise_unarmed(tail); return True
        if verb == "unarmeddown" and tail:
            self.lower_unarmed(tail); return True
        if verb == "addtalent" and tail:
            self.add_talent(tail); return True
        if verb == "addtalentnwp" and tail:
            self.add_talent(tail, "nonweapon"); return True
        if verb == "rmtalent" and tail:
            self.remove_talent(tail); return True
        if verb == "ambi":
            self.toggle_ambidexterity(); return True
        if verb == "addprof" and tail:
            self.add_proficiency(tail); return True
        if verb == "rmprof" and tail:
            self.remove_proficiency(tail); return True
        if verb == "profplus" and tail:
            self.add_proficiency_slot(tail); return True
        if verb == "profminus" and tail:
            self.remove_proficiency_slot(tail); return True
        if verb == "money":
            self.roll_money(); return True
        if verb == "buy" and tail:
            self.buy_item(tail); return True
        if verb == "sell" and tail:
            self.sell_item(tail); return True
        if verb == "wear" and tail:
            self.toggle_worn(tail); return True
        if verb == "addspell" and tail:
            self.add_spell(tail); return True
        if verb == "rmspell" and tail:
            self.remove_spell(tail); return True
        return False

"""monster_abilities.py — surface a monster's special abilities from its prose.

Phase C of the monster v2 plan (docs/monster-mode-plan.md). ~30% of MM
``special_attacks`` / ``special_defenses`` fields are bare pointers ("See below"),
with the real mechanics in the Combat prose; the prose recon found the mechanics are
present (89% of pointers have Combat text) but unstructured. This module reads the
Combat + ability text and tags it — a fixed vocabulary of ability *types* (breath,
gaze, poison, level drain, …) and the saving throws it calls for — so the sheet can
show them as chips over the Combat panel. It never rewrites the prose: the verbatim
text stays the source of truth; the chips are a scannable index onto it.

Pure and Qt-free, like char_rules / monster_tiers — it reads a ``Monster`` and
returns plain strings. The view (monster_html) renders the chips; app.py isn't
involved.
"""
import re
from dataclasses import dataclass

from monster import Monster

#: Ability *type* -> a pattern that means the monster has it. Order is display order;
#: matching is case-insensitive against the combined Combat / special-attack /
#: special-defense text. Patterns are deliberately loose (an ability is worth a chip
#: whether the prose says "poison" or "poisonous") but anchored to avoid the obvious
#: false friends ("fear" not "fearsome", a real "gaze" not "gazes at the horizon").
_ABILITY_VOCAB = [
    ("Breath weapon", r"breath weapon|breathes\b"),
    ("Gaze attack", r"\bgaze\b"),
    ("Poison", r"\bpoison(?:ous)?\b"),
    ("Paralysis", r"paraly[sz]"),
    ("Level drain", r"(?:energy|level)s?\s+drain|drain(?:s|ing)?\s+(?:\w+\s+){0,3}(?:level|energ)"),
    ("Petrification", r"petrif|turn(?:s|ed)?\s+(?:\w+\s+){0,3}to\s+stone"),
    ("Regeneration", r"regenerat"),
    ("Disease", r"\bdisease"),
    ("Charm", r"\bcharm"),
    ("Fear", r"\bfear\b|cause[s]?\s+fear|radiate[s]?\s+fear"),
    ("Blood drain", r"blood\s+drain|drain(?:s)?\s+blood"),
    ("Swallow whole", r"swallow(?:ed|s)?\s+(?:whole|its|a|the|prey)"),
    ("Constriction", r"constrict"),
    ("Invisibility", r"invisib"),
    ("Surprise", r"\bsurprise[ds]?\b"),
    ("Spell-like", r"spell-?like|cast[s]?\s+(?:spells|it|the|as)"),
]

#: Saving-throw category -> the keyword that identifies it in a "save vs. X" phrase.
#: Checked in order; the first keyword found in the extracted phrase wins, which folds
#: the ragged prose ("save vs. spells halves", "vs. breath weapon reduces …") onto a
#: clean category chip.
_SAVE_CATS = [
    ("poison", "Poison"),
    ("paralyz", "Paralyzation"), ("paralys", "Paralyzation"),
    ("death", "Death Magic"),
    ("petrif", "Petrification"),
    ("polymorph", "Polymorph"),
    ("breath", "Breath Weapon"),
    ("rod", "Rod/Staff/Wand"), ("staff", "Rod/Staff/Wand"), ("wand", "Rod/Staff/Wand"),
    ("spell", "Spells"),
]

_SAVE_VS = re.compile(
    r"sav(?:e|es|ing)\s+(?:throws?\s+)?(?:vs\.?|versus|against)\s+([a-z][a-z' -]{2,28})",
    re.IGNORECASE)

#: "-2 penalty to their saving throw", "save at -4", "+2 bonus to saves" — a signed
#: modifier attached to a save.
_SAVE_MOD = re.compile(
    r"([+-]\d+)\s+(?:penalty\s+|bonus\s+)?(?:to\s+(?:its|their|the|all|each)?\s*)?"
    r"sav(?:e|es|ing)|sav(?:e|es|ing)(?:\s+throws?)?\s+(?:at\s+)?(?:a\s+)?([+-]\d+)",
    re.IGNORECASE)


def _text(m: Monster) -> str:
    """The prose an ability chip can be read from: Combat, the terse attack / defense
    fields (which carry the ability name even when they point 'See below'), and the
    description — a creature written up as one flowing paragraph (the Gauth, a bird)
    keeps its mechanics there, not in Combat."""
    return " ".join((m.combat or "", m.special_attacks or "", m.special_defenses or "",
                     m.description or ""))


def ability_types(m: Monster):
    """The ability-type chips present in the monster's text, in vocabulary order,
    de-duplicated."""
    text = _text(m)
    return [label for label, pat in _ABILITY_VOCAB if re.search(pat, text, re.IGNORECASE)]


def _classify_save(phrase: str):
    """The canonical save category for a "vs. …" phrase, chosen by the *earliest*
    keyword in it — so "vs. petrification or be paralyzed" reads as Petrification
    (the head noun), not Paralyzation (a trailing clause the greedy capture caught)."""
    low = phrase.lower()
    best, best_pos = None, len(low) + 1
    for key, cat in _SAVE_CATS:
        i = low.find(key)
        if 0 <= i < best_pos:
            best, best_pos = cat, i
    return best


def saving_throws(m: Monster):
    """The saving-throw chips the text calls for — canonical categories from its
    "save vs. …" phrases, plus any signed save modifier ("-2 to saves"). Ordered,
    de-duplicated; the categories follow _SAVE_CATS order, the modifiers after."""
    text = _text(m)
    cats, seen = [], set()
    for phrase in _SAVE_VS.findall(text):
        cat = _classify_save(phrase)
        if cat and cat not in seen:
            seen.add(cat)
            cats.append(f"Save vs. {cat}")
    mods = []
    for a, b in _SAVE_MOD.findall(text):
        mod = a or b
        chip = f"Save {mod.replace('-', '−')}"      # minus sign for display
        if mod and chip not in mods:
            mods.append(chip)
    # keep categories in _SAVE_CATS order for a stable chip row
    order = [f"Save vs. {c}" for _k, c in _SAVE_CATS]
    cats.sort(key=lambda c: order.index(c) if c in order else 99)
    return cats + mods


def chips(m: Monster):
    """All chips for the Combat panel: ability types then saving throws. Empty list
    when the prose surfaces nothing (a plain melee brute)."""
    return ability_types(m) + saving_throws(m)


# ── structured per-ability detail (name · save · damage · range · frequency) ──
#
# The chips say *which* abilities a monster has; the sheet's Special Abilities card
# wants the mechanics. Rather than parse the prose into fields (brittle), each ability
# keeps the **source sentence** from Combat and highlights the facts extracted from it
# — so a bad parse is visible next to the author's own words, which stay authoritative.

_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“])")

#: Damage: dice (2d6, 1d4+1) or a "N-M points/hp" range.
_DAMAGE = re.compile(r"\b\d+d\d+(?:[+-]\d+)?\b|\b\d+-\d+(?=\s+(?:points|hp|hit points))", re.I)
#: Range / area: "30 feet", "60-foot cone", "10' radius", "within 5 yards".
_RANGE = re.compile(
    r"\b\d+[- ]?(?:foot|feet|ft\.?|yards?|yds?\.?|inch(?:es)?|')"
    r"(?:[- ]?(?:cone|radius|line|diameter|wide|long|range|sphere|square|area))?", re.I)
#: Frequency: "3 times per day", "once per round", "1/turn", "at will".
_FREQUENCY = re.compile(
    r"\bat will\b|\b(?:once|twice|thrice|\d+ times?)\s+(?:per|a|every|each)\s+"
    r"(?:round|turn|day|hour|week)\b|\b\d+\s*/\s*(?:round|turn|day)\b", re.I)


@dataclass
class Ability:
    """One special ability: its type ``name``, the ``text`` it was read from, and the
    facts highlighted out of that text (blank where not found)."""
    name: str
    text: str
    save: str = ""
    damage: str = ""
    range: str = ""
    frequency: str = ""

    def facts(self):
        """The non-empty extracted facts, damage first, then range/frequency, save
        last — the order the card renders their chips in."""
        return [f for f in (self.damage, self.range, self.frequency, self.save) if f]


def _sentences(text: str):
    return [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]


def _first(pattern, text: str) -> str:
    m = pattern.search(text)
    return " ".join(m.group(0).split()) if m else ""


def _save_in(text: str) -> str:
    for phrase in _SAVE_VS.findall(text):
        cat = _classify_save(phrase)
        if cat:
            return f"Save vs. {cat}"
    m = _SAVE_MOD.search(text)
    if m:
        return "Save " + (m.group(1) or m.group(2)).replace("-", "−")
    return ""


def _extract(name: str, text: str) -> Ability:
    return Ability(name=name, text=text, save=_save_in(text),
                   damage=_first(_DAMAGE, text), range=_first(_RANGE, text),
                   frequency=_first(_FREQUENCY, text))


def abilities(m: Monster):
    """Structured detail for each ability whose mechanics the Combat prose actually
    pins down: the sentence naming it (plus the next one when that sentence carries no
    save or damage — the numbers often land in the following line), with save/damage/
    range/frequency highlighted. Only abilities that yield at least one fact are
    returned, so the card stays mechanics — the bare "it's immune to charm" mentions
    stay in the chips (the index) and the full prose. Ordered by the vocabulary.

    Reads Combat and the description (a one-paragraph creature keeps its mechanics in
    description), so the Gauth's eye rays surface wherever the writeup landed."""
    sents = _sentences("\n".join(x for x in (m.combat, m.description) if x))
    out = []
    for label, pat in _ABILITY_VOCAB:
        rx = re.compile(pat, re.IGNORECASE)
        idx = next((i for i, s in enumerate(sents) if rx.search(s)), None)
        if idx is None:
            continue
        window = sents[idx]
        if not _save_in(window) and not _DAMAGE.search(window) and idx + 1 < len(sents):
            window = window + " " + sents[idx + 1]      # mechanics often spill to the next line
        ability = _extract(label, window)
        if ability.facts():
            out.append(ability)
    return out

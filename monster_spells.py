"""monster_spells.py — link a monster's spell-like abilities to the compendium.

Phase D of the monster v2 plan (docs/monster-mode-plan.md). Casters name their
spell-like abilities as bare spell names in the ability fields and Combat prose
(the Pit Fiend: "advanced illusion, animate dead, charm person, … teleport without
error"). This matches those against the 2e ``spells`` compendium so the sheet can
render each as a link into the Spell Compendium screen.

The match has to stay *reliable*. Many single-word spell names are also ordinary
English words (armor, strength, light, sleep, fear), so naive scanning is useless
(measured: "addition" and "armor" dominate the hits). Two rules keep it clean:

* **Multi-word** names (which effectively never occur by accident — "dispel magic",
  "charm person", "teleport without error") always match.
* **Single-word** names match only when a **casting cue** sits nearby — "once a day",
  "three times a day", "at will", "casts …", "spell-like". That catches the green
  dragon's "suggestion once a day" and "entangle once a day" without linking the
  "light" in "sensitive to bright light".

Longest-match wins ("improved invisibility" over "invisibility"), and hits render
with the compendium's own capitalized name ("Charm Person"), not the prose casing.

Pure and Qt-free: ``build_index`` compiles a matcher from the compendium's names
(passed in by app.py — no DB here), ``find`` returns the ordered hits, and the view
renders them as ``dnd:///spell/<slug>`` links. The anchor slug comes from
spellsscreen_html (which owns the ``id=`` targets) so links can't drift from ids.
"""
import re
from dataclasses import dataclass

from slugs import slug as spell_slug

#: Single-word spell names too ambiguous to link *even beside a casting cue* — the
#: monster-trait words whose innate description reads like a cast ("the ogre
#: regenerates 3 hp per round", "healed by fire", "in addition, once per day",
#: "strength drain") and so collide with real spells (Regenerate, Heal, Addition,
#: Strength). Words that are merely common but read plainly when *not* cast (fear,
#: slow, sleep, light, …) are NOT here — cue-gating already keeps "attacks without
#: fear" out while linking the beholder's "Fear (as wand)". Multi-word names never
#: need listing.
_STOPLIST = frozenset({
    "addition", "armor", "direct", "heal", "regenerate", "strength", "vision", "item",
})

#: A casting/frequency cue that promotes a single-word spell name to a real match.
#: "(as spell)" / "(as a wand)" are how the MM tags spell-like eye rays and gaze
#: effects (the beholder's numbered eye list) — strong signals a bare word is a spell.
_CAST_CUE = re.compile(
    r"\b(?:once|twice|thrice)\s+(?:a|per|each|every)\s+(?:day|round|turn|week)\b"
    r"|\btimes?\s+(?:a|per|each|every)\s+(?:day|round|turn|week)\b"
    r"|\bat\s+will\b|\bper\s+day\b|\bspell-?like\b|\bcast(?:s|ing)?\b|\bonce\s+per\b"
    r"|\bas\s+(?:a\s+|the\s+)?(?:\w+\s+)?spell\b|\bas\s+(?:a\s+)?wand\b",
    re.IGNORECASE)

#: How far from a single-word match a cue may sit (chars) — a clause or two. Wide
#: enough that one "(as spell)" tag carries to the adjacent items in a numbered list.
_CUE_WINDOW = 64


@dataclass(frozen=True)
class SpellIndex:
    """A compiled spell-name matcher: separate multi-word and single-word alternation
    regexes (single-word matches are cue-gated), and slug -> canonical-name for the
    display capitalization."""
    multi: "re.Pattern"
    single: "re.Pattern"
    names: dict          # slug -> canonical compendium name

    def __bool__(self):
        return bool(self.names)


def _compile(names):
    if not names:
        return None
    ordered = sorted(names, key=lambda n: (-len(n), n.lower()))
    return re.compile(r"\b(" + "|".join(re.escape(n) for n in ordered) + r")\b", re.IGNORECASE)


def build_index(names) -> SpellIndex:
    """Compile a matcher from compendium spell names. Multi-word and single-word names
    go into separate regexes (each longest-first, so the regex prefers the longer name
    at a position); ``names`` maps each slug to its canonical capitalization."""
    clean = {n.strip() for n in names if n and n.strip()}
    multi = [n for n in clean if len(n.split()) >= 2]
    single = [n for n in clean if len(n.split()) == 1 and n.lower() not in _STOPLIST]
    by_slug = {}
    for n in clean:                       # first canonical name wins a slug
        by_slug.setdefault(spell_slug(n), n)
    return SpellIndex(multi=_compile(multi), single=_compile(single), names=by_slug)


def _has_cue(text: str, start: int, end: int) -> bool:
    return _CAST_CUE.search(text, max(0, start - _CUE_WINDOW), end + _CUE_WINDOW) is not None


#: The Monster prose fields a spell-like ability can be named in. Spells turn up in the
#: terse attack/defense fields, the Combat prose, *and* the description/ecology (a
#: caster's spell list is often written into the flavor, not Combat), so scan them all.
_SEARCH_FIELDS = ("combat", "special_attacks", "special_defenses",
                  "description", "habitat_society", "ecology")


def find_in(monster, index: SpellIndex):
    """The spells a Monster names, across all its prose (see _SEARCH_FIELDS) — so a
    caster whose spells sit in its description/ecology rather than Combat still links.
    The single-word casting-cue gate keeps flavor prose from over-matching."""
    text = " ".join(v for v in (getattr(monster, f, "") for f in _SEARCH_FIELDS) if v)
    return find(text, index)


def find(text: str, index: SpellIndex):
    """The distinct spells named in ``text``, as (canonical_name, slug) in order of
    first appearance. Multi-word names always count; single-word names count only when
    a casting cue is near. Empty when the text names none (or the index is empty)."""
    if not index or not text:
        return []
    hits, spans = {}, []                  # start position -> name; multi-word spans
    if index.multi:
        for m in index.multi.finditer(text):
            hits[m.start()] = m.group(1)
            spans.append((m.start(), m.end()))
    if index.single:
        for m in index.single.finditer(text):
            inside = any(a <= m.start() < b for a, b in spans)   # e.g. within "improved invisibility"
            if not inside and _has_cue(text, m.start(), m.end()):
                hits[m.start()] = m.group(1)

    out, seen = [], set()
    for pos in sorted(hits):
        slug = spell_slug(hits[pos])
        if slug not in seen:
            seen.add(slug)
            out.append((index.names.get(slug, hits[pos]), slug))
    return out

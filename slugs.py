"""slugs.py — anchor ids for the two long reference screens.

The spell compendium and the proficiency codex are each one enormous HTML document
that app.py writes to a temp file and loads as a `file://` URL, so jumping to an
entry means scrolling to an `id=`. Three separate places have to agree on what that
id is: the screen that *emits* it, whatever *links* to it, and `navigation.py`, which
turns a `dnd:///spell/<slug>` click into a `spells#spell-<slug>` destination.

They used to agree by `monster_spells` — a logic module — importing `spell_slug` from
`spellsscreen_html`, a *view* module. The instinct was right (one owner for the slug,
so links can't drift from the ids they point at) but it pointed the dependency the
wrong way through the layers: the monster stack couldn't be imported without dragging
in the spell screen's CSS. See docs/audit-2-plan.md finding 6.

Both screens had independently written the same normaliser, differing only in whether
they guarded `None`. There's one now, and the `id=` prefixes live beside it, so the
anchor and the link to it are built by the same function.

Pure, dependency-free, bottom of the layering — importable from a view or a logic
module without either implying anything about the other.
"""
import re

#: Prefixes distinguishing the two anchor namespaces within their documents.
SPELL_PREFIX = "spell-"
PROF_PREFIX = "prof-"

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slug(name) -> str:
    """Normalise a name to an anchor-safe slug.

    'Cone of Cold' -> 'cone-of-cold', 'Bowyer/Fletcher' -> 'bowyer-fletcher'.
    Coerces, so a missing name gives "" rather than raising — the callers feed this
    straight from parsed rulebook text, where a blank is ordinary.
    """
    return _NON_ALNUM.sub("-", str(name or "").lower()).strip("-")


def spell_anchor(name) -> str:
    """The `id=` the spell compendium emits for a spell, and the fragment that
    scrolls to it. 'Cone of Cold' -> 'spell-cone-of-cold'."""
    return SPELL_PREFIX + slug(name)


def prof_anchor(name) -> str:
    """The `id=` the proficiency codex emits, and the sidebar's link target.
    'Bowyer/Fletcher' -> 'prof-bowyer-fletcher'."""
    return PROF_PREFIX + slug(name)

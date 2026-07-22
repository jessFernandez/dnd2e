"""theme.py — the app's colours, in one place.

Two things live here.

**The books.** Each rulebook has a name and three colours, in four different places
before this module existed: a vivid foreground for the sidebar tree, a saturated
accent for its table-of-contents page, and a dark tint for its rows in the search
and bookmark lists. Those were four separate dicts (three in `app.py`, one in
`browse_lists.py`) plus a fifth copy of the colours inline in `splash_html.py` and a
second copy of the *names* alongside it — and the names had already drifted, so the
splash screen said "Skills & Powers" while every other surface said "Skills and
Powers". One `Book` record per book now, spelled the way the rulebook DB spells it.

**The palette.** The neutral ramp the screens are built from. These are the values
that appear in three or more view modules; a colour used by one screen is that
screen's business and stays there (of ~237 distinct colours in the view layer, 178
appear in exactly one file).

## Why the CSS still has hex literals in it

This module is the *reference*, not yet the single source, and that's deliberate.
Most of the view layer's CSS sits in plain (non-f) triple-quoted strings, where
interpolating `{TEXT}` would render the brace literally instead of substituting —
a silent visual break, and one the tests wouldn't catch, since they assert on
structure and content rather than colour. Converting those blocks to f-strings means
escaping every brace in a stylesheet, which is a large edit with no way to verify
the result short of looking at the running app.

The safe route, when someone wants it, is CSS custom properties: emit a
`:root { --text: …; }` block from here and have the stylesheets say `var(--text)`.
`var(--x)` survives a plain string untouched, so that migration can be done a screen
at a time. QtWebEngine is Chromium-based and has supported custom properties since
long before the version this ships against. Recorded in docs/audit-2-plan.md finding 5.

Until then: **when you add a colour that another screen already uses, take it from
here.** Everything below is already deduplicated; the CSS blocks are the backlog.
"""
from dataclasses import dataclass

# ── the neutral ramp ─────────────────────────────────────────────────────────
#
# Named for the job, not the hue, so a retheme is a change here rather than a
# search-and-replace. Ordered light to dark within each group.

#: Headings and the text that should read first.
TEXT_BRIGHT = "#e6e9f6"
#: Slightly softer heading text.
TEXT_STRONG = "#e0e2f0"
#: Body text — the default foreground on every screen.
TEXT = "#c8cad8"
#: Secondary text: sub-labels, table captions, the second line of a list row.
TEXT_MUTED = "#8b93b8"
#: Tertiary text: hints, counts, the things you read only if you're looking.
TEXT_DIM = "#6b7290"
#: Placeholder and disabled text — deliberately low contrast.
TEXT_FAINT = "#5a6080"

#: The page behind everything.
BG_DEEPEST = "#13151f"
#: The default screen background.
BG = "#1a1c26"
#: A panel sitting on the background.
BG_PANEL = "#21243a"
#: A raised surface — cards, table headers, the thing under the cursor.
BG_RAISED = "#23263a"
#: The highest surface: hovered cards, open disclosure bodies.
BG_HIGH = "#262a40"

#: Hairlines between rows and cells.
BORDER_SOFT = "#2a2e45"
#: The default border.
BORDER = "#383c52"
#: A border that needs to be seen — focused inputs, active cards.
BORDER_STRONG = "#3a3f58"

#: The app's gold. The builder's accent, the search focus ring, the DM-screen rules.
#: Also read by app.py to tint the sidebar's builder entry.
ACCENT = "#c9a84c"

# ── status / category colours ────────────────────────────────────────────────
#
# Shared by the Actions screen's categories, the DM Screen's callouts and the
# splash cards, which is why they're here rather than in any one of them.

DANGER = "#e05555"      # offense, damage, a failed search
WARNING = "#e07b2a"     # forced movement, cautions
SUCCESS = "#4db870"     # movement, confirmations
INFO = "#5b9bd5"        # defense, informational callouts
SPECIAL = "#a76bcc"     # "other", the odd one out


# ── the books ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Book:
    """One rulebook and the colours that identify it across the UI."""

    code: str
    #: Spelled as the rulebook DB spells it (`pages.book_name`), so the sidebar, the
    #: search results and the splash cards can't disagree about a book's name.
    name: str
    #: Vivid foreground for the book's node in the sidebar tree, and its splash card.
    tree: str
    #: Saturated accent for the book's generated table-of-contents page.
    accent: str
    #: Dark row tint in the search-results and bookmarks lists.
    item: str


BOOKS = {
    "PHB": Book("PHB", "Player's Handbook",        "#5b9bd5", "#2563eb", "#192233"),
    "DMG": Book("DMG", "Dungeon Master Guide",     "#e07b2a", "#ea580c", "#2a1e12"),
    "MM":  Book("MM",  "Monstrous Manual",         "#4db870", "#16a34a", "#132213"),
    "SP":  Book("SP",  "Skills and Powers",        "#c8a828", "#ca8a04", "#232012"),
    "HLC": Book("HLC", "High-Level Campaigns",     "#a76bcc", "#7c3aed", "#1f1430"),
    "TM":  Book("TM",  "Tome of Magic",            "#e05555", "#dc2626", "#261212"),
    "SM":  Book("SM",  "Spells and Magic",         "#3dbfa8", "#0d9488", "#122424"),
    "CT":  Book("CT",  "Combat and Tactics",       "#e0924a", "#b45309", "#251b12"),
    "AEG": Book("AEG", "Arms and Equipment Guide", "#8a9bb0", "#4b5563", "#1c1f24"),
    "ECO": Book("ECO", "Economics of the Realm",   "#c9a84c", "#b7930a", "#22200a"),
}

#: Display order for the splash cards and anywhere else listing every book.
BOOK_ORDER = ("PHB", "DMG", "MM", "SP", "HLC", "TM", "SM", "CT", "AEG", "ECO")

# Fallbacks for a book_code we don't know. In practice unreachable — the sidebar and
# the TOC pages both iterate BOOK_ORDER — which is how the accent fallback managed to
# be two different colours in app.py (a dark red "#8b0000" when generating a TOC, the
# gold everywhere else). Settled on the gold.
DEFAULT_ITEM_COLOR = "#1a1d24"
DEFAULT_TREE_COLOR = "#c9ccd6"
DEFAULT_ACCENT_COLOR = ACCENT


def book(code: str):
    """The Book for a code, or None. Codes arrive from the DB and from link paths,
    so an unknown one is expected rather than exceptional."""
    return BOOKS.get(code or "")


def book_name(code: str, default: str = "") -> str:
    b = book(code)
    return b.name if b else default


def tree_color(code: str) -> str:
    b = book(code)
    return b.tree if b else DEFAULT_TREE_COLOR


def accent_color(code: str) -> str:
    b = book(code)
    return b.accent if b else DEFAULT_ACCENT_COLOR


def item_color(code: str) -> str:
    b = book(code)
    return b.item if b else DEFAULT_ITEM_COLOR

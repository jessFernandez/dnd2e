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

## How the screens get these colours

Through `css_vars()`, which emits a `:root { --text: …; }` block for a screen to
prepend to its `<style>`; the stylesheets then say `var(--text)`. That indirection
is not decoration — it is what made the migration possible at all. Most of the view
layer's CSS sits in plain (non-f) triple-quoted strings, where interpolating
`{TEXT}` would render the brace literally instead of substituting, so converting
those blocks to f-strings would have meant escaping every brace in every stylesheet.
`var(--x)` passes through a plain string untouched, so each declaration could be
swapped in place with no reformatting. QtWebEngine is Chromium-based and has
supported custom properties for years; the splash screen shipped using them first,
which is what showed the route was safe.

Only the colours used by three or more view modules live in `CSS_VARS`. A colour one
screen uses is that screen's business and stays a literal in its own stylesheet —
which is why hex has not disappeared from the view layer and shouldn't.

**When you add a colour another screen already uses, take it from here** — and if it
reaches a third screen, give it a name in `CSS_VARS` rather than a third literal.
The migration was verified colour-neutral by rendering every screen before and
after and comparing with the custom properties resolved back to their values.
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

#: Secondary text on a raised surface — table headers, card sub-labels. Between
#: TEXT_MUTED and TEXT_STRONG; shared by the Actions, Spells and card-grid screens.
TEXT_LABEL = "#8891b5"
#: The inset well a card's body sits in, one step darker than BG_PANEL.
BG_INSET = "#1c1f32"

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


# ── the palette as CSS custom properties ─────────────────────────────────────

#: CSS custom-property name -> the constant above it stands for. Only the colours
#: that appear in three or more view modules are here; a colour one screen uses is
#: that screen's business and stays a literal in its own stylesheet.
CSS_VARS = {
    "text-bright": TEXT_BRIGHT,
    "text-strong": TEXT_STRONG,
    "text": TEXT,
    "text-label": TEXT_LABEL,
    "text-muted": TEXT_MUTED,
    "text-dim": TEXT_DIM,
    "text-faint": TEXT_FAINT,
    "bg-deepest": BG_DEEPEST,
    "bg": BG,
    "bg-inset": BG_INSET,
    "bg-panel": BG_PANEL,
    "bg-raised": BG_RAISED,
    "bg-high": BG_HIGH,
    "border-soft": BORDER_SOFT,
    "border": BORDER,
    "border-strong": BORDER_STRONG,
    "accent": ACCENT,
    "danger": DANGER,
    "warning": WARNING,
    "success": SUCCESS,
    "info": INFO,
    "special": SPECIAL,
}


def css_vars() -> str:
    """A ``:root { --text: …; }`` block declaring the shared palette.

    This is what turns the module from a *reference* into the single source the
    docstring above wanted. The obstacle was never QtWebEngine — it is Chromium and
    has supported custom properties for years — but that most of the view layer's
    CSS lives in plain (non-f) triple-quoted strings, where interpolating ``{TEXT}``
    would render the brace literally. ``var(--text)`` passes through such a string
    untouched, so a stylesheet can be migrated a declaration at a time with no
    escaping and no reformatting.

    Prepend it to a screen's ``<style>`` and use ``var(--name)`` in the CSS below.
    """
    body = " ".join(f"--{name}: {value};" for name, value in CSS_VARS.items())
    return ":root { " + body + " }\n"


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

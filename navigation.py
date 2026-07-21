"""navigation.py — the pure navigation layer for a content tab.

Everything here is Qt-free and unit-tested without a running app (see
tests/test_navigation.py); app.py's MainWindow supplies the Qt shell and the
side effects (rendering, showing/hiding the browse pane, opening tabs).

Two pieces:

* ``History`` — a tiny back/forward state machine: a list of destination strings
  plus a cursor. The caller does the rendering; History only tracks position.
* the *destination grammar* — small helpers that classify and translate the
  canonical strings the rest of the app passes around.

A "destination" is the canonical string the app renders: a page_url
("PHB/DD01671.htm"), a book table of contents ("toc:PHB"), the Proficiencies
codex ("proficiencies" / "proficiencies#anchor"), or a full-width screen name
("splash", "dmscreen", "actions", "spells", "charactermancer", "ask").
"""
from dataclasses import dataclass
from enum import Enum
from urllib.parse import unquote

# Built-in reference/tool screens that take the full content width; opening one
# hides the book browser, while a book page or TOC keeps it. Single source of
# truth for that split — see takes_full_width().
FULLWIDTH_SCREENS = frozenset({"splash", "dmscreen", "actions",
                               "spells", "charactermancer", "ask", "monster"})


def link_to_destination(path: str) -> str:
    """Map a dnd:// link path to a canonical destination string.

    Links carry a routing prefix the destinations don't: "toc/PHB" addresses a
    book's contents, "screen/dmscreen" a built-in screen. Everything else (a
    page_url, "proficiencies", …) is already canonical.
    """
    if path.startswith("toc/"):
        return "toc:" + path[len("toc/"):]
    if path.startswith("screen/"):
        return path[len("screen/"):]
    if path.startswith("spell/"):
        return "spells#spell-" + path[len("spell/"):]   # a monster's spell-like link
    return path


def takes_full_width(dest: str) -> bool:
    """Whether a destination is a full-width reference/tool screen (so the browse
    pane makes way for it) rather than a book page or TOC (which keep the pane).

    Proficiencies and the spell compendium are reference screens reached with a
    `#fragment` (a codex anchor / a spell anchor), so they match by prefix too.
    """
    return (dest in FULLWIDTH_SCREENS or dest.startswith("proficiencies")
            or dest.startswith("spells#")       # spells screen scrolled to a spell
            or dest.startswith("monster-"))     # monster-sheet, monster-variant/…


class Trigger(Enum):
    """How the reader arrived at a destination — the browse pane reacts to this."""
    LINK = "link"            # a content-link click (a chip, cross-ref, citation)
    NAVIGATE = "navigate"    # history, next/prev, tree, buttons, session restore
    TAB_CHANGE = "tab"       # switching to — or closing onto — another tab


class Pane(Enum):
    """What should happen to the browse pane."""
    OPEN = "open"            # bring it out so the reader can see where they are
    CLOSE = "close"          # a full-width screen reclaims the width
    LEAVE = "leave"          # don't touch it — respect the reader's choice


def pane_action(dest: str, trigger: Trigger) -> Pane:
    """The browse pane's response to reaching `dest` via `trigger` — the single
    source of truth the reveal, the hide, and the tab-change reconciliation all
    read from.

    A full-width screen always reclaims the width. A book page (or TOC) opens the
    pane only when reached by a link, so the reader sees where the page sits in
    the tree; reaching one any other way (history, next/prev, a tab switch) leaves
    the pane as they left it — a pane deliberately closed stays closed.
    """
    if takes_full_width(dest):
        return Pane.CLOSE
    if trigger is Trigger.LINK:
        return Pane.OPEN
    return Pane.LEAVE


# ── link routing ──────────────────────────────────────────────────────────────
#
# The intent behind a content-link click. route_link() decides *what* the click
# means; MainWindow performs the side effect. Ask/builder routes act in place
# (no history entry); the rest resolve to a destination — opened in a new tab
# when the current page must stay put.

class Route:
    """Base for the tagged results of route_link()."""


@dataclass(frozen=True)
class Ask(Route):
    """Ask the Rules a question (already URL-decoded and trimmed)."""
    question: str


@dataclass(frozen=True)
class AskSetModel(Route):
    """Remember the chosen Ollama model, then re-render the Ask page."""
    model: str


@dataclass(frozen=True)
class AskRefresh(Route):
    """Reset the Ask conversation and re-check Ollama."""


@dataclass(frozen=True)
class AskStop(Route):
    """Cancel the in-flight Ask generation."""


@dataclass(frozen=True)
class CmAction(Route):
    """Apply a Charactermancer action (payload passed through verbatim)."""
    payload: str


@dataclass(frozen=True)
class MonAction(Route):
    """Apply a monster-sheet action (payload passed through verbatim)."""
    payload: str


@dataclass(frozen=True)
class NewTab(Route):
    """Open `dest` in a fresh tab, so the current page stays put."""
    dest: str


@dataclass(frozen=True)
class Navigate(Route):
    """Navigate the current tab to `dest`."""
    dest: str


def route_link(url: str, *, on_jarvis_page: bool) -> Route:
    """Classify a raw dnd:// link path into the intent behind the click.

    Pure counterpart to MainWindow._on_content_navigate. A citation clicked on
    the Jarvis (Ask the Rules) page opens in a new tab so the Q&A stays put, the
    same as an explicitly `newtab/`-tagged link.
    """
    if url.startswith("ask/"):
        return Ask(unquote(url[len("ask/"):]).strip())
    if url.startswith("ask-setmodel/"):
        return AskSetModel(unquote(url[len("ask-setmodel/"):]).strip())
    if url in ("ask-refresh", "ask-new"):
        return AskRefresh()
    if url == "ask-stop":
        return AskStop()
    if url.startswith("cm/"):
        return CmAction(url[len("cm/"):])
    if url.startswith("mon/"):
        return MonAction(url[len("mon/"):])
    if url.startswith("newtab/"):
        return NewTab(link_to_destination(url[len("newtab/"):]))
    dest = link_to_destination(url)
    return NewTab(dest) if on_jarvis_page else Navigate(dest)


# ── monster-sheet actions ─────────────────────────────────────────────────────
#
# The monster sheet's links are a grammar of their own ("mon/set/<field>/<value>",
# "mon/pickvar/<page>/<i>", "mon/tier/<i>"). route_mon() owns that grammar — the
# decoding, the index/id coercion, and what a malformed argument means — leaving
# MainWindow._mon_action a match statement of side effects. Kept here with the rest
# of the link routing, and Qt-free, so the parsing is unit-testable; *policy* (which
# fields may be edited, whether a tier blocks an edit) stays with the monster model.

class MonAct:
    """Base for the tagged results of route_mon()."""


@dataclass(frozen=True)
class MonSet(MonAct):
    """Store an edited stat/prose field. ``value`` is already URL-decoded."""
    field: str
    value: str


@dataclass(frozen=True)
class MonTier(MonAct):
    """Select an HD/age scaling tier; None means the base stat block as written."""
    index: "int | None"


@dataclass(frozen=True)
class MonInit(MonAct):
    """Override the initiative speed factor; None falls back to the size-derived one."""
    value: "int | None"


@dataclass(frozen=True)
class MonPick(MonAct):
    """Import an MM page (its sole creature, or its variant chooser)."""
    page_url: str


@dataclass(frozen=True)
class MonPickVariant(MonAct):
    """Import creature ``index`` from a multi-variant MM page."""
    page_url: str
    index: int


@dataclass(frozen=True)
class MonLoad(MonAct):
    """Open a saved monster."""
    saved_id: int


@dataclass(frozen=True)
class MonDelete(MonAct):
    """Delete a saved monster."""
    saved_id: int


@dataclass(frozen=True)
class MonFamily(MonAct):
    """Open a family sub-picker (Dragon → its types)."""
    family: str


@dataclass(frozen=True)
class MonPicker(MonAct):
    """Go to the monster landing (saved monsters + the MM import list)."""


@dataclass(frozen=True)
class MonNew(MonAct):
    """Start a blank custom monster."""


@dataclass(frozen=True)
class MonSave(MonAct):
    """Save the current monster to the user DB."""


@dataclass(frozen=True)
class MonExport(MonAct):
    """Copy the current monster's Roll20 import JSON to the clipboard."""


def _opt_int(text: str, blank=None):
    """``text`` as an int, or ``blank`` when it is empty or not a number. The sheet's
    own controls can only produce valid values; a malformed one means 'no selection'
    rather than an error the DM would have to see."""
    text = unquote(text or "").strip()
    if not text:
        return blank
    try:
        return int(text)
    except ValueError:
        return blank


def route_mon(payload: str):
    """Classify a monster-sheet link payload (the part after "mon/") into a tagged
    action, or None when it isn't one — an unrecognized verb is ignored, not guessed
    at. ``set`` splits on the *first* slash only: the value is percent-encoded by the
    sheet's monText() helper, so a field's own slashes survive."""
    verb, _, rest = payload.partition("/")
    match verb:
        case "set":
            field, _, raw = rest.partition("/")
            return MonSet(field, unquote(raw)) if field else None
        case "tier":
            return MonTier(None if rest == "base" else _opt_int(rest))
        case "init":
            return MonInit(_opt_int(rest))
        case "pick":
            return MonPick(rest) if rest else None
        case "pickvar":
            page_url, _, idx = rest.rpartition("/")
            i = _opt_int(idx)
            return MonPickVariant(page_url, i) if page_url and i is not None else None
        case "load" | "delete":
            sid = _opt_int(rest)
            if sid is None:
                return None
            return MonLoad(sid) if verb == "load" else MonDelete(sid)
        case "family":
            return MonFamily(rest) if rest else None
        case "import":
            return MonPicker()
        case "new":
            return MonNew()
        case "save":
            return MonSave()
        case "roll20":
            return MonExport()
    return None


class History:
    def __init__(self, entries=None, pos=-1):
        self.entries = list(entries or [])
        self.pos = pos

    def push(self, dest):
        """Record a newly-visited destination, discarding any forward history."""
        del self.entries[self.pos + 1:]
        self.entries.append(dest)
        self.pos = len(self.entries) - 1

    def current(self):
        """The destination currently shown, or None."""
        return self.entries[self.pos] if 0 <= self.pos < len(self.entries) else None

    def can_back(self) -> bool:
        return self.pos > 0

    def can_forward(self) -> bool:
        return self.pos < len(self.entries) - 1

    def back(self):
        """Step back; return the now-current destination, or None if already at start."""
        if not self.can_back():
            return None
        self.pos -= 1
        return self.current()

    def forward(self):
        """Step forward; return the now-current destination, or None if at the end."""
        if not self.can_forward():
            return None
        self.pos += 1
        return self.current()

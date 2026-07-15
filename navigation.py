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
                               "spells", "charactermancer", "ask"})


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
    return path


def takes_full_width(dest: str) -> bool:
    """Whether a destination is a full-width reference/tool screen (so the browse
    pane makes way for it) rather than a book page or TOC (which keep the pane).

    Proficiencies is the Codex reference screen; it carries a `#fragment`, so it
    is matched by prefix rather than membership.
    """
    return dest in FULLWIDTH_SCREENS or dest.startswith("proficiencies")


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
    if url.startswith("newtab/"):
        return NewTab(link_to_destination(url[len("newtab/"):]))
    dest = link_to_destination(url)
    return NewTab(dest) if on_jarvis_page else Navigate(dest)


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

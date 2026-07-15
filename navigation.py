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
from enum import Enum

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

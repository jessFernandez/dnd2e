"""navigation.py — back/forward history for a content tab.

A tiny pure state machine: a list of destination strings plus a cursor. The
caller does the rendering; History only tracks position, so the whole thing is
unit-testable without Qt (see tests/test_navigation.py). A "destination" is the
canonical string the app renders (a page_url, "toc:PHB", "spells", "ask", …).
"""


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

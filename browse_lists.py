"""browse_lists.py — how a page looks as a row in one of the side lists.

The three lists down the left of the window — the browse tree, the search results,
and the bookmarks — all render the same underlying thing: a rulebook page, shown as
a cleaned-up title over its book name, tinted by which book it came from. That
formatting was written out three times inside MainWindow, so a change to it landed
in one list and not the others (docs/audit-2-plan.md finding 2).

This module holds the *decisions* — what text to show, how to trim it, which colour
the row gets. It returns plain data; app.py builds the QListWidgetItem/QTreeWidgetItem
and applies it. Pure and Qt-free, so it's testable without a window.

A row's tint says which book the page came from, so the colours come from
`theme.BOOKS` — the same record the sidebar tree and the book's TOC page read.
"""
import re
from dataclasses import dataclass

import theme

#: Row tint for a page whose book we don't recognise (or that has no book_code).
DEFAULT_ITEM_COLOR = theme.DEFAULT_ITEM_COLOR

#: Foreground for a normal row, and for the "no results"/"search failed" placeholders.
#: Slightly warmer than theme.TEXT — these are Qt widget rows, not web content.
ROW_FG = "#c0c4d4"
MUTED_FG = "#505870"
ERROR_FG = "#c07070"

#: Snippets longer than this are cut, with the last two characters kept for the "…".
SNIPPET_MAX = 120

_TRAILING_PARENS = re.compile(r"\s*\([^)]+\)\s*$")
_WHITESPACE = re.compile(r"\s+")


def display_title(text: str) -> str:
    """A page title with its trailing "(Book Name)" suffix removed.

    Scraped titles carry the book in parentheses — "THAC0 (Player's Handbook)" —
    which is redundant once the row already shows the book underneath, and it pushes
    the part you're actually reading off the end of a narrow list.
    """
    return _TRAILING_PARENS.sub("", text or "").strip()


def snippet(text: str, limit: int = SNIPPET_MAX) -> str:
    """A search snippet flattened to one line and cut to `limit`.

    FTS marks its matches with `**`, which has no meaning in a list widget, and the
    surrounding page text arrives with the original line breaks in it.
    """
    flat = _WHITESPACE.sub(" ", (text or "").replace("**", "")).strip()
    if len(flat) <= limit:
        return flat
    return flat[:limit - 2].rstrip() + "…"


def book_color(book_code: str) -> str:
    """The row tint for a book, falling back for unknown or missing codes."""
    return theme.item_color(book_code)


@dataclass(frozen=True)
class Row:
    """One page as a side-list row: the text to display, the tint, and the page_url
    to navigate to when it's clicked."""
    text: str
    color: str
    page_url: str
    fg: str = ROW_FG


def page_row(page_url: str, title: str, book_name: str, book_code: str,
             snip: str = "") -> Row:
    """A search-result or bookmark row.

    The two lists differ only in whether there's a snippet to show, so they share
    this. The leading two spaces on each line are the lists' left inset — the
    widgets have no padding of their own.
    """
    text = f"  {display_title(title or page_url)}\n  {book_name or ''}"
    trimmed = snippet(snip)
    if trimmed:
        text += f"\n  {trimmed}"
    return Row(text=text, color=book_color(book_code), page_url=page_url)


def search_rows(rows) -> list:
    """Every search result as a Row. `rows` is db.search_pages output:
    (page_url, title, book_name, book_code, snippet)."""
    return [page_row(page_url, title, book_name, book_code, snip)
            for page_url, title, book_name, book_code, snip in rows]


def results_tab_label(count: int) -> str:
    return f"Results ({count})"


def bookmarks_tab_label(count: int) -> str:
    """Bookmarks keeps a bare label at zero — an empty count reads as an error."""
    return f"Bookmarks ({count})" if count else "Bookmarks"

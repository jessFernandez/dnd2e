"""Every page in the rulebook DB must have a route in the browse sidebar.

The sidebar renders a book from its `toc_tree` when it has one. But the site's TOC
XML is not a complete index of its own pages: 25 real content pages across six
books carry a `toc_entries` row and no tree node, so they had no route at all —
among them the *Skills & Powers* ability-score write-ups (Strength, Reason,
Knowledge, Intuition, **Willpower** — the very page whose name the character
builder borrows for Wisdom), *Arms and Equipment*'s Polearms, a *Tome of Magic*
chapter opener, and *Spells and Magic*'s Spheres of Access.

Worse than invisible: reachable by search, then stranded. `_book_page_order` is
built by the same tree walk, and `_adjacent_page` returns None for a url that isn't
in it, so Prev and Next were both dead on exactly those pages.

`_load_topics` now appends whatever the tree misses under an "Other pages" group.
This measures the result against the real corpus — a unit test on synthetic trees
(tests/test_toc.py) can prove the function correct without proving the *shipped
data* is covered, and it was the data that had the hole.
"""
import os

import pytest

import db
import toc

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

#: Books as the sidebar iterates them (theme.BOOK_ORDER, kept literal so a change
#: to that list shows up here as a failure rather than silently narrowing the sweep).
BOOKS = ("PHB", "DMG", "MM", "SP", "HLC", "TM", "SM", "CT", "AEG", "ECO")


@pytest.fixture(scope="module")
def conn():
    c = db.connect(RULES_DB)
    yield c
    c.close()


def _routes(conn, book_code) -> set:
    """Every page_url the sidebar can reach for a book: its tree, plus the
    `toc_entries` rows _add_unlisted appends under "Other pages"."""
    tree = toc.build_tree(db.toc_tree(conn, book_code))
    entries = db.toc_entries(conn, book_code)
    if not tree:
        return {u for u, _s in entries}          # flat fallback renders them all
    return toc.tree_page_urls(tree) | {
        u for u, _s in toc.entries_missing_from_tree(tree, entries)}


@needs_db
def test_theme_book_order_still_matches_the_books_in_the_db(conn):
    """Guards the sweep below: a book added to the DB but not to BOOKS would be
    skipped here and could go unreachable unnoticed."""
    in_db = {r[0] for r in conn.execute("SELECT DISTINCT book_code FROM pages")}
    assert in_db == set(BOOKS)


@needs_db
def test_no_page_is_unreachable_from_the_browse_tree(conn):
    unreachable = {}
    for book_code in BOOKS:
        pages = {r[0] for r in conn.execute(
            "SELECT page_url FROM pages WHERE book_code = ?", (book_code,))}
        missing = sorted(pages - _routes(conn, book_code))
        if missing:
            unreachable[book_code] = missing
    assert unreachable == {}, (
        "pages with no route in the browse sidebar: "
        + "; ".join(f"{b} ({len(v)}): {v[:3]}" for b, v in unreachable.items()))


@needs_db
def test_the_unlisted_group_is_what_recovers_them(conn):
    """The regression, sized. Without the "Other pages" group these 25 pages have no
    route; the count is pinned so a re-scrape that widens the gap is visible."""
    recovered = {}
    for book_code in BOOKS:
        tree = toc.build_tree(db.toc_tree(conn, book_code))
        if not tree:
            continue
        missing = toc.entries_missing_from_tree(tree, db.toc_entries(conn, book_code))
        if missing:
            recovered[book_code] = len(missing)

    assert recovered == {"DMG": 1, "SP": 18, "HLC": 2, "TM": 2, "SM": 1, "AEG": 1}
    assert sum(recovered.values()) == 25


@needs_db
def test_the_skills_and_powers_ability_pages_are_among_them(conn):
    """Named because they matter most: the house rules are built on these, and the
    builder already borrows this page's name for Wisdom."""
    tree = toc.build_tree(db.toc_tree(conn, "SP"))
    missing = dict(toc.entries_missing_from_tree(tree, db.toc_entries(conn, "SP")))
    titles = " ".join(missing.values())
    for ability in ("Strength", "Reason", "Knowledge", "Intuition", "Willpower"):
        assert ability in titles, f"{ability} (Skills and Powers) should be recovered"


@needs_db
def test_eco_still_renders_from_the_flat_fallback(conn):
    """Economics of the Realm has *no* toc_tree rows at all, so it takes the flat
    `toc_entries` layout. That path predates this change and must keep working —
    it is the only book that depends on it."""
    assert db.toc_tree(conn, "ECO") == []
    pages = {r[0] for r in conn.execute(
        "SELECT page_url FROM pages WHERE book_code = 'ECO'")}
    assert pages and pages <= _routes(conn, "ECO")

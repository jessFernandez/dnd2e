"""Tests for the data-access layer (db.py).

The rulebook-DB tests read the bundled database and skip if it's absent; the
bookmark tests use a throwaway temp DB and always run. This is the coverage that
used to be impossible while the SQL was buried inside MainWindow.
"""
import os
import sqlite3

import pytest

import db
import rules_agent

RULES_DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

THAC0_PAGE = "PHB/DD01671.htm"   # a stable known page (title "THAC0", book PHB)


@pytest.fixture
def conn():
    c = db.connect(RULES_DB)
    yield c
    c.close()


# ── pages ─────────────────────────────────────────────────────────────────────

@needs_db
def test_get_page_returns_content(conn):
    row = db.get_page(conn, THAC0_PAGE)
    assert row is not None
    assert "THAC0" in (row["title"] or "")
    assert row["book_code"] == "PHB"
    assert row["content_html"]


@needs_db
def test_get_page_missing_is_none(conn):
    assert db.get_page(conn, "PHB/DOES_NOT_EXIST.htm") is None


@needs_db
def test_page_meta_has_no_html(conn):
    row = db.page_meta(conn, THAC0_PAGE)
    assert set(row.keys()) == {"title", "book_name", "book_code"}


@needs_db
def test_search_pages_finds_and_snippets(conn):
    rows = db.search_pages(conn, "fireball")
    assert rows, "expected fireball hits"
    assert "snip" in rows[0].keys()
    assert any("fireball" in (r["title"] or "").lower()
               or "fireball" in (r["snip"] or "").lower() for r in rows)


@needs_db
def test_search_pages_bad_query_does_not_raise(conn):
    # An FTS-hostile query must fall back / return [] rather than throw.
    assert isinstance(db.search_pages(conn, '"'), list)
    assert isinstance(db.search_pages(conn, "   "), list)


# ── toc / chapters ────────────────────────────────────────────────────────────

@needs_db
def test_toc_entries_and_markers(conn):
    entries = db.toc_entries(conn, "PHB")
    assert len(entries) > 50
    markers = db.chapter_markers(conn, "PHB")
    assert markers and all("--" in m["subtopic"] for m in markers)


@needs_db
def test_chapter_keyword_for_page(conn):
    kw = db.chapter_keyword_for_page(conn, "PHB", THAC0_PAGE)
    assert kw is not None and kw.lower().startswith("chapter")


# ── house rules ───────────────────────────────────────────────────────────────

@needs_db
def test_all_house_rules(conn):
    rows = db.all_house_rules(conn)
    assert len(rows) >= 20
    assert set(rows[0].keys()) == {"category", "rule_text"}


@needs_db
def test_house_rules_book_and_chapter_roundtrip(conn):
    book_rules = db.house_rules_for_book(conn, "PHB")
    assert book_rules, "PHB should have house rules"
    kw = next((r["chapter_keyword"] for r in book_rules if r["chapter_keyword"]), None)
    if kw:
        chapter_rules = db.chapter_house_rules(conn, "PHB", kw)
        assert chapter_rules, f"chapter {kw!r} should resolve to rules"


# ── spells ────────────────────────────────────────────────────────────────────

@needs_db
def test_all_spells_shape_and_sort(conn):
    spells = db.all_spells(conn)
    assert len(spells) == 875
    assert {"name", "caster", "level", "spheres", "specializations"} <= set(spells[0])
    keys = [(s["caster"], s["level"], s["name"]) for s in spells]
    assert keys == sorted(keys)


# ── bookmarks (temp DB, no rulebook needed) ───────────────────────────────────

def test_bookmark_lifecycle(tmp_path):
    conn = db.connect(tmp_path / "user.db")
    db.ensure_bookmarks_schema(conn)

    assert db.bookmark_urls(conn) == []
    assert db.is_bookmarked(conn, "PHB/A.htm") is False

    assert db.toggle_bookmark(conn, "PHB/A.htm") is True      # now on
    assert db.is_bookmarked(conn, "PHB/A.htm") is True
    db.add_bookmark(conn, "PHB/A.htm")                        # idempotent
    assert db.bookmark_urls(conn) == ["PHB/A.htm"]

    db.add_bookmark(conn, "DMG/B.htm")
    assert set(db.bookmark_urls(conn)) == {"PHB/A.htm", "DMG/B.htm"}

    assert db.toggle_bookmark(conn, "PHB/A.htm") is False     # now off
    assert db.bookmark_urls(conn) == ["DMG/B.htm"]
    db.remove_bookmark(conn, "DMG/B.htm")
    assert db.bookmark_urls(conn) == []
    conn.close()


def test_migrate_legacy_bookmarks(tmp_path):
    # A legacy rulebook DB that still has a bookmarks table.
    legacy = sqlite3.connect(tmp_path / "old.db")
    legacy.execute("CREATE TABLE bookmarks (page_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    legacy.executemany("INSERT INTO bookmarks (page_url) VALUES (?)", [("PHB/X.htm",), ("DMG/Y.htm",)])
    legacy.commit()

    user = db.connect(tmp_path / "user.db")
    db.ensure_bookmarks_schema(user)
    db.migrate_legacy_bookmarks(user, legacy)
    assert set(db.bookmark_urls(user)) == {"PHB/X.htm", "DMG/Y.htm"}

    # Running again is a no-op (user DB already populated).
    db.migrate_legacy_bookmarks(user, legacy)
    assert len(db.bookmark_urls(user)) == 2
    user.close(); legacy.close()

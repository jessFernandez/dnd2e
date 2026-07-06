"""db.py — the app's data-access layer.

Every SQL query lives here so the rest of the app talks to typed functions, the
schema has a single owner, and the data logic is unit-testable without a running
Qt application (see tests/test_db.py).

Two databases are involved:
  • the bundled rulebook DB — pages, pages_fts, toc_entries, house_rules, spells
  • a per-user writable DB — bookmarks (survives app updates)

Functions take an open connection as their first argument rather than owning one,
which keeps them thread-safe (each QThread worker opens its own connection) and
trivial to test (pass a connection to a temp DB).
"""
import re
import sqlite3

# Shared SQL fragment: TOC rows that mark the start of a chapter/part/appendix.
_CHAPTER_MARKER = (
    "(subtopic LIKE '%-- Chapter %' OR subtopic LIKE '%-- Part %' "
    "OR subtopic LIKE '%-- Book %' OR subtopic LIKE '%-- Appendix %')"
)
_CHAPTER_KEYWORD_RE = re.compile(r"(Chapter\s+\d+|Part\s+\d+)", re.I)


def connect(path) -> sqlite3.Connection:
    """Open a connection with row access by name and index (sqlite3.Row)."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


# ── pages ─────────────────────────────────────────────────────────────────────

def get_page(conn, page_url):
    """Full page row (content_html, title, book_name, book_code) or None."""
    return conn.execute(
        "SELECT content_html, title, book_name, book_code FROM pages WHERE page_url = ?",
        (page_url,),
    ).fetchone()


def page_meta(conn, page_url):
    """Lightweight page row (title, book_name, book_code) or None — no HTML."""
    return conn.execute(
        "SELECT title, book_name, book_code FROM pages WHERE page_url = ?",
        (page_url,),
    ).fetchone()


def search_pages(conn, query: str, limit: int = 300):
    """Full-text search over page content; rows carry a highlighted snippet.

    Tries the query as a quoted phrase first, then falls back to a bare-token
    query if that trips an FTS5 syntax error. Returns [] on failure."""
    sql = (
        "SELECT p.page_url, p.title, p.book_name, p.book_code, "
        "       snippet(pages_fts, 2, '**', '**', '…', 25) AS snip "
        "FROM   pages_fts JOIN pages p ON pages_fts.page_url = p.page_url "
        "WHERE  pages_fts MATCH ? ORDER BY rank LIMIT ?"
    )
    for match in (f'"{query.replace(chr(34), "")}"', " ".join(query.split())):
        try:
            return conn.execute(sql, (match, limit)).fetchall()
        except sqlite3.Error:
            continue
    return []


# ── table of contents ───────────────────────────────────────────────────────

def toc_entries(conn, book_code: str):
    """Distinct (page_url, subtopic) TOC rows for a book, in page order."""
    return conn.execute(
        "SELECT DISTINCT te.page_url, te.subtopic FROM toc_entries te "
        "WHERE te.book_code = ? ORDER BY te.page_url",
        (book_code,),
    ).fetchall()


def chapter_markers(conn, book_code: str):
    """(subtopic, page_url) rows that open a chapter/part/book/appendix."""
    return conn.execute(
        f"SELECT te.subtopic, te.page_url FROM toc_entries te "
        f"WHERE te.book_code = ? AND {_CHAPTER_MARKER} ORDER BY te.page_url",
        (book_code,),
    ).fetchall()


def chapter_keyword_for_page(conn, book_code: str, page_url: str):
    """The 'Chapter N' / 'Part N' keyword the page falls under, or None."""
    row = conn.execute(
        f"SELECT subtopic FROM toc_entries WHERE book_code = ? AND page_url <= ? "
        f"AND {_CHAPTER_MARKER} ORDER BY page_url DESC LIMIT 1",
        (book_code, page_url),
    ).fetchone()
    if not row:
        return None
    m = _CHAPTER_KEYWORD_RE.search(row[0])
    return m.group(1) if m else None


# ── house rules ─────────────────────────────────────────────────────────────

def house_rules_for_book(conn, book_code: str):
    """(chapter_keyword, category, rule_text) rows tagged for a book; [] if none."""
    try:
        return conn.execute(
            "SELECT chapter_keyword, category, rule_text FROM house_rules "
            "WHERE book_codes LIKE ? ORDER BY id",
            (f"%{book_code}%",),
        ).fetchall()
    except sqlite3.Error:
        return []


def chapter_house_rules(conn, book_code: str, chapter_keyword: str):
    """(category, rule_text) rows for one chapter of one book; [] if none/missing."""
    try:
        return conn.execute(
            "SELECT category, rule_text FROM house_rules "
            "WHERE chapter_keyword = ? AND book_codes LIKE ? ORDER BY id",
            (chapter_keyword, f"%{book_code}%"),
        ).fetchall()
    except sqlite3.Error:
        return []


def all_house_rules(conn):
    """(category, rule_text) for every house rule; [] if the table is missing."""
    try:
        return conn.execute(
            "SELECT category, rule_text FROM house_rules ORDER BY id"
        ).fetchall()
    except sqlite3.Error:
        return []


# ── spells ────────────────────────────────────────────────────────────────────

def all_spells(conn) -> list:
    """Every spell as a plain dict, sorted by caster, level, name; [] if missing."""
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM spells ORDER BY caster, level, name")]
    except sqlite3.Error:
        return []


# ── bookmarks (user DB) ─────────────────────────────────────────────────────

def ensure_bookmarks_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS bookmarks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, page_url TEXT UNIQUE, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()


def migrate_legacy_bookmarks(user_conn, rules_conn):
    """One-time copy of bookmarks that used to live in the bundled DB."""
    if user_conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0] != 0:
        return
    try:
        legacy = rules_conn.execute(
            "SELECT page_url FROM bookmarks ORDER BY created_at").fetchall()
    except sqlite3.Error:
        return   # no legacy bookmarks table — nothing to migrate
    for (url,) in legacy:
        user_conn.execute("INSERT OR IGNORE INTO bookmarks (page_url) VALUES (?)", (url,))
    user_conn.commit()


def bookmark_urls(conn) -> list:
    """Bookmarked page_urls, most-recent first."""
    return [r[0] for r in conn.execute(
        "SELECT page_url FROM bookmarks ORDER BY created_at DESC")]


def is_bookmarked(conn, page_url: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM bookmarks WHERE page_url = ?", (page_url,)).fetchone() is not None


def add_bookmark(conn, page_url: str):
    conn.execute("INSERT OR IGNORE INTO bookmarks (page_url) VALUES (?)", (page_url,))
    conn.commit()


def remove_bookmark(conn, page_url: str):
    conn.execute("DELETE FROM bookmarks WHERE page_url = ?", (page_url,))
    conn.commit()


def toggle_bookmark(conn, page_url: str) -> bool:
    """Flip a page's bookmark; return the new state (True = now bookmarked)."""
    if is_bookmarked(conn, page_url):
        remove_bookmark(conn, page_url)
        return False
    add_bookmark(conn, page_url)
    return True


# ── saved characters (charactermancer) ──────────────────────────────────────
# Lives in the writable user DB (survives app updates), like bookmarks. The full
# build is stored as a JSON blob (Character.to_dict); the loose columns are just
# for listing/searching.

def ensure_characters_schema(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS characters ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, race TEXT, "
        "char_class TEXT, alignment TEXT, data TEXT NOT NULL, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()


def insert_character(conn, name, race, char_class, alignment, data_json) -> int:
    cur = conn.execute(
        "INSERT INTO characters (name, race, char_class, alignment, data) "
        "VALUES (?,?,?,?,?)", (name, race, char_class, alignment, data_json))
    conn.commit()
    return cur.lastrowid


def update_character(conn, char_id, name, race, char_class, alignment, data_json):
    conn.execute(
        "UPDATE characters SET name=?, race=?, char_class=?, alignment=?, data=?, "
        "updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (name, race, char_class, alignment, data_json, char_id))
    conn.commit()


def all_characters(conn) -> list:
    """Saved-character rows (id, name, race, char_class, alignment), most-recent first."""
    return conn.execute(
        "SELECT id, name, race, char_class, alignment FROM characters "
        "ORDER BY updated_at DESC").fetchall()


def get_character(conn, char_id):
    """The stored JSON blob for one character, or None."""
    row = conn.execute("SELECT data FROM characters WHERE id=?", (char_id,)).fetchone()
    return row[0] if row else None


def delete_character(conn, char_id):
    conn.execute("DELETE FROM characters WHERE id=?", (char_id,))
    conn.commit()

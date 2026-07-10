"""Verify char_rules' transcribed tables against the rulebook itself.

char_rules.py is full of hand-copied numbers -- thief skills, turning undead, spell
progressions. The rest of the suite exercises the *functions* that read those tables
without pinning what the tables say, so a typo in a constant sails through green (a
mutation audit changed a thief base score and a racial adjustment; both survived the
whole suite).

The rulebook is right here in dnd2e.db, so these tests parse the source page and
compare it to the constant, cell by cell. When dnd2e.db is absent they skip.

The one trap: parse the page wrong and you compare zero cells and call it a pass.
Every test below asserts *how many rows it pulled from the book* before comparing, so
"agrees with the book" can never secretly mean "found nothing".
"""
import os
import re
import html

import pytest

import char_rules as cr
import rules_agent

RULES_DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")


@pytest.fixture
def conn():
    import sqlite3
    c = sqlite3.connect(RULES_DB)
    yield c
    c.close()


def _table_rows(conn, url):
    """Every <tr> on a page as a list of cleaned cell strings (empty rows dropped)."""
    row = conn.execute("SELECT content_html FROM pages WHERE page_url=?", (url,)).fetchone()
    assert row is not None, f"page {url} not in the DB"
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", row[0], re.S | re.I):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if cells:
            out.append(cells)
    return out


def _pct(s):
    """A percentage cell -> int. '--', '-' and '' are zero; '%' and '+' are noise."""
    s = s.strip().replace("%", "").replace("+", "")
    return 0 if s in ("--", "-", "") else int(s)


def _slots(s):
    """A spell-slot cell -> int, with '--' meaning no slots (the constant stores 0)."""
    s = s.strip()
    return 0 if s in ("--", "-", "") else int(s)


def _turn(s):
    """A turning cell -> the constant's form: int, 'T', 'D', 'D*', or None for '--'."""
    s = s.strip()
    if s in ("--", "-", ""):
        return None
    if s in ("T", "D", "D*"):
        return s
    return int(s)


def _strip_marker(name):
    """Drop the book's trailing footnote marks ('Special**', 'Priest†') for matching."""
    return name.rstrip("*").rstrip("†").strip()


# ── Table 26: thief base scores ──────────────────────────────────────────────

@needs_db
def test_table_26_thief_base_scores_match_the_book(conn):
    rows = [r for r in _table_rows(conn, "PHB/DD01501.htm")
            if r and r[0] in cr.THIEF_SKILLS]
    assert len(rows) == len(cr.THIEF_SKILLS) == 8      # parsed every skill, not zero
    for skill, base in ((r[0], _pct(r[1])) for r in rows):
        assert base == cr._THIEF_BASE[skill], skill


# ── Table 27: thief racial adjustments ───────────────────────────────────────

@needs_db
def test_table_27_thief_racial_adjustments_match_the_book(conn):
    races = ["Dwarf", "Elf", "Gnome", "Half-Elf", "Halfling"]   # column order on the page
    rows = [r for r in _table_rows(conn, "PHB/DD01502.htm")
            if r and r[0] in cr.THIEF_SKILLS]
    assert len(rows) == 8
    compared = 0
    for r in rows:
        skill = r[0]
        for i, race in enumerate(races):
            book = _pct(r[1 + i])
            ours = cr._THIEF_RACIAL.get(race, {}).get(skill, 0)
            assert book == ours, f"{race} {skill}: book {book}, char_rules {ours}"
            compared += 1
    assert compared == 8 * 5 == 40


# ── Table 28: thief Dexterity adjustments ────────────────────────────────────

@needs_db
def test_table_28_thief_dexterity_adjustments_match_the_book(conn):
    # Five affected skills, in the page's column order (== cr._THIEF_DEX_SKILLS).
    rows = [r for r in _table_rows(conn, "PHB/DD01503.htm")
            if r and re.fullmatch(r"\d+(-\d+)?", r[0])]
    seen = set()
    for r in rows:
        lo, _, hi = r[0].partition("-")
        for dex in range(int(lo), int(hi or lo) + 1):     # '13-15' -> 13, 14, 15
            book = tuple(_pct(c) for c in r[1:6])
            assert book == cr._THIEF_DEX[dex], f"Dex {dex}: book {book}, ours {cr._THIEF_DEX[dex]}"
            seen.add(dex)
    assert seen == set(range(9, 20))                       # 9..19, the table's whole range


# ── Table 29: thief armor adjustments ────────────────────────────────────────

@needs_db
def test_table_29_thief_armor_adjustments_match_the_book(conn):
    # The page's four columns are none / elven_chain / padded_studded / chain_ring --
    # leather is the baseline the base scores already assume, so it isn't on the page.
    rows = [r for r in _table_rows(conn, "PHB/DD01504.htm")
            if r and r[0] in cr.THIEF_SKILLS]
    assert len(rows) == 8
    for r in rows:
        book = tuple(_pct(c) for c in r[1:5])
        assert book == cr._THIEF_ARMOR[r[0]], f"{r[0]}: book {book}, ours {cr._THIEF_ARMOR[r[0]]}"


# ── Table 61: turning undead ─────────────────────────────────────────────────

@needs_db
def test_table_61_turning_undead_matches_the_book(conn):
    by_type = {_strip_marker(r[0]): r for r in _table_rows(conn, "PHB/DD01734.htm")}
    compared = 0
    for kind in cr.TURN_UNDEAD_TYPES:
        assert kind in by_type, f"{kind} row missing from the parsed page"
        book = tuple(_turn(c) for c in by_type[kind][1:13])    # 12 priest-level columns
        assert book == cr._TURN_UNDEAD[kind], f"{kind}: book {book}, ours {cr._TURN_UNDEAD[kind]}"
        compared += 1
    assert compared == len(cr.TURN_UNDEAD_TYPES) == 13


# ── Tables 21 / 24: spell progressions ───────────────────────────────────────

def _progression_rows(conn, url, width):
    """Level-keyed rows of a spell-progression page: {level: (slots per spell level)}."""
    out = {}
    for r in _table_rows(conn, url):
        if r and re.fullmatch(r"\d+", r[0]) and len(r) >= width + 1:
            out[int(r[0])] = tuple(_slots(c) for c in r[1:width + 1])
    return out


@needs_db
def test_table_21_wizard_spell_slots_match_the_book(conn):
    book = _progression_rows(conn, "PHB/DD02354.htm", 9)
    assert set(book) == set(range(1, 21))              # levels 1..20, all present
    for level, slots in book.items():
        assert slots == cr._WIZARD_SPELL_SLOTS[level], level


@needs_db
def test_table_24_priest_spell_slots_match_the_book(conn):
    book = _progression_rows(conn, "PHB/DD01479.htm", 7)
    assert set(book) == set(range(1, 21))
    for level, slots in book.items():
        assert slots == cr._PRIEST_SPELL_SLOTS[level], level

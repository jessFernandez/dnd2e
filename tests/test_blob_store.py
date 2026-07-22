"""Tests for db.BlobStore, db.row_id, and Monster.from_dict's coercion.

The two saved-thing tables (characters, saved_monsters) were the same store written
twice — two CREATE TABLEs, two inserts, two of everything, differing only in the
table name and loose columns. One BlobStore describes both now
(docs/audit-2-plan.md finding 4).

The schema tests matter more than they look: `CREATE TABLE IF NOT EXISTS` will not
migrate an existing user's DB, so the generated SQL has to match what shipped before
byte for byte or an old DB and a new one quietly diverge.
"""
import json
import sqlite3

import pytest

import db
import monster
from monster import Monster

# The exact DDL that shipped before the store was parameterized.
ORIGINAL_SCHEMA = {
    "characters":
        "CREATE TABLE characters ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, race TEXT, "
        "char_class TEXT, alignment TEXT, data TEXT NOT NULL, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
    "saved_monsters":
        "CREATE TABLE saved_monsters ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
        "source_page TEXT, data TEXT NOT NULL, "
        "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
}


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "user.db")
    yield c
    c.close()


# ── the generated schema must not drift from what shipped ────────────────────

@pytest.mark.parametrize("store", [db.CHARACTERS, db.MONSTERS])
def test_generated_schema_matches_what_shipped(conn, store):
    store.ensure(conn)
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?",
                       (store.table,)).fetchone()[0]
    assert sql.replace("IF NOT EXISTS ", "") == ORIGINAL_SCHEMA[store.table]


def test_ensure_is_idempotent(conn):
    db.CHARACTERS.ensure(conn)
    db.CHARACTERS.insert(conn, ("Gornak", "Half-Orc", "Fighter", "CN"), '{"v":1}')
    db.CHARACTERS.ensure(conn)                       # must not wipe anything
    assert len(db.CHARACTERS.all_rows(conn)) == 1


# ── the store itself ─────────────────────────────────────────────────────────

def test_insert_returns_the_new_id_and_stores_the_blob(conn):
    db.MONSTERS.ensure(conn)
    mid = db.MONSTERS.insert(conn, ("Ankheg", "MM/DD03797.htm"), '{"name":"Ankheg"}')
    assert isinstance(mid, int) and mid > 0
    assert db.MONSTERS.blob(conn, mid) == '{"name":"Ankheg"}'


def test_all_rows_returns_id_then_the_loose_columns(conn):
    db.MONSTERS.ensure(conn)
    mid = db.MONSTERS.insert(conn, ("Ogre", "MM/x.htm"), "{}")
    assert db.MONSTERS.all_rows(conn) == [(mid, "Ogre", "MM/x.htm")]

    db.CHARACTERS.ensure(conn)
    cid = db.CHARACTERS.insert(conn, ("Gornak", "Half-Orc", "Fighter", "CN"), "{}")
    assert db.CHARACTERS.all_rows(conn) == [(cid, "Gornak", "Half-Orc", "Fighter", "CN")]


def test_update_replaces_columns_and_blob(conn):
    db.MONSTERS.ensure(conn)
    mid = db.MONSTERS.insert(conn, ("Ogre", "MM/x.htm"), '{"v":1}')
    db.MONSTERS.update(conn, mid, ("Ogre Mage", "MM/y.htm"), '{"v":2}')
    assert db.MONSTERS.all_rows(conn) == [(mid, "Ogre Mage", "MM/y.htm")]
    assert db.MONSTERS.blob(conn, mid) == '{"v":2}'


def test_blob_and_delete_for_a_missing_row(conn):
    db.MONSTERS.ensure(conn)
    assert db.MONSTERS.blob(conn, 999) is None
    db.MONSTERS.delete(conn, 999)                    # deleting nothing is not an error


def test_the_two_stores_do_not_share_rows(conn):
    """Different tables — a saved character must not appear among saved monsters."""
    db.CHARACTERS.ensure(conn)
    db.MONSTERS.ensure(conn)
    db.CHARACTERS.insert(conn, ("Gornak", "Half-Orc", "Fighter", "CN"), "{}")
    assert db.MONSTERS.all_rows(conn) == []


# ── row_id ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (7, 7), ("7", 7), ("  7 ", 7), (-1, -1),
    ("x", None), ("", None), (None, None), ([], None), ("7.5", None),
])
def test_row_id_coerces_or_rejects(value, expected):
    assert db.row_id(value) == expected


# ── Monster.from_dict is the typing boundary (finding 1c) ────────────────────

def test_from_dict_coerces_nulls_to_empty_strings():
    m = Monster.from_dict({"name": None, "hit_dice": None})
    assert m.name == "" and m.hit_dice == ""


def test_from_dict_coerces_numbers_in_string_fields():
    """A bare number used to reach re.sub in the house-rule conversions and raise
    TypeError: expected string or bytes-like object."""
    m = Monster.from_dict({"armor_class": 5, "thac0": 17})
    assert m.armor_class == "5" and m.thac0 == "17"
    assert m.ascending_ac() == "15"          # the conversion now runs


def test_from_dict_leaves_the_nullable_int_fields_alone():
    """initiative_override and selected_tier are genuinely `int | None` — coercing
    them to "" would break the "derive from size" / "base stat block" defaults."""
    m = Monster.from_dict({"initiative_override": None, "selected_tier": None})
    assert m.initiative_override is None and m.selected_tier is None
    m2 = Monster.from_dict({"initiative_override": 5, "selected_tier": 2})
    assert m2.initiative_override == 5 and m2.selected_tier == 2


def test_from_dict_drops_unknown_keys():
    """An older app version opening a save written by a newer one."""
    m = Monster.from_dict({"name": "Ogre", "a_field_from_the_future": 1})
    assert m.name == "Ogre"
    assert not hasattr(m, "a_field_from_the_future")


def test_from_dict_preserves_list_fields():
    m = Monster.from_dict({"related_creatures": [{"name": "Kapoacinth", "text": "…"}]})
    assert m.related_creatures == [{"name": "Kapoacinth", "text": "…"}]


def test_a_degenerate_blob_survives_the_whole_round_trip(tmp_path):
    """The finding-1c path end to end: a blob with nulls and numbers in string
    fields saves, loads, and renders."""
    import monster_html
    from monster_library import MonsterLibrary

    lib = MonsterLibrary(sqlite3.connect(tmp_path / "user.db"))
    db.ensure_monsters_schema(lib.user_db)
    raw = json.dumps({"name": None, "armor_class": 5, "hit_dice": None})
    mid = db.insert_monster(lib.user_db, "Broken", "MM/x.htm", raw)

    m = lib.load(mid)
    assert isinstance(m, monster.Monster)
    assert monster_html.generate(m)


def test_library_load_and_delete_reject_a_malformed_id(tmp_path):
    from monster_library import MonsterLibrary
    lib = MonsterLibrary(sqlite3.connect(tmp_path / "user.db"))
    assert lib.load("not-an-id") is None
    assert lib.delete("not-an-id") is None

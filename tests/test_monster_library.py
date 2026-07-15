"""Tests for monster_library.py — save/load/delete for DM monster sheets.

Runs against a throwaway temp user DB, so the persistence logic is exercised
without a running app (same approach as test_character_library.py).
"""
import db
from monster import Monster
from monster_library import MonsterLibrary


def _goblin() -> Monster:
    return Monster(name="Goblin", source_page="MM/DD03940.htm",
                   armor_class="6", thac0="20", size="S", hit_dice="1-1",
                   special_attacks="Nil", combat="Goblins attack in swarms.")


def _lib(tmp_path) -> MonsterLibrary:
    return MonsterLibrary(db.connect(tmp_path / "user.db"))


def test_save_inserts_then_updates_in_place(tmp_path):
    lib = _lib(tmp_path)
    m = _goblin()

    mid = lib.save(m)
    assert isinstance(mid, int)
    assert len(lib.all()) == 1

    # Editing and saving with the id updates the same row rather than inserting.
    m.name = "Hobgoblin"
    same_id = lib.save(m, saved_id=mid)
    assert same_id == mid
    rows = lib.all()
    assert len(rows) == 1 and rows[0]["name"] == "Hobgoblin"


def test_save_defaults_blank_name(tmp_path):
    lib = _lib(tmp_path)
    m = _goblin()
    m.name = ""
    lib.save(m)
    assert lib.all()[0]["name"] == "Unnamed Monster"


def test_load_roundtrips_fields_and_derived_values(tmp_path):
    lib = _lib(tmp_path)
    m = _goblin()
    got = lib.load(lib.save(m))
    assert got == m                              # every stored field survives
    assert got.ascending_ac() == "14"            # AC 6 -> 20-6, derived still works
    assert got.initiative_modifier() == 3        # size S


def test_load_missing_or_malformed_id_returns_none(tmp_path):
    lib = _lib(tmp_path)
    assert lib.load(999) is None
    assert lib.load("not-an-id") is None
    assert lib.load(None) is None


def test_delete_removes_and_reports_the_id(tmp_path):
    lib = _lib(tmp_path)
    mid = lib.save(_goblin())
    assert lib.delete(mid) == mid
    assert lib.all() == []
    assert lib.delete("bad") is None             # malformed id is a no-op


def test_all_lists_name_and_source_page(tmp_path):
    lib = _lib(tmp_path)
    lib.save(_goblin())
    (row,) = lib.all()
    assert row["name"] == "Goblin" and row["source_page"] == "MM/DD03940.htm"


def test_saved_monster_survives_a_reopen(tmp_path):
    path = tmp_path / "user.db"
    MonsterLibrary(db.connect(path)).save(_goblin())
    rows = MonsterLibrary(db.connect(path)).all()   # fresh connection to the same file
    assert len(rows) == 1 and rows[0]["name"] == "Goblin"

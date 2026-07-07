"""Tests for character_library.py — save/load/delete and Roll20 export for builds.

Runs against a throwaway temp user DB, so it exercises the persistence logic that
used to be buried inside MainWindow (and was therefore untestable).
"""
import db
from character import Character
from charactermancer import Charactermancer, STEPS
from character_library import CharacterLibrary


def _cleric_build() -> Charactermancer:
    c = Character()
    for a in c.ability_names():
        c.assign_ability(a, 14)
    c.race, c.char_class, c.alignment, c.name = "Human", "Cleric", "Lawful Good", "Bryn"
    return Charactermancer(character=c)


def _lib(tmp_path) -> CharacterLibrary:
    return CharacterLibrary(db.connect(tmp_path / "user.db"))


def test_save_inserts_then_updates_in_place(tmp_path):
    lib = _lib(tmp_path)
    cm = _cleric_build()

    new_id = lib.save(cm)
    cm.saved_id = new_id
    assert isinstance(new_id, int)
    assert len(lib.all()) == 1

    # Editing and saving again updates the same row rather than inserting.
    cm.character.name = "Brynn"
    same_id = lib.save(cm)
    assert same_id == new_id
    rows = lib.all()
    assert len(rows) == 1 and rows[0]["name"] == "Brynn"


def test_save_defaults_blank_name(tmp_path):
    lib = _lib(tmp_path)
    cm = _cleric_build()
    cm.character.name = ""
    lib.save(cm)
    assert lib.all()[0]["name"] == "Unnamed"


def test_load_round_trips_and_opens_on_final_step(tmp_path):
    lib = _lib(tmp_path)
    cm = _cleric_build()
    cid = lib.save(cm)

    loaded = lib.load(cid)
    assert loaded is not None
    assert loaded.saved_id == cid
    assert loaded.index == len(STEPS) - 1          # opens on the finished sheet
    assert loaded.character.name == "Bryn"
    assert loaded.character.char_class == "Cleric"


def test_load_accepts_string_id(tmp_path):
    lib = _lib(tmp_path)
    cid = lib.save(_cleric_build())
    assert lib.load(str(cid)) is not None           # ids arrive from URLs as strings


def test_load_bad_or_missing_id_returns_none(tmp_path):
    lib = _lib(tmp_path)
    assert lib.load("not-a-number") is None
    assert lib.load(999) is None


def test_delete_removes_row_and_reports_id(tmp_path):
    lib = _lib(tmp_path)
    cid = lib.save(_cleric_build())
    assert lib.delete(cid) == cid
    assert lib.all() == []


def test_delete_bad_id_returns_none(tmp_path):
    lib = _lib(tmp_path)
    assert lib.delete("nope") is None


def test_roll20_payload_uses_character(tmp_path):
    lib = _lib(tmp_path)
    cm = _cleric_build()
    cm.character.name = "Bryn"
    data = lib.roll20_payload(cm, all_spells=[])
    assert data["character_name"] == "Bryn"
    assert data["player_class"] == "Cleric"

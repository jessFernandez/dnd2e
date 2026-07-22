"""monster_library.py — persistence for DM monster sheets.

The monster counterpart to character_library.py: save/load/delete monsters in the
writable *user* DB (see db.py), so a DM's saved monsters survive app updates like
bookmarks and characters do. A monster is stored as a JSON blob (Monster.to_dict);
the loose name/source_page columns are just for listing.

Pure and Qt-free — the UI (app.py) keeps the Qt concerns and delegates here. The
row id is tracked by the caller (not stored in the Monster), the same separation
character_library keeps between a build and its ``saved_id``.
"""
import json

import db
from monster import Monster


class MonsterLibrary:
    """CRUD for saved monster sheets. Holds the user-DB connection; every method is
    Qt-free and returns plain data, so it can be tested against a temp DB."""

    def __init__(self, user_db):
        self.user_db = user_db

    def all(self) -> list:
        """Saved-monster rows (most-recent first), ensuring the schema exists."""
        db.ensure_monsters_schema(self.user_db)
        return db.all_monsters(self.user_db)

    def save(self, m: Monster, saved_id=None) -> int:
        """Insert the monster, or update the row ``saved_id`` when given; return the
        row id. The caller holds ``saved_id`` (the Monster model stays persistence-
        free) and writes back the returned value."""
        db.ensure_monsters_schema(self.user_db)
        data = json.dumps(m.to_dict())
        name = m.name or "Unnamed Monster"
        if saved_id:
            db.update_monster(self.user_db, saved_id, name, m.source_page, data)
            return saved_id
        return db.insert_monster(self.user_db, name, m.source_page, data)

    def load(self, mid) -> Monster | None:
        """The saved monster, or None if the id is malformed or missing."""
        mid = db.row_id(mid)
        if mid is None:
            return None
        db.ensure_monsters_schema(self.user_db)
        raw = db.get_monster(self.user_db, mid)
        return Monster.from_dict(json.loads(raw)) if raw else None

    def delete(self, mid) -> int | None:
        """Delete a saved monster; return the deleted id, or None if the id is
        malformed."""
        mid = db.row_id(mid)
        if mid is None:
            return None
        db.ensure_monsters_schema(self.user_db)
        db.delete_monster(self.user_db, mid)
        return mid

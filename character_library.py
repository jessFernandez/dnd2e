"""character_library.py — persistence + export for saved character builds.

Extracted from app.py's MainWindow so the save/load/delete and Roll20-payload
logic lives in one Qt-free, unit-testable place. The UI layer keeps only the
Qt concerns (clipboard, status messages, re-render) and delegates the rest here.

Saved characters live in the writable *user* DB (see db.py), so they survive app
updates like bookmarks do. A build is stored as a JSON blob (Character.to_dict);
the loose columns are just for listing.
"""
import json

import db
from character import Character
from charactermancer import Charactermancer, STEPS


class CharacterLibrary:
    """CRUD for saved character builds, plus the Roll20 export payload.

    Holds the user-DB connection; every method is Qt-free and returns plain data
    so it can be tested against a temp DB without a running app.
    """

    def __init__(self, user_db):
        self.user_db = user_db

    def all(self) -> list:
        """Saved-character rows (most-recent first), ensuring the schema exists."""
        db.ensure_characters_schema(self.user_db)
        return db.all_characters(self.user_db)

    def save(self, cm: Charactermancer) -> int:
        """Insert or update the build the charactermancer holds; return its row id.

        Updates in place when the build already has a ``saved_id``, otherwise
        inserts a new row. The returned id should be written back onto ``cm``.
        """
        c = cm.character
        db.ensure_characters_schema(self.user_db)
        data = json.dumps(c.to_dict())
        name = c.name or "Unnamed"
        if cm.saved_id:
            db.update_character(self.user_db, cm.saved_id,
                                name, c.race, c.char_class, c.alignment, data)
            return cm.saved_id
        return db.insert_character(
            self.user_db, name, c.race, c.char_class, c.alignment, data)

    def load(self, cid) -> Charactermancer | None:
        """Return a Charactermancer for the saved character, or None if the id is
        malformed or missing. A loaded build opens on its finished sheet."""
        try:
            cid = int(cid)
        except (ValueError, TypeError):
            return None
        db.ensure_characters_schema(self.user_db)
        raw = db.get_character(self.user_db, cid)
        if not raw:
            return None
        cm = Charactermancer(character=Character.from_dict(json.loads(raw)))
        cm.saved_id = cid
        cm.index = len(STEPS) - 1        # a saved build opens on its finished sheet
        return cm

    def delete(self, cid) -> int | None:
        """Delete a saved character; return the deleted id, or None if the id is
        malformed. Callers use the returned id to clear a matching in-progress build."""
        try:
            cid = int(cid)
        except (ValueError, TypeError):
            return None
        db.ensure_characters_schema(self.user_db)
        db.delete_character(self.user_db, cid)
        return cid

    def roll20_payload(self, cm: Charactermancer, all_spells: list) -> dict:
        """Build the Roll20 import JSON for the build, enriching spells from the
        rulebook spell list. ``all_spells`` is the app's cached ``db.all_spells``."""
        import roll20_export
        details = {s["name"]: {"level": s.get("level"), "school": s.get("school"),
                               "range": s.get("range"), "casting_time": s.get("casting_time"),
                               "duration": s.get("duration"), "aoe": s.get("aoe"),
                               "save": s.get("save"), "damage": s.get("damage"),
                               "materials": s.get("materials"), "components": s.get("components"),
                               "description": s.get("description")}
                   for s in all_spells}
        return roll20_export.character_to_roll20(cm.character, details)

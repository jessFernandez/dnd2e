"""build_spells.py — import the 2e spell compendium into the app database.

Parses the spell cards from regalgoblins.com/spells.php (the same site the
rulebooks came from) into a structured `spells` table that the Spells screen
renders. Each card carries caster (wizard/priest), level, school, components,
the stat block (range / casting time / save / area / duration / damage /
materials), the description, residue, and source.

Run:  python scripts/build_spells.py               # fetch live and rebuild the table
      python scripts/build_spells.py --file x.html # parse a saved copy instead
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

URL = "https://regalgoblins.com/spells.php"
DB = Path(__file__).resolve().parent.parent / "dnd2e.db"   # repo root (script lives in scripts/)
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Referer": "https://regalgoblins.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIELD_MAP = {  # <dt> label -> column
    "Range": "range", "Casting Time": "casting_time", "Save": "save",
    "AoE": "aoe", "Duration": "duration", "Damage": "damage",
    "Materials": "materials", "Residue": "residue", "Source": "source",
}


def fetch(path=None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    import requests
    r = requests.get(URL, headers=HEADERS, timeout=45)
    r.raise_for_status()
    return r.text


def _clean(s: str) -> str:
    return re.sub(r"\s+\Z", "", re.sub(r"\A\s+", "", (s or "").replace("\xa0", " "))).strip()


# Priest spheres and wizard specialists are server-side filters (spells.php?sphere=…
# / ?specialization=…), not per-card data — so we fetch each and record which
# spells (by data-id) it returns. Specialization = spells the specialist can learn
# (i.e. every school except their opposition schools).
SPHERES = ["Animal", "Astral", "Chaos", "Charm", "Combat", "Creation", "Divination",
           "Elemental Air", "Elemental Earth", "Elemental Fire", "Elemental Water",
           "Guardian", "Healing", "Law", "Necromantic", "Numbers", "Plant",
           "Protection", "Summoning", "Sun", "Thought", "Time", "Travelers", "War",
           "Wards", "Weather"]
SPEC_LABELS = {"abjurer": "Abjurer", "conjurer": "Conjurer", "diviner": "Diviner",
               "enchanter": "Enchanter", "illusionist": "Illusionist", "invocation": "Invoker",
               "necromancer": "Necromancer", "transmuter": "Transmuter",
               "dimensionalist": "Dimensionalist"}


def _fetch_ids(params: dict) -> set:
    """Return the set of spell data-ids returned by a spells.php filter query."""
    import requests
    r = requests.get("https://regalgoblins.com/spells.php", params=params,
                     headers=HEADERS, timeout=45)
    r.raise_for_status()
    return set(re.findall(r'<div data-id="(\d+)" class="card ', r.text))


def fetch_group_maps():
    """Build {src_id -> [spheres]} and {src_id -> [specializations]} from the site."""
    import time
    spheres, specs = {}, {}
    for i, sph in enumerate(SPHERES, 1):
        for sid in _fetch_ids({"sphere": sph}):
            spheres.setdefault(sid, []).append(sph)
        print(f"  sphere {i}/{len(SPHERES)}: {sph}")
        time.sleep(0.6)
    for i, (param, label) in enumerate(SPEC_LABELS.items(), 1):
        for sid in _fetch_ids({"specialization": param, "caster": "Wizard"}):
            specs.setdefault(sid, []).append(label)
        print(f"  specialization {i}/{len(SPEC_LABELS)}: {label}")
        time.sleep(0.6)
    return spheres, specs


def parse(html: str):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    spells = []
    for card in soup.select("div.card"):
        caster = card.get("data-caster") or ""
        if caster not in ("wizard", "priest"):
            continue
        lvl_el = card.select_one("button.level")
        level = int(re.sub(r"\D", "", lvl_el.get_text()) or 0) if lvl_el else 0
        name = _clean(card.select_one(".name").get_text()) if card.select_one(".name") else ""
        if not name:
            continue

        comp_div = card.find("div", class_="components")
        classes = comp_div.get("class", []) if comp_div else []
        components = ", ".join(
            letter for key, letter in (("verbal", "V"), ("somatic", "S"), ("material", "M"))
            if key in classes
        )

        row = {"caster": caster, "level": level, "school": card.get("data-school") or "",
               "name": name, "components": components, "src_id": card.get("data-id") or ""}
        for dt in card.select("dt"):
            col = FIELD_MAP.get(_clean(dt.get_text()))
            dd = dt.find_next_sibling("dd")
            if col and dd:
                row[col] = _clean(dd.get_text(" "))

        desc_el = card.select_one(".description-content")
        if desc_el:
            for br in desc_el.select("br"):
                br.replace_with("\n")
            row["description"] = re.sub(r"\n{3,}", "\n\n", _clean(desc_el.get_text())).strip()
        spells.append(row)
    return spells


COLUMNS = ["caster", "level", "school", "name", "components", "range", "casting_time",
           "duration", "aoe", "save", "damage", "materials", "description", "residue",
           "source", "spheres", "specializations"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="parse a saved HTML file instead of fetching")
    args = ap.parse_args()

    html = fetch(args.file)
    spells = parse(html)
    if len(spells) < 500:
        print(f"only parsed {len(spells)} spells — aborting (expected ~875)"); sys.exit(1)

    print("fetching sphere / specialization groupings…")
    sphere_map, spec_map = fetch_group_maps()
    for s in spells:
        sid = s.get("src_id", "")
        s["spheres"] = ", ".join(sphere_map.get(sid, []))
        s["specializations"] = ", ".join(spec_map.get(sid, []))

    conn = sqlite3.connect(str(DB))
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS spells")
    c.execute(f"""CREATE TABLE spells (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {', '.join(f'{col} TEXT' for col in COLUMNS if col != 'level')},
        level INTEGER)""")
    c.executemany(
        f"INSERT INTO spells ({', '.join(COLUMNS)}) VALUES ({', '.join('?' * len(COLUMNS))})",
        [tuple(s.get(col, "") for col in COLUMNS) for s in spells],
    )
    conn.commit()
    n_wiz = c.execute("SELECT COUNT(*) FROM spells WHERE caster='wizard'").fetchone()[0]
    n_pri = c.execute("SELECT COUNT(*) FROM spells WHERE caster='priest'").fetchone()[0]
    n_sph = c.execute("SELECT COUNT(*) FROM spells WHERE spheres != ''").fetchone()[0]
    n_spec = c.execute("SELECT COUNT(*) FROM spells WHERE specializations != ''").fetchone()[0]
    conn.close()
    print(f"imported {len(spells)} spells  ({n_wiz} wizard, {n_pri} priest); "
          f"{n_sph} with spheres, {n_spec} with specializations")


if __name__ == "__main__":
    main()

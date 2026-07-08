"""build_nwp_book.py — generate nonweapon_book.py from the campaign source files.

The campaign's expanded nonweapon-proficiency list lives in two hand-maintained
source files exported from Google Drive:

  * nonweapon_proficiencies.csv — the mechanical table (cost, ability, prereq,
    check modifier, and which of the four class groups may take each skill), and
  * nonweapon_proficiencies.txt — the full prose rules text for each skill.

This script joins them by proficiency name and writes `nonweapon_book.py`, the
data module char_rules.py loads. Re-run it whenever either source file changes:

    python scripts/build_nwp_book.py

Like build_spells.py / build_economics.py, it is a one-shot generator, not part
of the running app.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # repo root (this script lives in scripts/)
CSV_PATH = ROOT / "nonweapon_proficiencies.csv"
DOC_PATH = ROOT / "nonweapon_proficiencies.txt"
OUT_PATH = ROOT / "nonweapon_book.py"

# The in-world sourcebook these proficiencies are published in. Rename here to
# re-brand the book everywhere (it is stored as each proficiency's `source`).
BOOK_NAME = "The Codex of Worldly Craft"
BOOK_CODE = "CWC"

# CSV class-availability columns, in sheet order, mapped to char_rules group names.
CLASS_COLUMNS = ("Warrior", "Rogue", "Wizard", "Priest")

# The sheet's Engineering row lists its prerequisite as "Mathmatics" (a typo for
# the "Mathematics" proficiency it actually names). Fix the reference so prereq
# gating can resolve it.
PREREQ_FIXUPS = {"Mathmatics": "Mathematics"}

# A few sheet skills have no dedicated section in the prose doc (the doc instead
# folds them into related entries). Author short, faithful descriptions for them.
DESCRIPTION_OVERRIDES = {
    "Languages, Modern":
        "The character can speak one additional living language of his choice, "
        "declared when the slot is filled. (Reading and writing that language "
        "additionally requires the Literacy proficiency.)",
    "Literacy":
        "The character can read and write any modern language he is able to "
        "speak, provided someone is available to teach him the script.",
    "Story Telling":
        "The character is a practiced teller of tales, able to entertain an "
        "audience with myths, legends, and yarns. On a successful proficiency "
        "check he adds a story to his repertoire or holds a crowd; a well-told "
        "tale can grant a temporary Charisma bonus with a receptive audience.",
}

# Short non-check effect labels for the skills that have no ability check (their
# ability/modifier are "NA" on the sheet). Kept empty: these skills simply show
# "no check" in the compact picker; their full effect is in the description.
SPECIAL_LABELS: dict = {}

# Prose headers that are NOT sheet proficiencies but must still be recognised so
# their text does not bleed into the preceding skill's description.
DOC_ONLY_HEADERS = ("Teaching", "Reading / Writing")


def norm_variants(name: str) -> set:
    """Normalised match keys for a proficiency name, tolerant of the spacing /
    hyphenation / punctuation differences between the sheet and the prose doc
    (e.g. 'Fire-building' vs 'Fire Building', 'Glassblowing' vs 'Glass Blowing')."""
    s = name.strip().lower()
    s = s.replace("&", "and")
    s = re.sub(r"\s*/\s*", "/", s)      # unify "a / b" and "a/b"
    s = s.replace("-", " ")
    s = re.sub(r"[.,]", "", s)           # drop commas / periods
    s = re.sub(r"\s+", " ", s).strip()
    return {s, s.replace(" ", "")}       # also a spaces-removed variant


def parse_csv():
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            name = (r["Proficiency"] or "").strip()
            if not name:
                continue
            ability_raw = (r["Ability"] or "").strip()
            mod_raw = (r["Modifier"] or "").strip()
            no_check = ability_raw.upper() == "NA" or mod_raw.upper() == "NA"
            ability = "" if no_check else ability_raw
            modifier = 0 if no_check else int(mod_raw)

            prereq = []
            for part in re.split(r"[,;]", (r["Pre. Req"] or "")):
                part = part.strip()
                if part:
                    prereq.append(PREREQ_FIXUPS.get(part, part))

            classes = tuple(col for col in CLASS_COLUMNS
                            if (r.get(col) or "").strip().lower() == "x")

            rows.append({
                "name": name,
                "slots": int((r["Cost"] or "0").strip() or 0),
                "ability": ability,
                "modifier": modifier,
                "classes": classes,
                "prereq": tuple(prereq),
                "special": SPECIAL_LABELS.get(name, ""),
            })
    return rows


def parse_doc(names):
    """Return {normalised-name: description}. Segments the prose doc into
    (header -> body) sections, recognising a line as a header when it matches a
    known proficiency name (sheet names plus DOC_ONLY_HEADERS)."""
    header_keys = set()
    for n in list(names) + list(DOC_ONLY_HEADERS):
        header_keys |= norm_variants(n)

    lines = DOC_PATH.read_text(encoding="utf-8-sig").splitlines()

    def is_header(line: str) -> bool:
        s = line.strip()
        if not s or len(s) > 40 or s[0] in "*•-–":
            return False
        return bool(norm_variants(s) & header_keys)

    sections = {}          # normalised header -> list[str] body lines
    current = None
    for line in lines:
        if is_header(line):
            current = norm_variants(line.strip())
            for key in current:
                sections.setdefault(key, [])
            current = next(iter(current))          # index bodies by one variant
            sections[current] = []
            sections["__head__" + current] = line.strip()
        elif current is not None:
            sections[current].append(line)

    # Build description lookup keyed by every variant of each detected header.
    out = {}
    for key, body in sections.items():
        if key.startswith("__head__"):
            continue
        head = sections.get("__head__" + key, "")
        text = "\n".join(body).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)      # collapse big gaps
        for v in norm_variants(head):
            out[v] = text
    return out


def describe(name, doc_index):
    if name in DESCRIPTION_OVERRIDES:
        return DESCRIPTION_OVERRIDES[name]
    for v in norm_variants(name):
        if doc_index.get(v):
            return doc_index[v]
    return ""


def emit(rows):
    lines = [
        '"""nonweapon_book.py — AUTO-GENERATED by build_nwp_book.py. Do not edit by hand.',
        "",
        f"The campaign's nonweapon-proficiency sourcebook, {BOOK_NAME!r}: the mechanical",
        "table joined to its prose rules text. char_rules.py loads ENTRIES into its",
        "Proficiency model. Regenerate with `python scripts/build_nwp_book.py`.",
        '"""',
        "",
        f"BOOK_NAME = {BOOK_NAME!r}",
        f"BOOK_CODE = {BOOK_CODE!r}",
        "",
        "# name, slots, ability, modifier, classes, prereq, special, description",
        "ENTRIES = [",
    ]
    for r in rows:
        lines.append("    {")
        lines.append(f"        \"name\": {r['name']!r},")
        lines.append(f"        \"slots\": {r['slots']}, \"ability\": {r['ability']!r}, "
                     f"\"modifier\": {r['modifier']},")
        lines.append(f"        \"classes\": {r['classes']!r},")
        lines.append(f"        \"prereq\": {r['prereq']!r},")
        if r["special"]:
            lines.append(f"        \"special\": {r['special']!r},")
        # repr() preserves the prose verbatim — including its paragraph breaks and
        # bullet lines — with safe quoting (the reader renders those breaks).
        lines.append(f"        \"description\": {r['description']!r},")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    rows = parse_csv()
    names = [r["name"] for r in rows]
    doc_index = parse_doc(names)

    missing = []
    for r in rows:
        r["description"] = describe(r["name"], doc_index)
        if not r["description"]:
            missing.append(r["name"])

    emit(rows)

    print(f"Wrote {OUT_PATH.name}: {len(rows)} proficiencies.")
    have = sum(1 for r in rows if r["description"])
    print(f"  descriptions matched: {have}/{len(rows)}")
    if missing:
        print("  NO description for:", ", ".join(missing))
    # Sanity: every prereq names a real proficiency.
    known = {r["name"] for r in rows}
    dangling = sorted({p for r in rows for p in r["prereq"] if p not in known})
    if dangling:
        print("  WARNING dangling prereqs:", ", ".join(dangling))
    # Sanity: any prereq a class-restricted skill can never satisfy.
    from collections import defaultdict
    avail = defaultdict(set)
    for r in rows:
        avail[r["name"]] = set(r["classes"]) or set(CLASS_COLUMNS)
    for r in rows:
        for pre in r["prereq"]:
            if pre in avail and not (avail[r["name"]] & avail[pre]):
                print(f"  NOTE '{r['name']}' ({'/'.join(sorted(avail[r['name']]))}) "
                      f"requires '{pre}' ({'/'.join(sorted(avail[pre]))}) — unsatisfiable "
                      f"for that class; will show permanently locked.")


if __name__ == "__main__":
    main()

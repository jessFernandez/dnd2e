"""build_ct_text.py — generate ct_text.py from the scraped Combat & Tactics pages.

The builder's weapon step now offers CT's fighting styles, unarmed disciplines,
special talents and martial-arts talents. Each needs the same expandable "What it
does" block the nonweapon proficiencies already have, which means prose — and the
prose lives in dnd2e.db, not in char_rules.

Run from the repo root:  python scripts/build_ct_text.py

Writes ct_text.py: {name: {"page": page_url, "description": text}}.
"""
import html
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "dnd2e.db"
OUT = ROOT / "ct_text.py"

# One page per entry.
SINGLE_PAGE = {
    # Fighting styles (Ch4 specialisation pages)
    "Weapon and Shield":        "CT/DD02646.htm",
    "One-Handed Weapon":        "CT/DD02647.htm",
    "Two-Handed Weapon":        "CT/DD02648.htm",
    "Two-Weapon":               "CT/DD02649.htm",
    "Missile or Thrown Weapon": "CT/DD02650.htm",
    # Unarmed disciplines (Ch5 overviews)
    "Pummeling":   "CT/DD02672.htm",
    "Wrestling":   "CT/DD02679.htm",
    "Overbearing": "CT/DD02689.htm",
    # Special talents (Ch4)
    "Alertness":       "CT/DD02654.htm",
    "Ambidexterity":   "CT/DD02655.htm",
    "Ambush":          "CT/DD02656.htm",
    "Camouflage":      "CT/DD02657.htm",
    "Dirty Fighting":  "CT/DD02658.htm",
    "Endurance":       "CT/DD02659.htm",
    "Fine Balance":    "CT/DD02660.htm",
    "Iron Will":       "CT/DD02661.htm",
    "Leadership":      "CT/DD02662.htm",
    "Quickness":       "CT/DD02663.htm",
    "Steady Hand":     "CT/DD02664.htm",
    "Trouble Sense":   "CT/DD02665.htm",
    # Siege proficiencies (Ch8) — both described on one page; split below.
}

# The four martial-arts styles are bullets on the Procedures page.
MA_STYLES_PAGE = "CT/DD02701.htm"
MA_STYLES = {f"Martial Arts: Style {L}": L for L in "ABCD"}

# All six martial-arts talents share one page.
MA_TALENTS_PAGE = "CT/DD02705.htm"
MA_TALENTS = ("Flying Kick", "Backward Kick", "Spring", "Crushing Blow",
              "Instant Stand", "Missile Deflection")

# Both siege proficiencies share one page.
SIEGE_PAGE = "CT/DD02824.htm"
SIEGE = ("Artillerist", "Vehicle Handling")


def page_text(conn, url: str) -> str:
    row = conn.execute("SELECT content_html FROM pages WHERE page_url = ?", (url,)).fetchone()
    if not row:
        raise SystemExit(f"missing page {url}")
    text = re.sub(r"<[^>]+>", " ", row[0])
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# The stat header a talent page opens with, e.g.
#   "(1 slot/3 CP) Strength/Muscle Groups: Warrior Initial rating: 5"
#   "(2 slots/6 CP) Wisdom/Willpower, -2 Group: Warrior, Priest Initial rating: 3"
#   "(1 Slot) Charisma/Leadership Group: Warrior"
# Every part of that already lives in char_rules.SPECIAL_TALENTS, so drop it — but
# only the parts we can name exactly. A greedy match here silently eats the first
# sentence of the rules text.
_CLASS_GROUP = r"(?:Warriors?|Priests?|Rogues?|Wizards?|All|General)"
_COST = r"\(\s*\d+\s*slots?\s*(?:/[^)]*)?\)"                     # (1 slot/3 CP) | (1 Slot)

# The full stat header, anchored on "Group(s):" so it can never match plain prose.
# The ability clause is lazy and colon-free ("Wis./Int.", "Wisdom/Willpower, -2",
# "N/A"), which is why the anchor matters: without it, `[A-Za-z]+` happily ate the
# first word of the rules text ("This", "Some", "Normally,").
_HEADER_WITH_GROUPS = re.compile(
    rf"^\s*(?:{_COST}\s*)?[^:]{{0,40}}?Groups?:\s*"
    rf"{_CLASS_GROUP}(?:\s*,\s*{_CLASS_GROUP})*\s*"
    r"(?:Initial rating:\s*\d+\s*)?",
    re.IGNORECASE)
# Some entries carry only a cost (the siege proficiencies name their group later).
_HEADER_COST_ONLY = re.compile(rf"^\s*{_COST}\s*", re.IGNORECASE)


def strip_chrome(text: str, *headings) -> str:
    """Drop the scraped title line, the page heading and the stat header, plus the
    trailing 'Table of Contents' link. `headings` are tried longest-first, and
    case-insensitively — the book heads the pages "One-handed Weapon Style"."""
    text = re.sub(r"\s*Table of Contents\s*$", "", text)
    # "Ambush-- Special Talent (Combat and Tactics) Ambush (1 slot/4 CP) ..."
    text = re.sub(r"^[^(]*\(Combat and Tactics\)\s*", "", text)
    for heading in sorted(headings, key=len, reverse=True):
        stripped = re.sub(r"^" + re.escape(heading) + r"\*?\s*", "", text,
                          count=1, flags=re.IGNORECASE)
        if stripped != text:
            text = stripped
            break
    stripped = _HEADER_WITH_GROUPS.sub("", text, count=1)
    if stripped == text:
        stripped = _HEADER_COST_ONLY.sub("", text, count=1)
    return stripped.strip()


def split_on_headings(text: str, names) -> dict:
    """Carve one page into per-name sections, cutting at each name in turn."""
    positions = []
    for name in names:
        m = re.search(re.escape(name) + r"\s*\(?", text)
        if not m:
            raise SystemExit(f"could not find {name!r} on its page")
        positions.append((m.start(), name))
    positions.sort()
    out = {}
    for i, (start, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[name] = strip_chrome(text[start:end], name)
    return out


def split_ma_styles(text: str) -> dict:
    """The Procedures page lists 'Style A: ...' through 'Style D: ...'."""
    out = {}
    letters = list("ABCD")
    spans = []
    for letter in letters:
        m = re.search(r"Style " + letter + r":", text)
        if not m:
            raise SystemExit(f"could not find Style {letter}")
        spans.append((m.start(), letter))
    for i, (start, letter) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else len(text)
        body = re.sub(r"^Style " + letter + r":\s*", "", text[start:end]).strip()
        out[f"Martial Arts: Style {letter}"] = re.sub(r"\s*Table of Contents\s*$", "", body)
    return out


def main():
    if not DB.exists():
        raise SystemExit(f"{DB} not found — run from the repo root")
    conn = sqlite3.connect(DB)

    entries = {}
    for name, url in SINGLE_PAGE.items():
        # The fighting-style pages head themselves "Two-Weapon Style", etc.
        entries[name] = {"page": url,
                         "description": strip_chrome(page_text(conn, url),
                                                     name, f"{name} Style")}

    for name, desc in split_ma_styles(page_text(conn, MA_STYLES_PAGE)).items():
        entries[name] = {"page": MA_STYLES_PAGE, "description": desc}

    for name, desc in split_on_headings(page_text(conn, MA_TALENTS_PAGE), MA_TALENTS).items():
        entries[name] = {"page": MA_TALENTS_PAGE, "description": desc}

    for name, desc in split_on_headings(page_text(conn, SIEGE_PAGE), SIEGE).items():
        entries[name] = {"page": SIEGE_PAGE, "description": desc}

    problems = []
    for name, e in entries.items():
        desc = e["description"]
        if len(desc) < 40:
            problems.append(f"{name}: suspiciously short ({len(desc)} chars)")
        # A leftover stat header, or a sentence eaten off the front, both show up here.
        if re.match(r"^[(:,]|^Groups?:|^Initial rating|^Style\b|^\d", desc):
            problems.append(f"{name}: leftover header -> {desc[:60]!r}")
        if not desc[:1].isupper() and not desc.startswith(("“", '"')):
            problems.append(f"{name}: does not start a sentence -> {desc[:60]!r}")
    if problems:
        for p in problems:
            print("PROBLEM:", p, file=sys.stderr)
        raise SystemExit(f"{len(problems)} extraction problem(s); not writing ct_text.py")

    lines = ['"""ct_text.py — Combat & Tactics rules prose. GENERATED, DO NOT EDIT.',
             "",
             "Regenerate with:  python scripts/build_ct_text.py",
             "",
             'Maps a fighting style / unarmed discipline / talent to the page it comes',
             'from and its rules text, so the builder can show a "What it does" block',
             'without char_rules reaching into the database.',
             '"""',
             "",
             "CT_TEXT = {"]
    for name in sorted(entries):
        e = entries[name]
        lines.append(f"    {name!r}: {{")
        lines.append(f"        \"page\": {e['page']!r},")
        lines.append(f"        \"description\": {e['description']!r},")
        lines.append("    },")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(entries)} entries")


if __name__ == "__main__":
    main()

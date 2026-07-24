"""ask_retrieval.py — the text work behind "Ask the Rules", with no Qt and no SQL.

Two jobs sit either side of the model, and neither needs a thread, a socket or a
database:

  * **question -> search query.** ``terms`` normalises a question into rulebook
    vocabulary (stopwords dropped, colloquialisms mapped: "hp" -> hit points, "crit"
    -> critical hit) and ``fts_query`` / ``fts_from_terms`` turn that into FTS5
    syntax. ``title_is_query`` scores the strong signal that a page titled entirely
    in the question's own words is the canonical page for it.
  * **model answer -> rendered Markdown.** ``linkify`` turns the bare ``dnd:///``
    URLs a small local model emits into proper ``[Title](url)`` links, and
    ``mark_house_rules`` gives house-rule mentions the crossed-swords marker the
    rest of the app uses.

Extracted from ``rules_agent``, which remains the Qt + Ollama + SQL layer. That
module is the app's one grandfathered exception to "all SQL lives in db.py" and its
least-covered code, precisely because a QThread that talks to a language model is
awkward to test. None of what follows has that excuse: it is string in, string out,
and the retrieval quality of the whole feature rests on it.

``rules_agent`` imports from here, never the reverse — the ranking weights stay with
the SQL query they are interpolated into.
"""
import re
from html import unescape


# Common words that only add noise to a keyword search.
_STOP = set(
    "a an the to of for in on at by is are am be been being do does did done how "
    "what when where which who whom whose why will would can could should i me my "
    "we us our you your he she it its they them their that this these those with "
    "without as if then than so just about into over under out up down get gets "
    "getting got use used using need needs want wants make makes made also many "
    "much more most some any all each per vs versus and or but not no yes there "
    "here work works working does".split()
)

# Colloquial / shorthand → the vocabulary the 2e rulebooks actually use.
_SYN = {
    "stat": ["ability", "scores"], "stats": ["ability", "scores"],
    "statistic": ["ability", "scores"], "statistics": ["ability", "scores"],
    "hp": ["hit points", "hit dice"], "hitpoints": ["hit points", "hit dice"],
    "health": ["hit points"], "fighter": ["warrior"], "paladin": ["warrior"],
    "ranger": ["warrior"], "mage": ["wizard"], "priest": ["cleric"],
    "ac": ["armor class"], "armour": ["armor"],
    "xp": ["experience"], "exp": ["experience"],
    "init": ["initiative"], "crit": ["critical hit"], "crits": ["critical hit"],
    "dmg": ["damage"], "tohit": ["attack roll"], "thaco": ["thac0"],
    "str": ["strength"], "dex": ["dexterity"], "con": ["constitution"],
    "int": ["intelligence"], "wis": ["wisdom"], "cha": ["charisma"],
    "lvl": ["level"], "lvls": ["level"], "leveling": ["experience", "level"],
    "save": ["saving throw"], "saves": ["saving throws"],
    "gp": ["coins"], "gold": ["coins", "treasure"], "money": ["coins", "treasure"],
    "grapple": ["wrestling"], "wrestle": ["wrestling"], "grappling": ["wrestling"],
    "multiclass": ["multi-class"], "multiclassing": ["multi-class"],
    "spellcasting": ["spells"], "caster": ["wizard", "priest"],
    "rolls": ["rolling"], "movement": ["move"], "encumbrance": ["weight"],
    # colloquial / edition-shorthand -> 2e rulebook terminology
    "sneak": ["backstab", "move silently"], "stealth": ["move silently", "hide in shadows"],
    "hide": ["hide in shadows"], "hiding": ["hide in shadows"],
    "resurrect": ["raise dead", "resurrection"], "resurrecting": ["raise dead"],
    "revive": ["raise dead"], "rez": ["raise dead"],
    "bribe": ["reaction"], "bribing": ["reaction"], "persuade": ["reaction"],
    "tie": ["binding"], "restrain": ["binding", "wrestling"],
    "disarm": ["disarm"], "enemy": ["opponent"], "opponent": ["opponent"],
}


def terms(text: str) -> list:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out: list = []
    for t in toks:
        if len(t) < 2 or t in _STOP:
            continue
        if t not in out:
            out.append(t)
        for s in _SYN.get(t, []):
            if s not in out:
                out.append(s)
    if not out:                                  # query was all stopwords
        out = [t for t in toks if len(t) >= 3]
    return out[:16]


def fts_from_terms(atoms: list, fallback: str = "", prefix: bool = False) -> str:
    seen: list = []
    for t in atoms:
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    if not seen:
        return f'"{fallback.strip()}"' if fallback.strip() else '""'
    atoms = []
    for t in seen[:20]:
        # Prefix-match plain words (≥4 chars) so the un-stemmed FTS index still
        # matches singular/plural and inflections: lock*→lock/locks, climb*→
        # climbing, spell*→spells. Phrases and short/odd tokens stay exact.
        if prefix and t.isascii() and t.isalnum() and len(t) >= 4:
            atoms.append(f"{t}*")
        else:
            atoms.append(f'"{t}"')
    return " OR ".join(atoms)


def fts_query(text: str) -> str:
    return fts_from_terms(terms(text), fallback=text)


# Minor words ignored when testing whether a page title is "made of" query words.
_TITLE_MINOR = {"a", "an", "the", "of", "in", "on", "to", "for", "and", "or",
                "vs", "with", "your", "you", "how", "into", "at", "by"}


def query_stems(atoms: list) -> set:
    """Flatten query atoms (tokens + multi-word phrases) into a set of word stems."""
    stems: set = set()
    for atom in atoms:
        for w in re.findall(r"[a-z0-9]+", atom.lower()):
            stems.add(w)
    return stems


def title_is_query(clean_title: str, stems: set) -> bool:
    """True if every meaningful word of the title is covered by a query stem.

    Captures the strong signal that a page titled entirely in the question's own
    words (e.g. "Movement", "Poison", "Charisma") is the canonical page for it,
    even when a longer prose page loses on raw term-frequency.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", clean_title.lower())
             if w not in _TITLE_MINOR]
    if not words:
        return False
    for w in words:
        if not any(w == s or (len(s) >= 4 and w.startswith(s))
                   or (len(w) >= 4 and s.startswith(w)) for s in stems):
            return False
    return True


def strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


def linkify(text: str, titles: dict) -> str:
    """Turn bare / bracketed dnd:/// URLs into proper [Title](url) Markdown links,
    so they render as clickable links even if the model didn't format them."""
    def _title(url: str) -> str:
        key = url[len("dnd:///"):]
        return titles.get(key, key.rsplit("/", 1)[-1].replace(".htm", ""))

    # [dnd:///PHB/DD01673.htm]  ->  [Figuring the To-Hit Number](dnd:///PHB/DD01673.htm)
    text = re.sub(r'\[(dnd:///[A-Za-z0-9/._#\-]+)\]',
                  lambda m: f'[{_title(m.group(1))}]({m.group(1)})', text)
    # bare dnd:///... that isn't already the target of a [text](...) link
    text = re.sub(r'(?<![(\[])dnd:///[A-Za-z0-9/._#\-]+',
                  lambda m: f'[{_title(m.group(0))}]({m.group(0)})', text)
    return text


def mark_house_rules(text: str) -> str:
    """Prefix house-rule mentions with the crossed-swords marker used in the books."""
    text = re.sub(r'(?im)(?:⚔️?\s*)?\*{0,2}house rules?\*{0,2}\s*:\*{0,2}',
                  '⚔️ **House Rule:**', text)
    text = re.sub(r'(?i)\((?:⚔️?\s*)?house rules?\)', '(⚔️ house rule)', text)
    return text

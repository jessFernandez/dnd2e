"""toc.py — turn a book's flat TOC entries into a chapter tree.

Pure functions (no DB, no Qt): they take the rows db.toc_entries / db.chapter_markers
return and group them into chapters, so the (previously untested) grouping logic
can be exercised directly. See tests/test_toc.py.

Shapes:
  entries : iterable of (page_url, subtopic)   — every TOC row, in page order
  markers : iterable of (subtopic, page_url)   — rows that open a chapter/part/…
  chapter : {"name": str, "page_url": str, "entries": [(page_url, subtopic), …]}
"""
import re
from collections import defaultdict

_CHAPTER_NAME_RE = re.compile(
    r"^(.+?)--\s*(Chapter\s+\d+|Part\s+\d+|Book\s+\d+|Appendix\s+\w+)", re.I)


def extract_chapter_name(subtopic: str) -> str:
    """'Combat-- Chapter 9 (PHB)' -> 'Chapter 9: Combat'; else the bare label."""
    m = _CHAPTER_NAME_RE.match(subtopic)
    if m:
        return f"{m.group(2).strip()}: {m.group(1).strip()}"
    return subtopic.split("(")[0].strip()


def chapters_from_markers(entries, markers) -> list:
    """Group entries into chapters delimited by the marker rows."""
    marker_map = {url: sub for sub, url in markers}
    marker_set = set(marker_map)
    chapters, pre, current = [], [], None

    for page_url, subtopic in entries:
        if page_url in marker_set:
            if current is not None:
                chapters.append(current)
            elif pre:
                chapters.append({"name": "Introduction", "page_url": pre[0][0], "entries": pre})
                pre = []
            current = {
                "name":     extract_chapter_name(marker_map[page_url]),
                "page_url": page_url,
                "entries":  [(page_url, subtopic)],
            }
        elif current is not None:
            current["entries"].append((page_url, subtopic))
        else:
            pre.append((page_url, subtopic))

    if current is not None:
        chapters.append(current)
    if pre:
        chapters.insert(0, {"name": "Introduction", "page_url": pre[0][0], "entries": pre})
    return chapters


def chapters_by_letter(entries) -> list:
    """Fallback for books with no chapter markers: group alphabetically."""
    by_letter = defaultdict(list)
    for page_url, subtopic in entries:
        letter = subtopic[0].upper() if subtopic else "#"
        by_letter[letter].append((page_url, subtopic))
    return [
        {"name": letter, "page_url": entries0[0][0], "entries": entries0}
        for letter, entries0 in sorted(by_letter.items())
    ]


def build_chapters(entries, markers) -> list:
    """Chapter tree for a book: marker-delimited if any markers, else by letter."""
    entries = [tuple(e) for e in entries]
    if not entries:
        return []
    markers = list(markers)
    return chapters_from_markers(entries, markers) if markers else chapters_by_letter(entries)


def tree_page_urls(nodes) -> set:
    """Every page_url the nested tree reaches, at any depth. Folders carry None and
    contribute nothing."""
    found = set()

    def walk(node):
        if node["page_url"]:
            found.add(node["page_url"])
        for child in node["children"]:
            walk(child)

    for node in nodes or ():
        walk(node)
    return found


def entries_missing_from_tree(nodes, entries) -> list:
    """The (page_url, subtopic) entries the nested tree doesn't reach, in `entries`
    order, deduplicated.

    The site's TOC XML is not a complete index of its own pages: 25 real content
    pages across six books have a `toc_entries` row but no `toc_tree` node — the
    Skills & Powers ability-score write-ups (Strength, Reason, Knowledge, Intuition,
    Willpower), *Arms and Equipment*'s Polearms, a Tome of Magic chapter opener,
    *Spells and Magic*'s Spheres of Access, and five psionicist proficiencies.

    Because a book with any tree rows renders from the tree alone, those pages had
    no route in the browse sidebar at all — reachable only by search or a
    cross-reference, and once there, stranded: the reading order Prev/Next walks is
    built from the same tree, so both buttons went dead.

    Pure so the gap can be measured in a test (see tests/test_toc.py) rather than
    noticed by a reader who goes looking for a page that is in the book.
    """
    covered = tree_page_urls(nodes)
    seen, out = set(), []
    for page_url, subtopic in entries:
        if page_url in covered or page_url in seen:
            continue
        seen.add(page_url)
        out.append((page_url, subtopic))
    return out


def build_tree(rows) -> list:
    """Reconstruct the site's real nested TOC tree from flat rows.

    `rows` are (id, parent_id, position, name, page_url) — see db.toc_tree. Returns
    the root nodes (those whose parent_id is None), each a dict
    {"name": str, "page_url": str|None, "children": [node, …]} ordered by position;
    folders carry a None page_url. Returns [] for no rows, so the caller can fall
    back to the flat chapter layout on an older DB with no toc_tree table.
    """
    from collections import defaultdict
    nodes, children = {}, defaultdict(list)
    for row in rows:
        nid, pid, pos, name, url = row[0], row[1], row[2], row[3], row[4]
        nodes[nid] = {"name": name, "page_url": url, "children": []}
        children[pid].append((pos, nid))

    def attach(pid):
        out = []
        for _pos, nid in sorted(children.get(pid, [])):
            node = nodes[nid]
            node["children"] = attach(nid)
            out.append(node)
        return out

    return attach(None)

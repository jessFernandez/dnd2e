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

"""build_toc_tree.py — populate the `toc_tree` table from the site's real TOC tree.

The original site (regalgoblins.com/2erules) renders its browse sidebar from a
nested XML document (`pw_toc_6.xml`) loaded by a JavaScript tree widget — NOT from
the flat alphabetical index the original scraper read. That XML is the faithful,
arbitrary-depth hierarchy (Book › Chapter › Section › page), so we mirror it into
a `toc_tree` table the app renders directly. See docs/toc-tree-fidelity.md.

XML shape (per node):
    <li>
      <o><p n="N" v="Node Name"/><p n="L" v="BOOK\\PAGE.htm"/></o>   # page (has a link)
      <ul> …child <li>s… </ul>                                       # folder (has children)
    </li>
A node with a link is a page (leaf); one without is a folder. Book display names
in the XML differ from ours (e.g. "Player's Option: Combat and Tactics"), so the
book code is taken from a node's link prefix, and only INCLUDED_BOOKS are kept.

Run:  python scripts/build_toc_tree.py                 # fetch live and rebuild
      python scripts/build_toc_tree.py --file toc.xml  # parse a saved copy instead
"""
import argparse
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # repo root (this script lives in scripts/)
DB_PATH = ROOT / "dnd2e.db"
XML_URL = "https://regalgoblins.com/2erules/pw_toc_6.xml"

# Same whitelist the app ships (scraper.INCLUDED_BOOKS); other books in the XML
# (the Complete Handbooks, etc.) are skipped.
INCLUDED_BOOKS = {"PHB", "DMG", "MM", "SP", "HLC", "TM", "SM", "CT", "AEG"}


def _props(li):
    """{'N': name, 'L': link} for a <li>'s direct <o> object."""
    o = li.find("o")
    return {p.get("n"): p.get("v") for p in o.findall("p")} if o is not None else {}


def _book_code(li):
    """Book code from the first descendant page link, e.g. 'CT\\DD..' -> 'CT'."""
    link = next((p.get("v") for p in li.iter("p") if p.get("n") == "L"), None)
    return link.split("\\")[0] if link else None


class _Walker:
    """Assigns dense ids while flattening the tree to (id, book, parent, pos, name, url) rows."""

    def __init__(self):
        self.rows = []
        self._next = 0

    def walk(self, li, book_code, parent_id, position):
        props = _props(li)
        link = props.get("L")
        page_url = link.replace("\\", "/") if link else None
        node_id = self._next
        self._next += 1
        self.rows.append((node_id, book_code, parent_id, position,
                          (props.get("N") or "").strip(), page_url))
        child_ul = li.find("ul")
        if child_ul is not None:
            for i, child in enumerate(child_ul.findall("li")):
                self.walk(child, book_code, node_id, i)


def parse_tree(xml_text: str):
    """Flatten the site TOC XML into rows for the INCLUDED_BOOKS.

    A book's top-level chapters become roots (parent_id NULL); the book node
    itself is not stored (the app draws the book header separately)."""
    root = ET.fromstring(xml_text)
    walker = _Walker()
    for book_li in root.find("ul").findall("li"):
        code = _book_code(book_li)
        if code not in INCLUDED_BOOKS:
            continue
        child_ul = book_li.find("ul")
        if child_ul is None:
            continue
        for i, chapter_li in enumerate(child_ul.findall("li")):
            walker.walk(chapter_li, code, None, i)
    return walker.rows


def write_rows(conn, rows):
    conn.execute("DROP TABLE IF EXISTS toc_tree")
    conn.execute(
        "CREATE TABLE toc_tree ("
        "id INTEGER PRIMARY KEY, book_code TEXT NOT NULL, parent_id INTEGER, "
        "position INTEGER NOT NULL, name TEXT NOT NULL, page_url TEXT)")
    conn.executemany(
        "INSERT INTO toc_tree (id, book_code, parent_id, position, name, page_url) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.execute("CREATE INDEX idx_toc_tree_book ON toc_tree(book_code)")
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="parse a saved pw_toc_6.xml instead of fetching")
    args = ap.parse_args()

    if args.file:
        xml_text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        req = urllib.request.Request(XML_URL, headers={"User-Agent": "Mozilla/5.0"})
        xml_text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

    rows = parse_tree(xml_text)
    conn = sqlite3.connect(str(DB_PATH))
    write_rows(conn, rows)

    books = sorted({r[1] for r in rows})
    folders = sum(1 for r in rows if r[5] is None)
    print(f"Wrote toc_tree: {len(rows)} nodes across {len(books)} books "
          f"({folders} folders, {len(rows) - folders} pages).")
    for b in books:
        print(f"  {b}: {sum(1 for r in rows if r[1] == b)} nodes")


if __name__ == "__main__":
    main()

"""build_chunks.py — split rulebook pages into passages for sharper retrieval.

Long 2e pages (the thief-skills page alone is ~2,500 words covering 8 skills)
dilute a single rule under BM25 length-normalization, so the page that actually
answers a question can rank below short table/supplement pages. This builds a
`chunks_fts` table where each labelled section ("Hide in Shadows:", "Open
Locks:", …) — or, for heading-less prose, each ~180-word sentence window — is
indexed on its own. Retrieval then scores the *passage*, and the matched passage
becomes the excerpt the model sees (tighter than page-start truncation).

Idempotent: drops and rebuilds chunks_fts. Run:  python scripts/build_chunks.py
"""
import re
import sqlite3
from pathlib import Path

DB = str(Path(__file__).resolve().parent.parent / "dnd2e.db")   # repo root (script lives in scripts/)
TARGET_WORDS = 180      # flush a passage once it reaches ~this size
MIN_WORDS    = 60       # merge anything smaller into a neighbour (avoid fragments)
MAX_WORDS    = 300      # hard cap before a section is sentence-split


def _is_heading(line: str) -> bool:
    """A short label line like 'Hide in Shadows:' that opens a section."""
    w = line.split()
    return bool(line.endswith(":")) and 1 <= len(w) <= 7


def _sentence_pack(text: str, target: int = TARGET_WORDS, cap: int = MAX_WORDS):
    """Pack a long heading-less block into ~target-word windows on sentence bounds."""
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, buf, w = [], [], 0
    for s in sents:
        sw = len(s.split())
        if w + sw > target and buf:
            out.append(" ".join(buf)); buf, w = [], 0
        buf.append(s); w += sw
    if buf:
        out.append(" ".join(buf))
    return out


def split_page(text: str):
    """Split one page's content_text into passage strings."""
    text = (text or "").replace("\r", "")
    if len(text.split()) <= TARGET_WORDS:
        t = re.sub(r"\s+", " ", text).strip()
        return [t] if t else []

    # Group hard-wrapped lines into (heading-led) blocks.
    blocks, head, cur = [], None, []
    for raw in text.split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        if _is_heading(ln):
            if cur:
                blocks.append(((head + " ") if head else "") + " ".join(cur))
                cur = []
            head = ln
        else:
            cur.append(ln)
    if cur or head:
        blocks.append(((head + " ") if head else "") + " ".join(cur))

    # Greedily pack sections into ~TARGET-word passages (oversize ones are
    # sentence-split); this keeps a full labelled section together while merging
    # tiny cross-reference fragments so they can't dominate BM25 on their own.
    chunks, buf, w = [], [], 0
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if not b:
            continue
        if len(b.split()) > MAX_WORDS:
            if buf:
                chunks.append(" ".join(buf)); buf, w = [], 0
            chunks.extend(_sentence_pack(b))
            continue
        buf.append(b); w += len(b.split())
        if w >= TARGET_WORDS:
            chunks.append(" ".join(buf)); buf, w = [], 0
    if buf:
        if chunks and w < MIN_WORDS:             # fold a tiny tail into the last passage
            chunks[-1] = chunks[-1] + " " + " ".join(buf)
        else:
            chunks.append(" ".join(buf))
    return chunks


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS chunks_fts")
    c.execute("""CREATE VIRTUAL TABLE chunks_fts USING fts5(
                     page_url UNINDEXED, chunk_no UNINDEXED, title, body)""")
    pages = c.execute("SELECT page_url, title, content_text FROM pages").fetchall()
    n_pages = n_chunks = 0
    rows = []
    for url, title, text in pages:
        parts = split_page(text)
        if not parts:
            continue
        n_pages += 1
        for i, body in enumerate(parts):
            rows.append((url, i, title or "", body))
            n_chunks += 1
    c.executemany("INSERT INTO chunks_fts(page_url, chunk_no, title, body) VALUES (?,?,?,?)", rows)
    conn.commit()
    conn.close()
    print(f"chunked {n_pages} pages into {n_chunks} passages "
          f"(avg {n_chunks / max(n_pages,1):.1f} per page)")


if __name__ == "__main__":
    main()

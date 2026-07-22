"""build_images.py — pull the rulebook's page art into dnd2e.db.

The original scrape took the rulebook's text and left its pictures on the
website. Because the web view resolves relative URLs against
BASE_URL + the page's folder, every <img> in a stored page was a silent live
request to regalgoblins.com — so a reference app meant to work offline quietly
needed someone else's server, and rendered broken tags when it was unreachable.

This walks every page, resolves each <img src> through page_images.resolve (the
same function the app uses to look one up, so the stored key and the requested
key cannot drift), downloads what is missing, and stores the bytes in an
`images` table. ~317 files, ~7.5 MB.

Idempotent: images already in the table are skipped, so a re-run after a
re-scrape fetches only what is new. Nothing here runs in the app or in CI — like
the other generators it is a manual, one-off tool, and it is the reason the app
itself no longer talks to the network at all.

Run:  python scripts/build_images.py              # fetch what is missing
      python scripts/build_images.py --dry-run    # list what would be fetched
      python scripts/build_images.py --refetch    # re-download everything
"""
import argparse
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # repo root (this script lives in scripts/)
sys.path.insert(0, str(ROOT))                   # so `import db` / `page_images` works

import db                  # noqa: E402  (path shim above must run first)
import page_images         # noqa: E402

DB_PATH  = ROOT / "dnd2e.db"
BASE_URL = "https://regalgoblins.com/2erules/"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Referer": BASE_URL}

# The site is a hobbyist host and this is a one-off bulk read; pause between
# requests rather than hammering it.
DELAY_S = 0.3


def referenced_keys(conn) -> dict:
    """{image key: first page that referenced it} across the whole rulebook."""
    found = {}
    for row in conn.execute("SELECT page_url, content_html FROM pages"):
        for key in page_images.page_image_keys(row["page_url"], row["content_html"]):
            found.setdefault(key, row["page_url"])
    return found


def fetch(key: str) -> bytes:
    req = urllib.request.Request(BASE_URL + key, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="list what is missing, fetch nothing")
    ap.add_argument("--refetch", action="store_true", help="re-download images already stored")
    args = ap.parse_args()

    conn = db.connect(DB_PATH)
    db.ensure_images_schema(conn)

    wanted = referenced_keys(conn)
    have   = set() if args.refetch else db.image_keys(conn)
    todo   = sorted(k for k in wanted if k not in have)

    print(f"referenced: {len(wanted)}   already stored: {len(wanted) - len(todo)}   "
          f"to fetch: {len(todo)}")
    if args.dry_run:
        for k in todo:
            print(f"  would fetch  {k}   (first seen on {wanted[k]})")
        return

    ok = failed = total = 0
    for i, key in enumerate(todo, 1):
        try:
            blob = fetch(key)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"  [{i}/{len(todo)}] FAIL {key}: {type(e).__name__}: {e}")
            failed += 1
            continue
        db.put_image(conn, key, blob)
        ok += 1
        total += len(blob)
        print(f"  [{i}/{len(todo)}] {len(blob):>8,} B  {key}")
        if i % 25 == 0:
            conn.commit()
        time.sleep(DELAY_S)

    conn.commit()
    count, stored = db.image_stats(conn)
    print(f"\nfetched {ok}, failed {failed} ({total/1e6:.1f} MB this run)")
    print(f"images table now: {count} rows, {stored/1e6:.1f} MB")

    # A page referencing art we could not fetch still renders — page_images.rewrite
    # leaves unknown srcs alone — but it is worth knowing about.
    missing = sorted(k for k in wanted if k not in db.image_keys(conn))
    if missing:
        print(f"\nstill missing ({len(missing)}):")
        for k in missing[:20]:
            print(f"  {k}   (referenced by {wanted[k]})")

    try:
        conn.execute("VACUUM")          # reclaim churn from a --refetch
    except sqlite3.Error:
        pass
    conn.close()


if __name__ == "__main__":
    main()

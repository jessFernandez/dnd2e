"""page_images.py — turn the rulebook's remote <img> tags into local ones.

The scrape took the rulebook's *text* into dnd2e.db and left its pictures on the
website. 319 of the 4,609 pages carry an <img>, 383 tags between them resolving
to 317 distinct files, and every one of those was a live fetch from
regalgoblins.com: the web view's base URL is BASE_URL + the page's folder, so a
relative src silently became a request. That made a local-first reference app
depend on someone else's server staying up.

The images now live in the rulebook DB (see db.ensure_images_schema) and this
module is the piece that connects the two — resolving what an <img src> on a
given page *means*, and rewriting the tag to an inline data: URI.

It is deliberately Qt-free and knows nothing about SQL. Callers pass a `lookup`
callable, so the same logic serves the app (reading from dnd2e.db) and
scripts/build_images.py (which uses `resolve` to decide what to download in the
first place). One resolver for both sides means the key a page asks for and the
key the fetcher stored can never drift apart.
"""
import base64
import posixpath
import re

# src="..." or src=... — the rulebook's HTML is inconsistent about quoting.
_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*)(["\']?)([^"\'>\s]+)\2', re.I)

# Schemes we cannot localise: already-inline data, or an absolute URL pointing
# somewhere other than the scraped site. None appear in the current corpus, but a
# future re-scrape could introduce one and it must pass through untouched.
_ABSOLUTE_RE = re.compile(r'^(?:[a-z][a-z0-9+.-]*:|//)', re.I)

# Extension → MIME. The corpus is entirely .gif, but a re-scrape could bring
# others, and a wrong MIME in a data: URI renders as a broken image.
_MIME = {
    ".gif":  "image/gif",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".bmp":  "image/bmp",
    ".webp": "image/webp",
}


def mime_for(key: str) -> str:
    """The MIME type for a stored image key. Unknown extensions fall back to GIF,
    which is what every image in the scraped corpus actually is."""
    dot = key.rfind(".")
    return _MIME.get(key[dot:].lower() if dot >= 0 else "", "image/gif")


def resolve(page_url: str, src: str) -> str | None:
    """The canonical DB key for `src` as written on `page_url`, or None if the
    reference cannot be localised (absolute URL, data: URI, or an escape above
    the rulebook root).

    Keys are rulebook-root-relative and forward-slashed: a page "MM/DD01671.htm"
    referring to "AARAKOCR.gif" yields "MM/AARAKOCR.gif". 66 tags in the corpus
    use Windows separators ("..\\AEG\\DD90000.gif"), which is why separators are
    normalised before anything else.
    """
    if not src:
        return None
    src = src.replace("\\", "/").strip()
    if not src or _ABSOLUTE_RE.match(src):
        return None

    folder = page_url.rsplit("/", 1)[0] if "/" in page_url else ""
    joined = posixpath.join(folder, src) if not src.startswith("/") else src.lstrip("/")
    key = posixpath.normpath(joined).replace("\\", "/")

    # normpath leaves a leading "../" when a src climbs past the rulebook root.
    # There is nothing above that root to serve, so such a reference is not ours.
    if key.startswith("../") or key in (".", "..", ""):
        return None
    return key


def page_image_keys(page_url: str, html: str) -> list[str]:
    """Every localisable image key referenced by `html`, in order, deduplicated.
    Used by scripts/build_images.py to enumerate what needs downloading."""
    seen, out = set(), []
    for _, _, src in _IMG_SRC_RE.findall(html or ""):
        key = resolve(page_url, src)
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def data_uri(key: str, blob: bytes) -> str:
    """An inline data: URI for stored image bytes."""
    return f"data:{mime_for(key)};base64,{base64.b64encode(blob).decode('ascii')}"


def rewrite(html: str, page_url: str, lookup) -> str:
    """`html` with every stored <img src> replaced by an inline data: URI.

    `lookup` takes a key and returns the image bytes, or None when the DB has no
    copy. Anything unresolvable or missing is left exactly as written, so a page
    whose art was never fetched degrades to the old remote behaviour rather than
    rendering a broken tag.

    Returns `html` unchanged (same object) when it has no <img> at all — true of
    4,290 of the 4,609 pages, so the common path stays free.
    """
    if not html or "<img" not in html.lower():
        return html

    def swap(m):
        prefix, quote, src = m.group(1), m.group(2), m.group(3)
        key = resolve(page_url, src)
        if not key:
            return m.group(0)
        blob = lookup(key)
        if not blob:
            return m.group(0)
        q = quote or '"'
        return f"{prefix}{q}{data_uri(key, blob)}{q}"

    return _IMG_SRC_RE.sub(swap, html)

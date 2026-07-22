"""Tests for page_images — the <img src> resolver and rewriter.

The resolver is the load-bearing part: scripts/build_images.py uses it to decide
what to download and the app uses it to decide what to look up, so a bug here
does not render a wrong image, it stores art under a key nothing ever asks for.
"""
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db              # noqa: E402
import page_images     # noqa: E402

RULES_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

GIF = b"GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;"


# ── resolve ──────────────────────────────────────────────────────────────────

def test_sibling_file_resolves_against_the_pages_folder():
    assert page_images.resolve("MM/DD01671.htm", "AARAKOCR.gif") == "MM/AARAKOCR.gif"


def test_windows_separators_are_normalised():
    """66 tags in the corpus are written with backslashes."""
    assert page_images.resolve("HLC/DD01156.htm", r"..\AEG\DD90000.gif") == "AEG/DD90000.gif"


def test_parent_traversal_crosses_between_books():
    assert page_images.resolve("MM/DD01.htm", "../CT/DIAGRM1.gif") == "CT/DIAGRM1.gif"


def test_explicit_current_directory_is_collapsed():
    assert page_images.resolve("CT/DD02374.htm", "./DIAGRM1.gif") == "CT/DIAGRM1.gif"


def test_root_relative_src_drops_the_leading_slash():
    assert page_images.resolve("MM/DD01.htm", "/MM/ABOLETH.gif") == "MM/ABOLETH.gif"


@pytest.mark.parametrize("src", [
    "https://example.com/x.gif",
    "http://example.com/x.gif",
    "//example.com/x.gif",
    "data:image/gif;base64,AAAA",
])
def test_absolute_and_inline_sources_are_not_ours(src):
    assert page_images.resolve("MM/DD01.htm", src) is None


def test_escaping_above_the_rulebook_root_is_refused():
    """Nothing lives above the root, so such a reference cannot be localised."""
    assert page_images.resolve("MM/DD01.htm", "../../etc/passwd") is None


@pytest.mark.parametrize("src", ["", "   ", None])
def test_empty_sources_resolve_to_nothing(src):
    assert page_images.resolve("MM/DD01.htm", src) is None


def test_a_page_at_the_root_still_resolves():
    assert page_images.resolve("index.htm", "logo.gif") == "logo.gif"


# ── mime ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key,mime", [
    ("MM/ABOLETH.gif", "image/gif"),
    ("MM/X.PNG",       "image/png"),
    ("MM/x.jpeg",      "image/jpeg"),
    ("MM/x.jpg",       "image/jpeg"),
    ("MM/noext",       "image/gif"),   # the corpus is all GIF
])
def test_mime_follows_the_extension(key, mime):
    assert page_images.mime_for(key) == mime


# ── page_image_keys ──────────────────────────────────────────────────────────

def test_keys_are_deduplicated_but_keep_first_seen_order():
    html = ('<img src="B.gif"><img src="A.gif"><img src="B.gif">')
    assert page_images.page_image_keys("MM/p.htm", html) == ["MM/B.gif", "MM/A.gif"]


def test_unquoted_src_is_still_found():
    """The rulebook's HTML is inconsistent about quoting."""
    assert page_images.page_image_keys("MM/p.htm", "<img src=ABOLETH.gif>") == ["MM/ABOLETH.gif"]


def test_a_page_with_no_images_yields_nothing():
    assert page_images.page_image_keys("MM/p.htm", "<p>text</p>") == []


# ── rewrite ──────────────────────────────────────────────────────────────────

def test_a_stored_image_becomes_an_inline_data_uri():
    out = page_images.rewrite('<img src="ABOLETH.gif">', "MM/p.htm", lambda k: GIF)
    assert "data:image/gif;base64," + base64.b64encode(GIF).decode() in out
    assert "ABOLETH.gif" not in out


def test_an_image_we_never_fetched_is_left_alone():
    """Degrades to the old remote behaviour rather than rendering a broken tag."""
    html = '<img src="ABOLETH.gif">'
    assert page_images.rewrite(html, "MM/p.htm", lambda k: None) == html


def test_other_attributes_and_tags_survive_the_rewrite():
    html = '<p><img class="art" src="A.gif" width="200" alt="x"></p>'
    out = page_images.rewrite(html, "MM/p.htm", lambda k: GIF)
    assert 'class="art"' in out and 'width="200"' in out and 'alt="x"' in out
    assert out.startswith("<p><img") and out.endswith("></p>")


def test_unquoted_src_is_rewritten_with_quotes_added():
    out = page_images.rewrite("<img src=A.gif>", "MM/p.htm", lambda k: GIF)
    assert 'src="data:image/gif;base64,' in out


def test_absolute_urls_are_passed_through_untouched():
    html = '<img src="https://example.com/x.gif">'
    assert page_images.rewrite(html, "MM/p.htm", lambda k: GIF) == html


def test_html_without_images_is_returned_unchanged():
    html = "<p>no art here</p>"
    assert page_images.rewrite(html, "MM/p.htm", lambda k: GIF) is html


def test_lookup_is_not_called_for_pages_without_images():
    """The 4,290 image-free pages must not pay for this feature."""
    calls = []
    page_images.rewrite("<p>text</p>", "MM/p.htm", lambda k: calls.append(k))
    assert calls == []


def test_each_image_on_a_page_is_looked_up_by_its_own_key():
    seen = []

    def lookup(k):
        seen.append(k)
        return GIF

    page_images.rewrite('<img src="A.gif"><img src="../CT/B.gif">', "MM/p.htm", lookup)
    assert seen == ["MM/A.gif", "CT/B.gif"]


# ── the db side ──────────────────────────────────────────────────────────────

def test_images_round_trip_through_the_database(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.ensure_images_schema(conn)
    db.put_image(conn, "MM/ABOLETH.gif", GIF)
    conn.commit()
    assert db.get_image(conn, "MM/ABOLETH.gif") == GIF
    assert db.image_keys(conn) == {"MM/ABOLETH.gif"}
    assert db.image_stats(conn) == (1, len(GIF))


def test_put_image_replaces_rather_than_duplicating(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.ensure_images_schema(conn)
    db.put_image(conn, "MM/A.gif", GIF)
    db.put_image(conn, "MM/A.gif", GIF + b"more")
    conn.commit()
    assert db.image_stats(conn)[0] == 1
    assert db.get_image(conn, "MM/A.gif") == GIF + b"more"


def test_a_missing_key_reads_as_none(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.ensure_images_schema(conn)
    assert db.get_image(conn, "nope.gif") is None


def test_a_database_without_the_images_table_degrades_quietly(tmp_path):
    """An older dnd2e.db must still open — reads return empty, not an exception."""
    conn = db.connect(tmp_path / "old.db")
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    assert db.get_image(conn, "MM/A.gif") is None
    assert db.image_keys(conn) == set()
    assert db.image_stats(conn) == (0, 0)


def test_ensure_images_schema_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.ensure_images_schema(conn)
    db.put_image(conn, "MM/A.gif", GIF)
    conn.commit()
    db.ensure_images_schema(conn)          # must not wipe an existing user's data
    assert db.get_image(conn, "MM/A.gif") == GIF


# ── against the real corpus ──────────────────────────────────────────────────

@needs_db
def test_every_referenced_image_is_stored_in_the_shipped_database():
    """The whole point: no page should need the network to render its art."""
    conn = db.connect(RULES_DB)
    stored = db.image_keys(conn)
    if not stored:
        pytest.skip("images not yet fetched into this dnd2e.db "
                    "(run scripts/build_images.py)")
    missing = set()
    for row in conn.execute("SELECT page_url, content_html FROM pages"):
        for key in page_images.page_image_keys(row["page_url"], row["content_html"]):
            if key not in stored:
                missing.add(key)
    assert not missing, f"{len(missing)} referenced images are not in the DB: {sorted(missing)[:10]}"


@needs_db
def test_no_page_still_points_at_the_network_after_rewriting():
    conn = db.connect(RULES_DB)
    if not db.image_keys(conn):
        pytest.skip("images not yet fetched into this dnd2e.db")
    leftovers = []
    for row in conn.execute(
            "SELECT page_url, content_html FROM pages WHERE content_html LIKE '%<img%'"):
        out = page_images.rewrite(
            row["content_html"], row["page_url"],
            lambda k: db.get_image(conn, k))
        for _, _, src in page_images._IMG_SRC_RE.findall(out):
            if not src.startswith("data:"):
                leftovers.append((row["page_url"], src))
    assert not leftovers, f"{len(leftovers)} <img> tags still resolve remotely: {leftovers[:5]}"


@needs_db
def test_stored_bytes_actually_look_like_images():
    conn = db.connect(RULES_DB)
    keys = sorted(db.image_keys(conn))
    if not keys:
        pytest.skip("images not yet fetched into this dnd2e.db")
    bad = []
    for k in keys:
        blob = db.get_image(conn, k)
        # GIF87a/GIF89a, PNG, or JPEG magic — an HTML error page would fail this.
        if not (blob[:4] == b"GIF8" or blob[:4] == b"\x89PNG" or blob[:2] == b"\xff\xd8"):
            bad.append(k)
    assert not bad, f"{len(bad)} stored blobs are not images (error pages?): {bad[:10]}"

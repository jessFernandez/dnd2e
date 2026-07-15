"""Tests for monster.py — the MM stat-block parser and its house-rule conversions.

Pure tests build synthetic HTML stat blocks and always run; the DB-backed tests
parse the real Monstrous Manual pages and skip when dnd2e.db is absent (the
needs_db pattern from test_db.py).
"""
import os

import pytest

import db
import char_rules as cr
import monster
from monster import Monster, parse_stat_block

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

ANKHEG = "MM/DD03797.htm"       # single monster
BEAR = "MM/DD03805.htm"         # 4 variants, values on one line each
CAT_GREAT = "MM/DD03818.htm"    # 5 variants with wrapped names and values

LABELS = list(monster.FIELD_BY_LABEL)   # canonical order


def _html(rows, variants=(), prose=""):
    """A synthetic MM stat-block page. ``rows`` is (LABEL, [value per variant])
    pairs; each continuation row is ("", [...]) with an empty first cell."""
    trs = ""
    if variants:
        trs += "<TR><TD></TD>" + "".join(f"<TD>{v}</TD>" for v in variants) + "</TR>"
    for label, vals in rows:
        head = f"<TD><B>{label}:</B></TD>" if label else "<TD></TD>"
        trs += "<TR>" + head + "".join(f"<TD>{v}</TD>" for v in vals) + "</TR>"
    return f"<HTML><BODY><TABLE>{trs}</TABLE>{prose}</BODY></HTML>"


def _full(**field_vals):
    """One-variant page with every label filled (default 'x', overridable by field)."""
    rows = [(lab, [field_vals.get(monster.FIELD_BY_LABEL[lab], "x")]) for lab in LABELS]
    return _html(rows)


# ── house-rule conversions (pure, no parsing) ─────────────────────────────────

def test_attack_bonus_is_the_base_value():
    assert Monster(thac0="19").attack_bonus() == "1"
    assert Monster(thac0="17-13").attack_bonus() == "3"     # base (first) THAC0, not a range
    assert Monster(thac0="1+1 and 2+2 HD: 19 3+3 HD: 17").attack_bonus() == "1"  # first HD: value
    assert Monster(thac0="").attack_bonus() == ""
    assert Monster(thac0="Nil").attack_bonus() == ""


def test_ascending_ac_handles_negatives_and_notes():
    assert Monster(armor_class="5").ascending_ac() == "15"
    assert Monster(armor_class="-2").ascending_ac() == "22"          # AC can be negative
    assert Monster(armor_class="Overall 2, underside 4").ascending_ac() == "Overall 18, underside 16"


def test_size_category_takes_the_largest_of_a_range():
    assert Monster(size="M (6'+ tall)").size_category() == "M"
    assert Monster(size="L-H (10' to 20' long)").size_category() == "H"
    assert Monster(size="").size_category() == ""


def test_initiative_from_size_and_override():
    assert Monster(size="M").initiative_modifier() == 3
    assert Monster(size="L-H").initiative_modifier() == 9            # largest -> Huge
    assert Monster(size="G").initiative_modifier() == 12
    assert Monster(size="M", initiative_override=1).initiative_modifier() == 1
    assert Monster(size="???").initiative_modifier() is None


def test_char_rules_initiative_table_covers_every_size():
    assert [cr.monster_initiative_modifier(s) for s in "TSMLHG"] == [0, 3, 3, 6, 9, 12]
    assert cr.monster_initiative_modifier("Large") == 6             # first letter, case-folded
    assert cr.monster_initiative_modifier("") is None


# ── parsing (pure, synthetic HTML) ────────────────────────────────────────────

def test_parses_a_single_monster_with_all_fields():
    html = _html([(lab, ["v_" + monster.FIELD_BY_LABEL[lab]]) for lab in LABELS])
    (m,) = parse_stat_block(html, title="Ankheg (Monstrous Manual)", source_page=ANKHEG)
    assert m.name == "Ankheg" and m.variant == "" and m.source_page == ANKHEG
    assert m.climate_terrain == "v_climate_terrain"
    assert m.armor_class == "v_armor_class"
    assert m.xp_value == "v_xp_value"


def test_parses_multiple_variants_by_column():
    rows = [(lab, ["a", "b"]) for lab in LABELS]
    rows[LABELS.index("ARMOR CLASS")] = ("ARMOR CLASS", ["7", "6"])
    rows[LABELS.index("THAC0")] = ("THAC0", ["17", "15"])
    rows[LABELS.index("SIZE")] = ("SIZE", ["M", "L"])
    ms = parse_stat_block(_html(rows, variants=("Black", "Brown")),
                          title="Bear (Monstrous Manual)")
    assert [m.name for m in ms] == ["Black Bear", "Brown Bear"]
    assert [m.ascending_ac() for m in ms] == ["13", "14"]
    assert [m.attack_bonus() for m in ms] == ["3", "5"]
    assert [m.initiative_modifier() for m in ms] == [3, 6]


def test_stitches_wrapped_values_from_continuation_rows():
    # a value split across two cells (empty-first continuation row) is rejoined
    rows = [("CLIMATE/TERRAIN", ["Warm plains", "Tropical"]),
            ("", ["and grasslands", "jungle"]),          # continuation of the row above
            ("ARMOR CLASS", ["7", "6"]),
            ("SIZE", ["M", "L"])]
    ms = parse_stat_block(_html(rows, variants=("Cheetah", "Jaguar")),
                          title="Cat, Great (Monstrous Manual)")
    assert ms[0].climate_terrain == "Warm plains and grasslands"
    assert ms[1].climate_terrain == "Tropical jungle"


def test_normalizes_ocr_and_spacing_label_variants():
    rows = [("CLIMATE/ TERRAIN", ["Somewhere"]), ("ARMOR CLASS", ["5"]),
            ("THACO", ["19"]), ("ACTIVE TIME", ["Night"]), ("SIZE", ["S"])]
    (m,) = parse_stat_block(_html(rows), title="Foo (Monstrous Manual)")
    assert m.climate_terrain == "Somewhere"
    assert m.thac0 == "19"                      # THACO -> THAC0
    assert m.activity_cycle == "Night"          # ACTIVE TIME -> ACTIVITY CYCLE
    assert m.size == "S"


def test_splits_prose_into_sections():
    rows = [(lab, ["x"]) for lab in LABELS]
    prose = ("<P>The beast is fearsome.<P>Combat:<BR>It bites."
             "<P>Habitat/Society:<BR>It lurks.<P>Ecology:<BR>It eats.")
    (m,) = parse_stat_block(_html(rows, prose=prose), title="Beast (Monstrous Manual)")
    assert m.description == "The beast is fearsome."
    assert m.combat == "It bites."
    assert m.habitat_society == "It lurks."
    assert m.ecology == "It eats."


def test_non_monster_page_yields_nothing():
    assert parse_stat_block("<HTML><BODY><TABLE><TR><TD>Contents</TD></TR></TABLE></BODY></HTML>") == []
    assert parse_stat_block("") == []


def test_to_dict_from_dict_roundtrip():
    (m,) = parse_stat_block(_full(thac0="17", armor_class="4", size="L"),
                            title="Beast (Monstrous Manual)")
    assert Monster.from_dict(m.to_dict()) == m
    Monster.from_dict({"name": "X", "bogus": 1})   # tolerates unknown keys


# ── parsing the real Monstrous Manual (DB-backed) ─────────────────────────────

@pytest.fixture
def conn():
    c = db.connect(RULES_DB)
    yield c
    c.close()


def _parse_page(conn, page_url):
    row = db.get_page(conn, page_url)
    return parse_stat_block(row["content_html"], row["title"], page_url)


@needs_db
def test_parse_real_ankheg(conn):
    (m,) = _parse_page(conn, ANKHEG)
    assert m.name == "Ankheg"
    assert m.thac0 == "17-13" and m.attack_bonus() == "3"       # base attack bonus
    assert "Overall 2" in m.armor_class and m.ascending_ac().startswith("Overall 18")
    assert m.size_category() == "H" and m.initiative_modifier() == 9
    assert m.combat and "acid" in m.combat.lower()


@needs_db
def test_parse_real_bear_variants(conn):
    ms = _parse_page(conn, BEAR)
    names = [m.name for m in ms]
    assert "Black Bear" in names and "Polar Bear" in names
    black = next(m for m in ms if m.name == "Black Bear")
    assert black.thac0 == "17" and black.attack_bonus() == "3"
    polar = next(m for m in ms if m.name == "Polar Bear")
    assert polar.attack_bonus() == "9"          # THAC0 11 -> 20-11


@needs_db
def test_parse_real_cat_great_wrapped_columns(conn):
    """The regression that motivated HTML parsing: nine cats across two stacked
    stat-block groups, with wrapped names and values that content_text flattens."""
    ms = _parse_page(conn, CAT_GREAT)
    names = [m.name for m in ms]
    assert len(ms) == 9                                   # 5 in group 1, 4 in group 2
    assert any("Cheetah" in n for n in names)             # group 1
    assert any("Smilodon" in n for n in names)            # group 2
    cheetah = next(m for m in ms if "Cheetah" in m.name)
    # the wrapped climate value is stitched back, not a stray fragment
    assert "Warm plains" in cheetah.climate_terrain and "grass" in cheetah.climate_terrain
    assert cheetah.armor_class and not cheetah.armor_class.endswith(":")


# Pages with no parseable stat block: family lore pages, front matter, and two
# odd-format summary tables the parser doesn't yet handle. The parser correctly
# yields nothing for them.
CATEGORY_PAGES = {
    "MM/DD03842.htm",  # Dragon-- General
    "MM/DD03954.htm",  # Human (unusual format)
    "MM/DD04100.htm",  # Instructions for the Blank Monster Form
    "MM/DD03980.htm",  # Lycanthrope-- General
    "MM/DD03992.htm",  # Mammal-- Small (wrapped compact header)
    "MM/DD03794.htm",  # The Monsters
}


@needs_db
def test_parse_real_beholder_all_variants(conn):
    """A cosmetic blank row mid-stat-block once split this 6-variant group in two."""
    ms = _parse_page(conn, "MM/DD03808.htm")     # Beholder and Beholder-kin I
    assert len(ms) == 6
    assert any("Death Kiss" in m.name for m in ms)
    assert any("Spectator" in m.name for m in ms)
    for m in ms:
        assert m.armor_class and not m.armor_class.endswith(":")


@needs_db
def test_parse_real_mammal_compact_table(conn):
    """The Mammal page is a compact 'creature per row' summary table, not the
    standard label-per-row stat block."""
    ms = _parse_page(conn, "MM/DD03990.htm")
    names = [m.name for m in ms]
    assert len(ms) > 20
    assert any(n.startswith("Ape") for n in names) and any(n == "Badger" for n in names)
    ape = next(m for m in ms if m.name.startswith("Ape"))
    assert ape.armor_class == "6" and ape.hit_dice == "5" and ape.attack_bonus() == "5"
    assert all(m.name and m.armor_class for m in ms)     # no cross-reference junk rows


@needs_db
def test_importable_index_groups_families(conn):
    families, standalone = monster.importable_index(conn)
    by_name = {f[0]: f for f in families}
    assert "Dragon" in by_name and "Golem" in by_name and "Lycanthrope" in by_name
    _name, general_url, members = by_name["Dragon"]
    assert general_url is not None               # Dragon has a '-- General' lore page
    assert len(members) > 10                      # many dragon types under one entry
    assert any(n == "Ankheg" for _, n, _ in standalone)   # a lone monster stays standalone
    bear = next((c for u, n, c in standalone if n == "Bear"), None)
    assert bear and bear > 1                             # a multi-variant page carries its count


@needs_db
def test_importable_pages_excludes_category_pages(conn):
    urls = {u for u, _, _ in monster.importable_pages(conn)}
    assert "MM/DD03797.htm" in urls               # Ankheg — a real monster
    assert "MM/DD03794.htm" not in urls           # "The Monsters" (front matter)
    assert "MM/DD04100.htm" not in urls           # blank-form instructions
    assert len(urls) > 250


@needs_db
def test_every_mm_monster_page_parses_cleanly(conn):
    pages = db.list_monster_pages(conn)
    parsed = 0
    for page_url, title in pages:
        monsters = _parse_page(conn, page_url)
        if not monsters:
            assert page_url in CATEGORY_PAGES, f"unexpected empty parse: {page_url} ({title})"
            continue
        for m in monsters:
            assert m.name and m.armor_class, f"empty core field in {page_url}"
            assert not m.armor_class.endswith(":"), f"misaligned columns in {page_url}"
            m.attack_bonus(); m.ascending_ac(); m.initiative_modifier()   # must not raise
        parsed += 1
    assert parsed > 250                          # ~293 real monster pages

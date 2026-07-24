"""Tests for the monster model (monster.py) and its MM parser (monster_parser.py).

Pure tests build synthetic HTML stat blocks and always run; the DB-backed tests
parse the real Monstrous Manual pages and skip when dnd2e.db is absent (the
needs_db pattern from test_db.py).
"""
import os
import re

import pytest

import db
import char_rules as cr
import monster
import monster_parser
from monster import Monster
from monster_parser import parse_stat_block

RULES_DB = os.path.join(os.path.dirname(db.__file__), "dnd2e.db")
needs_db = pytest.mark.skipif(not os.path.exists(RULES_DB), reason="rulebook DB not present")

ANKHEG = "MM/DD03797.htm"       # single monster
BEAR = "MM/DD03805.htm"         # 4 variants, values on one line each
CAT_GREAT = "MM/DD03818.htm"    # 5 variants with wrapped names and values

LABELS = list(monster_parser.FIELD_BY_LABEL)   # canonical order


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
    rows = [(lab, [field_vals.get(monster_parser.FIELD_BY_LABEL[lab], "x")]) for lab in LABELS]
    return _html(rows)


# ── house-rule conversions (pure, no parsing) ─────────────────────────────────

def test_attack_bonus_is_the_base_value():
    assert Monster(thac0="19").attack_bonus() == "1"
    assert Monster(thac0="17-13").attack_bonus() == "3"     # base (first) THAC0, not a range
    assert Monster(thac0="1+1 and 2+2 HD: 19 3+3 HD: 17").attack_bonus() == "1"  # first HD: value
    assert Monster(thac0="45-49 hp: 11 50-59 hp: 9").attack_bonus() == "9"       # hp-conditional (Beholder)
    assert Monster(thac0="").attack_bonus() == ""
    assert Monster(thac0="Nil").attack_bonus() == ""


def test_house_rule_round_trips_guards_lossy_thaco_edits():
    """attack_bonus() reports one number, but the field it came from may hold a range
    or an HD-conditional list — writing the bonus back would replace the lot (and the
    tiers monster_tiers derives from it). Only a bare THAC0 may be edited as a bonus."""
    assert monster.house_rule_round_trips("thac0", "19")
    assert monster.house_rule_round_trips("thac0", " -1 ")
    assert not monster.house_rule_round_trips("thac0", "17-13")
    assert not monster.house_rule_round_trips("thac0", "3+3 HD: 17 4+4 HD: 15")
    assert not monster.house_rule_round_trips("thac0", "Nil")
    # AC is its own inverse — every number converts in place, so it always round-trips
    assert monster.house_rule_round_trips("armor_class", "Overall 2, underside 4")
    assert monster.house_rule_round_trips("climate_terrain", "Any land")


def test_clean_prose_reflows_wraps_and_collapses_blank_runs():
    from monster_parser import _clean_prose
    assert _clean_prose("The beast\nis fierce.") == "The beast is fierce."   # <br> wraps -> one line
    assert _clean_prose("Para one.\n\n\n\n\nPara two.") == "Para one.\n\nPara two."  # table gap -> one break
    assert _clean_prose("It eats meat.\nIndex") == "It eats meat."           # footer 'Index' dropped


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

def test_monster_name_prefixes_plain_groups_not_category_groups():
    from monster_parser import _monster_name
    assert _monster_name("Black", "Bear") == "Black Bear"           # plain group -> prefix base
    assert _monster_name("Phase", "Spider") == "Phase Spider"
    assert _monster_name("Death Kiss", "Beholder and Beholder-kin I") == "Death Kiss"  # category -> as-is
    assert _monster_name("Cheetah", "Cat, Great") == "Cheetah"
    assert _monster_name("Camel", "Mammal, Herd") == "Camel"
    assert _monster_name("Rat", "Rat") == "Rat"                     # no "Rat Rat" duplication
    assert _monster_name("", "Ankheg") == "Ankheg"                  # single monster


def test_resolve_name_applies_curated_overrides():
    from monster_parser import _resolve_name
    # _ALONE page: a full-name variant the rule would wrongly prefix
    assert _resolve_name("MM/DD03896.htm", "Djinni", "Genie") == "Djinni"
    # base-noun page: an adjective variant the rule would wrongly leave bare
    assert _resolve_name("MM/DD03957.htm", "Fire", "Imp, Mephit") == "Fire Mephit"
    assert _resolve_name("MM/DD03928.htm", "Stone", "Golem, Greater") == "Stone Golem"
    # mixed page: only the listed outlier is overridden; the rest fall through
    assert _resolve_name("MM/DD03803.htm", "Dracolisk", "Basilisk") == "Dracolisk"
    assert _resolve_name("MM/DD03803.htm", "Lesser", "Basilisk") == "Lesser Basilisk"
    # an un-curated page still uses the automatic rule
    assert _resolve_name("MM/DD03805.htm", "Black", "Bear") == "Black Bear"


def test_parses_a_single_monster_with_all_fields():
    html = _html([(lab, ["v_" + monster_parser.FIELD_BY_LABEL[lab]]) for lab in LABELS])
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


def test_dehyphenate_closes_soft_line_break_wraps():
    from monster_parser import _dehyphenate
    assert _dehyphenate("Ankylo- saurus") == "Ankylosaurus"    # hyphen + <br> wrap -> one word
    assert _dehyphenate("Amphis- baena") == "Amphisbaena"
    assert _dehyphenate("Beholder-kin") == "Beholder-kin"      # a real hyphen (no space) is kept


def test_trailing_age_progression_table_is_captured_not_bled_into_xp():
    # a dragon-shaped page: the stat block, then an age-progression table (its own
    # <TABLE>, as in the real MM) with a two-row header. Phase A *captures* it as an
    # ``age`` extra while still keeping it out of the last stat value (XP VALUE) —
    # the no-contamination half of the old "Variable Body" bug.
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["2"]),
            ("SIZE", ["G"]), ("XP VALUE", ["Variable"])]
    html = _html(rows).replace(
        "</TABLE>",
        "</TABLE><TABLE>"
        "<TR><TD></TD><TD>Body</TD><TD>Tail</TD><TD>Breath</TD></TR>"
        "<TR><TD>Age</TD><TD>1-12</TD><TD>3-12</TD><TD>2d10</TD></TR></TABLE>")
    (m,) = parse_stat_block(html, title="Dragon (Monstrous Manual)")
    assert m.xp_value == "Variable"                 # not "Variable Body" — no contamination
    (age,) = [t for t in m.extra_tables if t["kind"] == "age"]  # now captured, not dropped
    assert age["header_rows"] == 2
    assert any("Body" in c for row in age["rows"] for c in row)


def test_trailing_subtable_inside_the_stat_block_table_still_ignored():
    # the same-<TABLE> guard: a sub-table crammed into the stat block's own <TABLE>
    # (the 'Wyrm' data row ends the block; wrapped continuations follow) can't be
    # captured at the table level, so it must still be ignored — never bleeding onto
    # XP VALUE.
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["2"]), ("XP VALUE", ["Variable"])]
    html = _html(rows).replace(
        "</TABLE>",
        "<TR><TD>Age</TD><TD>Ability</TD></TR>"
        "<TR><TD>Wyrm</TD><TD>repulsion 3</TD></TR>"
        "<TR><TD></TD><TD>times/day</TD></TR></TABLE>")
    (m,) = parse_stat_block(html, title="Dragon (Monstrous Manual)")
    assert m.xp_value == "Variable"
    assert m.extra_tables == []                     # nothing trailing the stat block's table


def test_classifier_recognizes_the_three_known_shapes():
    from monster_parser import _classify_table
    age = _classify_table([
        ["", "Body", "Tail", "", "Breath", "Spells", "", "Treas.", "XP"],
        ["Age", "Lgt. (')", "Lgt. (')", "AC", "Weapon", "Wizard/Priest", "MR", "Type", "Value"],
        ["1", "3-6", "2-5", "4", "2d4+1", "Nil", "Nil", "Nil", "4,000"]])
    assert age["kind"] == "age" and age["header_rows"] == 2

    psi = _classify_table([
        ["Level", "Dis/Sci/Dev", "Attack/Defense", "Power Score", "PSPs"],
        ["8", "3/5/16", "TS,IF,TW", "= Int", "250"]])
    assert psi["kind"] == "psionics" and psi["header_rows"] == 1

    # a psionics header wrapped onto two rows (Couatl / Ki-rin shape)
    psi2 = _classify_table([
        ["Level", "Dis/Sci", "Attack/", "Power", "PSPs"],
        ["", "Dev", "Defense", "Score", ""],
        ["9", "4/5/18", "Any/All", "= Int", "200"]])
    assert psi2["kind"] == "psionics" and psi2["header_rows"] == 2

    dmg = _classify_table([["Attack", "Damage", "Attack", "Damage"],
                           ["acid", "full", "cold", "half*"]])
    assert dmg["kind"] == "attack_damage"


def test_classifier_normalizes_and_keeps_unknown_tables_as_other():
    from monster_parser import _classify_table
    # a leading spacer column present in every row is folded away
    hit = _classify_table([["", "Roll", "Location", "AC"],
                           ["", "01-75", "Body", "0"]])
    assert hit["kind"] == "other"
    assert hit["rows"][0] == ["Roll", "Location", "AC"]      # spacer column dropped
    # an age→lore table (no combat columns) is not mistaken for age progression
    notes = _classify_table([["Age", "Ability"], ["Wyrm", "repulsion 3/day"]])
    assert notes["kind"] == "other"
    assert _classify_table([["", ""]]) is None              # a wholly blank table


def test_compact_table_filters_spell_and_psionics_junk_rows():
    from monster_parser import _parse_compact_table
    rows = [["Bird", "AC", "HD", "THAC0"],
            ["Blood Hawk", "7", "1+1", "19"],           # a real creature
            ["Roll", "Spell", "Roll", "Spell"],         # a spell-table header (no digit in HD col)
            ["1", "Audible glamer", "5", "Hypnotic"]]   # a spell row (name has no letter)
    ms = _parse_compact_table(rows, "MM/DDbird.htm")
    assert [m.name for m in ms] == ["Blood Hawk"]


def test_compact_table_stitches_wrapped_name_but_not_a_caste_header():
    from monster_parser import _parse_compact_table
    rows = [["Fish", "AC", "HD", "THAC0"],
            ["Catfish,", "7", "7 to 10", "13"],   # a creature whose name wrapped...
            ["Giant", "", "", ""],                # ...its second line, right after the stat row
            ["Praying", "5", "2 to 12", "19"],    # another creature
            ["", "", "", "8 HD: 13"],             # an HD-conditional tail row
            ["Termite", "", "", ""],              # a caste header — NOT a wrapped name
            ["King", "5", "6+6", "15"]]           # the caste's own stat row
    ms = _parse_compact_table(rows, "MM/DDfish.htm")
    assert [m.name for m in ms] == ["Catfish, Giant", "Praying", "King"]


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


def test_splits_prose_on_ocr_habitat_society_variants():
    from monster_parser import _split_prose
    # "Habit/Society" (Blue Dragon), "Society/Habitat" and "Habitat Society" are OCR
    # variants; each must still route to habitat_society, not bleed into Combat.
    for header in ("Habit/Society:", "Society/Habitat:", "Habitat Society:"):
        desc, combat, habitat, ecology = _split_prose(
            f"A dragon.\nCombat:\nIt bites.\n{header}\nIt nests in caves.\nEcology:\nIt eats sheep.")
        assert combat == "It bites."
        assert habitat == "It nests in caves.", header      # not absorbed into Combat
        assert ecology == "It eats sheep."


def _variant_html(variants, base_sections, blocks):
    """A multi-variant page: a stat table, then ``base_sections`` prose, then a bold
    sub-header + block per entry in ``blocks`` (list of (header, text))."""
    rows = [("CLIMATE/TERRAIN", ["x"] * len(variants)),
            ("ARMOR CLASS", ["5"] * len(variants)), ("SIZE", ["M"] * len(variants))]
    prose = base_sections + "".join(f"<P><B>{h}</B> {t}" for h, t in blocks)
    return _html(rows, variants=variants, prose=prose)


def test_variant_prose_splits_a_base_creature_from_its_kin():
    # base creature (Ogre) owns the leading Combat/Ecology; the kin block stands alone
    html = _variant_html(
        ["Ogre", "Merrow"],
        "<P>Ogres are big.<P>Combat:<BR>Ogres club foes.<P>Ecology:<BR>Ogres eat lots.",
        [("Merrow", "Merrow are aquatic ogres that cast fireball once per day.")])
    ms = parse_stat_block(html, title="Ogre (Monstrous Manual)")
    ogre = next(m for m in ms if m.name == "Ogre")
    merrow = next(m for m in ms if "Merrow" in m.name)
    assert ogre.combat == "Ogres club foes." and ogre.ecology == "Ogres eat lots."
    assert "Merrow are aquatic" in merrow.description   # its own one-paragraph block -> Description
    assert "club foes" not in merrow.description        # not the base creature's text
    assert merrow.combat == ""                          # a kin paragraph has no Combat section


def test_variant_prose_shares_general_sections_when_no_base_creature():
    # every column has a header -> the leading sections are general and inherited
    html = _variant_html(
        ["Guardian Naga", "Spirit Naga"],
        "<P>Combat:<BR>Nagas bite.<P>Habitat/Society:<BR>Nagas live alone.",
        [("Guardian Naga", "Guardian nagas are good."),
         ("Spirit Naga", "Spirit nagas are evil.")])
    ms = parse_stat_block(html, title="Naga (Monstrous Manual)")
    for m in ms:
        assert m.habitat_society == "Nagas live alone."     # shared section inherited by both
        assert m.combat == "Nagas bite."                    # shared combat inherited
    guardian = next(m for m in ms if m.name == "Guardian Naga")
    assert "Guardian nagas are good." in guardian.description   # its own specifics -> Description


def test_variant_prose_header_matches_most_specific_variant():
    # "Lamia Noble" heads the Noble column, not the base "Lamia" (a prefix of it)
    html = _variant_html(
        ["Lamia", "Lamia Noble"],
        "<P>Combat:<BR>Lamiae drain wisdom.<P>Ecology:<BR>They haunt ruins.",
        [("Lamia Noble", "Lamia nobles are spellcasters.")])
    ms = parse_stat_block(html, title="Lamia (Monstrous Manual)")
    lamia = next(m for m in ms if m.name == "Lamia")
    noble = next(m for m in ms if m.name == "Lamia Noble")
    assert lamia.combat == "Lamiae drain wisdom."       # base keeps the shared sections
    assert lamia.ecology == "They haunt ruins."
    assert "spellcasters" in noble.description           # noble gets its own block


def test_variant_prose_header_matches_a_reordered_or_run_together_name():
    """The MM's stat columns are index entries ('Rat (Giant)', 'Jelly, Stun-') while
    its prose sub-headers read naturally ('Giant Rats', 'Stunjelly'). Same creature —
    so the header must find its column, not be filed as a prose-only creature."""
    from monster_parser import _same_words
    assert _same_words("Giant Rats", "Rat (Giant)")
    assert _same_words("Stunjelly", "Jelly, Stun-")
    assert _same_words("Greenhag", "Green Hag")
    assert _same_words("Megalo- centipede", "Megalocentipede")
    assert _same_words("The Gorgimera", "Gorgimera")
    assert not _same_words("Giant Rats", "Brush Rat")        # different words
    assert not _same_words("Undead Beholder", "Beholder")    # a subset is not the same name

    html = _variant_html(
        ["Chimera", "Gorgimera"],
        "<P>Combat:<BR>It breathes fire.",
        [("The Gorgimera", "The gorgimera has a snake tail.")])
    ms = parse_stat_block(html, title="Chimera (Monstrous Manual)")
    gorgimera = next(m for m in ms if m.variant == "Gorgimera")
    assert "snake tail" in gorgimera.description
    assert ms[0].related_creatures == []          # not a prose-only creature — it has a column


def test_a_bolded_sentence_fragment_is_not_a_prose_only_creature():
    """Creature names are title case in this book; a trailing lowercase word marks a
    bolded caption ('Dodge missiles', 'Rrakkma bands') that must not bound the prose."""
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["5"])]
    prose = ("<P>A thri-kreen.<P><B>Combat:</B><BR>It leaps."
             "<P><B>Dodge missiles:</B> it can swat arrows aside."
             "<P><B>Black Cloud of Vengeance:</B> a real creature, capitalized.")
    (m,) = parse_stat_block(_html(rows, prose=prose), title="Thri-kreen (Monstrous Manual)")
    assert [r["name"] for r in m.related_creatures] == ["Black Cloud of Vengeance"]
    assert "swat arrows aside" in m.combat        # the caption stayed with its section


def test_prose_only_creature_is_captured_not_merged_into_the_parent():
    # the Archlich shape: a creature described in prose with no stat column of its own
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["5"]), ("SIZE", ["M"])]
    prose = ("<P>A lich is undead.<P><B>Combat:</B><BR>It paralyzes."
             "<P><B>Habitat/Society:</B><BR>It broods."
             "<P><B>Archlich:</B> A rare good-aligned lich.")
    (m,) = parse_stat_block(_html(rows, prose=prose), title="Lich (Monstrous Manual)")
    assert m.combat == "It paralyzes." and m.habitat_society == "It broods."
    assert "Archlich" not in m.habitat_society           # never bleeds into the parent
    assert [r["name"] for r in m.related_creatures] == ["Archlich"]
    assert "good-aligned lich" in m.related_creatures[0]["text"]


def test_captions_ages_and_spell_names_are_not_prose_only_creatures():
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["5"])]
    prose = ("<P>A dragon.<P><B>Combat:</B><BR>It bites."
             "<P><B>Venerable:</B> old and wise."                  # a dragon age tier
             "<P><B>Telepathy - Sciences:</B> mind link."          # a psionic discipline
             "<P><B>Alignment:</B> lawful."                        # a table legend
             "<P><B>Create Crypt Thing:</B> a spell.")             # a spell name
    (m,) = parse_stat_block(_html(rows, prose=prose), title="Foo (Monstrous Manual)")
    assert m.related_creatures == []


def test_inline_bold_emphasis_is_not_a_prose_only_creature():
    rows = [("CLIMATE/TERRAIN", ["Any"]), ("ARMOR CLASS", ["5"])]
    prose = ("<P>The <B>Mummies</B> of the desert are feared."
             "<P><B>Habitat/Society:</B><BR>They haunt tombs.")
    (m,) = parse_stat_block(_html(rows, prose=prose), title="Mummy (Monstrous Manual)")
    assert m.related_creatures == []                    # mid-sentence emphasis, not a header
    assert m.habitat_society == "They haunt tombs."     # and it can't cut the prose in half


def test_prose_only_block_does_not_swallow_trailing_shared_sections():
    # the Slaad shape: prose-only blurbs, then Habitat/Ecology shared by every variant
    rows = [("CLIMATE/TERRAIN", ["Any", "Any"]), ("ARMOR CLASS", ["5", "6"]),
            ("SIZE", ["M", "M"])]
    prose = ("<P><B>Red Slaad:</B> red ones.<P><B>Blue Slaad:</B> blue ones."
             "<P><B>Death Slaad:</B> the greatest."
             "<P><B>Habitat/Society:</B><BR>Slaadi roam Limbo.<P><B>Ecology:</B><BR>They breed.")
    ms = parse_stat_block(_html(rows, variants=("Red Slaad", "Blue Slaad"), prose=prose),
                          title="Slaad (Monstrous Manual)")
    for m in ms:
        assert m.habitat_society == "Slaadi roam Limbo."   # shared, not eaten by Death Slaad
        assert m.ecology == "They breed."
    assert [r["name"] for r in ms[0].related_creatures] == ["Death Slaad"]
    assert "Limbo" not in ms[0].related_creatures[0]["text"]


def test_non_monster_page_yields_nothing():
    assert parse_stat_block("<HTML><BODY><TABLE><TR><TD>Contents</TD></TR></TABLE></BODY></HTML>") == []
    assert parse_stat_block("") == []


def test_to_dict_from_dict_roundtrip():
    (m,) = parse_stat_block(_full(thac0="17", armor_class="4", size="L"),
                            title="Beast (Monstrous Manual)")
    assert Monster.from_dict(m.to_dict()) == m
    Monster.from_dict({"name": "X", "bogus": 1})   # tolerates unknown keys


def test_extra_tables_survive_a_dict_roundtrip():
    m = Monster(name="Dragon", extra_tables=[
        {"kind": "age", "header_rows": 2, "rows": [["Age", "AC"], ["1", "4"]]}])
    back = Monster.from_dict(m.to_dict())
    assert back == m
    assert back.extra_tables[0]["kind"] == "age"


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
    assert "\n\n\n" not in m.combat                   # prose reflowed, no blank-line runs
    assert m.image == "ANKHEG.gif"                    # the page's illustration filename


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
def test_every_compact_table_header_is_understood(conn):
    """No compact summary grid may carry a column this parser silently drops.

    `_COMPACT_HEADERS` is a hand-maintained list of the MM's abbreviations, and the
    MM is not consistent: the Insect, Mammal and Fish grids write "# OF ATT" /
    "DMG/ATT" while the Bird grid writes "# AT" / "DMG/AT". The short pair was
    missing, so all 18 creatures on the Bird page imported with no attacks and no
    damage and exported to Roll20 with zero weapon rows -- the entire content of a
    monster sheet, gone, with nothing to notice.

    Sweeping every MM page for unmapped header cells catches that class of bug on
    the day a page is first parsed, rather than one creature at a time.
    """
    unmapped = {}
    for row in db.list_monster_pages(conn):
        page = db.get_page(conn, row["page_url"])
        for table in _creature_grids(conn, page, row["page_url"]):
            for key in _header_keys(table):
                if key and key not in monster_parser._COMPACT_HEADERS:
                    unmapped.setdefault(key, []).append(row["page_url"])
    assert unmapped == {}, (
        "compact-table headers no field maps to: "
        + ", ".join(f"{k!r} ({v[0]})" for k, v in sorted(unmapped.items()))
    )


def _header_keys(table) -> list:
    """The header row's columns, normalised the way _parse_compact_table keys them."""
    return [" ".join(c.strip().rstrip(".").upper().split()) for c in table[0][1:]]


def _creature_grids(conn, page, page_url) -> list:
    """The compact *creature* grids on a page — the tables that list one monster per
    row, as the Bird/Insect/Mammal/Fish pages do.

    Deliberately narrower than "any table with an AC column", because two other
    kinds of table have one and neither is a creature list:

      * **age progression tables** (the dragons, the Greater Mummy) — the parser
        classifies these as ``kind: "age"`` and monster_tiers turns them into
        selectable tiers, so their columns are read elsewhere;
      * **hit-location tables** (the Beholder's "Roll / Location / AC") — these have
        an empty first header cell, where a creature grid names its subject ("Bird").

    Matching the parser's own classification keeps this test about the thing it is
    meant to guard rather than about every table in the Monstrous Manual.
    """
    parser = monster_parser._StatBlockHTML()
    parser.feed(page["content_html"])
    out = []
    for table in parser.tables:
        if not table or len(table) < 3:
            continue
        if not any(k in ("AC", "ARMOR CLASS") for k in _header_keys(table)):
            continue
        if monster_parser._is_age_table(table):
            continue
        if not (table[0] and table[0][0].strip()):
            continue                     # hit-location table, not a creature grid
        out.append(table)
    return out


@needs_db
def test_compact_grids_yield_usable_stat_blocks(conn):
    """Every creature from a compact grid carries the fields a DM needs to run it.

    The Bird regression showed up here as empty attack/damage on 18 creatures. Size,
    alignment and the rest are deliberately *not* asserted: the MM's summary grids
    genuinely do not print those columns, so their absence is the source data rather
    than a parse failure.
    """
    missing = []
    for row in db.list_monster_pages(conn):
        page = db.get_page(conn, row["page_url"])
        monsters = parse_stat_block(page["content_html"], page["title"], row["page_url"])
        if len(monsters) < 6:
            continue                                  # not one of the compact grids
        for m in monsters:
            if not (m.damage_attack or "").strip() or not (m.no_of_attacks or "").strip():
                missing.append(f"{row['page_url']}:{m.name}")
    assert missing == [], f"compact-grid creatures with no attack line: {missing[:10]}"


@needs_db
def test_bird_page_creatures_carry_their_attacks(conn):
    """The specific regression, named. MM/DD03810 is the grid that abbreviates to
    "# AT" / "DMG/AT"."""
    ms = _parse_page(conn, "MM/DD03810.htm")
    assert len(ms) == 18
    hawk = next(m for m in ms if m.name == "Blood Hawk")
    assert hawk.no_of_attacks == "3"
    assert hawk.damage_attack == "1-4/1-4/1-6"


@needs_db
def test_importable_index_groups_families(conn):
    families, standalone = monster_parser.importable_index(conn)
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
    urls = {u for u, _, _ in monster_parser.importable_pages(conn)}
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


def _identity(name: str):
    """A name's fuzzy identity — its words, de-pluralized, order-and-spacing blind.
    Deliberately *not* built on _header_score, so this checks the matcher's result
    rather than restating its rules."""
    words = []
    for w in monster_parser._norm_header(name).split():
        if w in ("the", "a", "an", "of", "and"):
            continue
        words.append(w[:-1] if len(w) >= 4 and w.endswith("s") and not w.endswith("ss") else w)
    return "".join(sorted(words))


@needs_db
def test_no_prose_only_creature_duplicates_a_real_stat_variant(conn):
    """A page's 'Also Described on This Page' blurbs must name creatures the page has
    *no* stat column for. When the prose sub-header and the stat column spell the same
    creature differently ('Giant Constrictor Snake' vs the column's 'Constrictor
    (Giant)'), the matcher used to score 0 — so the variant's own prose was captured as
    a blurb and the variant itself was left with the page's generic text."""
    for page_url, _title in db.list_monster_pages(conn):
        monsters = _parse_page(conn, page_url)
        if not monsters:
            continue
        real = {_identity(m.name) for m in monsters} | {
            _identity(m.variant) for m in monsters if m.variant}
        for rel in (monsters[0].related_creatures or []):
            assert _identity(rel["name"]) not in real, (
                f"{page_url}: prose for the stat variant {rel['name']!r} was diverted "
                f"into related_creatures")


# ── Phase A: enrichment tables captured past the stat block (DB-backed) ────────

@needs_db
def test_real_black_dragon_captures_its_age_progression(conn):
    (m,) = _parse_page(conn, "MM/DD03843.htm")   # Dragon, Chromatic: Black Dragon
    assert m.armor_class == "1 (base)" and m.xp_value == "Variable"   # stat block unchanged
    (age,) = [t for t in m.extra_tables if t["kind"] == "age"]
    assert age["header_rows"] == 2
    header = " ".join(c for row in age["rows"][:2] for c in row)
    assert "Breath" in header and "XP" in header                # the columns Phase B consumes
    assert any(row[0].strip() == "12" for row in age["rows"])   # the Great Wyrm age row


@needs_db
def test_real_aboleth_captures_its_psionics_summary(conn):
    (m,) = _parse_page(conn, "MM/DD03796.htm")   # Aboleth
    (psi,) = [t for t in m.extra_tables if t["kind"] == "psionics"]
    header = " ".join(psi["rows"][0])
    assert "Level" in header and "PSPs" in header


@needs_db
def test_real_baatezu_captures_per_attack_damage_on_every_variant(conn):
    ms = _parse_page(conn, "MM/DD03801.htm")     # Baatezu — 4 variants + an Attack|Damage table
    assert len(ms) >= 2
    for m in ms:                                  # the page's table is attached to each variant
        assert any(t["kind"] == "attack_damage" for t in m.extra_tables)


@needs_db
def test_plain_monster_has_no_extra_tables(conn):
    (m,) = _parse_page(conn, ANKHEG)             # a single, table-free stat block
    assert m.extra_tables == []


# ── Phase B: HD / age scaling tiers (DB-backed) ───────────────────────────────

@needs_db
def test_real_black_dragon_age_tiers_scale_ac_and_xp(conn):
    import monster_tiers as mt
    (m,) = _parse_page(conn, "MM/DD03843.htm")   # Black Dragon: a 12-step age table
    ts = mt.tiers(m)
    assert len(ts) == 12 and ts[0].label == "Age 1"
    m.selected_tier = 11                          # the oldest (Great Wyrm)
    scaled = mt.active_monster(m)
    assert scaled.armor_class == "-7" and scaled.ascending_ac() == "27"
    assert scaled.xp_value == "20,000"
    assert m.armor_class == "1 (base)"            # base untouched


@needs_db
def test_real_hd_conditional_monster_scales_attack_bonus(conn):
    import monster_tiers as mt
    (m,) = _parse_page(conn, "MM/DD03799.htm")   # Argos: THAC0 "5-6 HD: 15 7-8 HD: 13 9-10 HD: 11"
    ts = mt.tiers(m)
    assert [t.label for t in ts] == ["5-6 HD", "7-8 HD", "9-10 HD"]
    m.selected_tier = 2                           # 9-10 HD: THAC0 11 -> attack bonus 9
    scaled = mt.active_monster(m)
    assert scaled.thac0 == "11" and scaled.attack_bonus() == "9"
    assert scaled.hit_dice == "9-10"


@needs_db
def test_real_blue_dragon_habitat_society_is_populated(conn):
    # regression: the Blue Dragon page spells the header "Habit/Society", which the
    # prose splitter used to miss — leaving habitat_society empty and the section
    # swallowed into Combat.
    (m,) = _parse_page(conn, "MM/DD03844.htm")
    assert "deserts" in m.habitat_society.lower()


_HABITAT_HEADER = re.compile(
    r"^\s*(habitat/society|habit/society|society/habitat|habitat society)\s*:", re.I)


@needs_db
def test_habitat_society_parsed_when_the_page_has_that_section(conn):
    """Guard against a header spelling slipping past the prose splitter: any page whose
    text carries a Habitat/Society header (in any of its spellings) must parse to a
    non-empty habitat_society for at least one creature. Catches the Blue Dragon
    'Habit/Society' class of bug. (Per-variant splitting means a *kin* creature written
    as one flowing paragraph legitimately has no habitat section of its own, so the
    invariant is per page, not per variant.)"""
    missing = []
    for page_url, title in db.list_monster_pages(conn):
        text = conn.execute(
            "SELECT content_text FROM pages WHERE page_url = ?", (page_url,)).fetchone()[0] or ""
        if not any(_HABITAT_HEADER.match(line) for line in text.splitlines()):
            continue
        monsters = _parse_page(conn, page_url)
        if monsters and not any(m.habitat_society.strip() for m in monsters):
            missing.append(f"{title} ({page_url})")
    assert not missing, f"no creature got habitat_society despite a header on: {missing}"

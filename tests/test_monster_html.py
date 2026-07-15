"""Tests for monster_html.py — the DM monster sheet view (pure HTML render)."""
import monster_html
from monster import Monster
from monster_html import _to_dice


def _ankheg() -> Monster:
    return Monster(
        name="Ankheg", source_page="MM/DD03797.htm",
        climate_terrain="Temperate/Plains", armor_class="Overall 2, underside 4",
        thac0="17-13", hit_dice="3-8", no_of_attacks="1",
        damage_attack="3-18 (crush)+1-4 (acid)", special_attacks="Squirt acid", size="L-H",
        description="A burrowing monster.", combat="It squirts acid to 30 feet.",
        habitat_society="Solitary broods.", ecology="Eats fresh meat.",
    )


def test_to_dice_converts_ranges():
    assert _to_dice("3-18 (crush)+1-4 (acid)") == "3d6 (crush)+d4 (acid)"
    assert _to_dice("1-6/1-6") == "d6/d6"          # single die drops the count
    assert _to_dice("2-8 (bite)/2-12 per leg") == "2d4 (bite)/2d6 per leg"
    assert _to_dice("2-5") == "2-5"                # doesn't divide -> left alone
    assert _to_dice("Nil") == "Nil"


def test_renders_name_and_source_link():
    h = monster_html.generate(_ankheg())
    assert "Ankheg" in h
    assert 'dnd:///MM/DD03797.htm' in h          # back-link to the MM page


def test_shows_house_rule_values():
    h = monster_html.generate(_ankheg())
    # attack bonus is the base value (THAC0 17-13 -> base 17 -> +3), ascending AC, init
    assert ">3<" in h                            # base attack bonus tile, not a range
    assert "3-7" not in h                        # the old cluttered range is gone
    assert "Overall 18, underside 16" in h       # AC converted in place
    assert "+9" in h                             # size L-H -> Huge initiative


def test_only_house_rule_ac_and_thaco_shown():
    h = monster_html.generate(_ankheg())
    assert "17-13" not in h                       # raw THAC0 not shown
    assert "Overall 2," not in h                  # raw descending AC not shown
    assert "Attack Bonus" in h                    # THAC0 row relabeled


def test_damage_shown_as_dice():
    h = monster_html.generate(_ankheg())
    assert "3d6" in h and "d4" in h
    assert "3-18" not in h                         # the range form is gone


def test_stat_fields_are_editable_hooks():
    h = monster_html.generate(_ankheg())
    assert "set/armor_class" in h and "set/thac0" in h and "set/size" in h
    assert "set/name" in h
    assert "function monText" in h               # the dnd:///mon/ interaction helper


def test_combat_is_a_feature_panel():
    h = monster_html.generate(_ankheg())
    assert "It squirts acid to 30 feet." in h
    assert "panel feature" in h                  # Combat rendered as first-class text
    assert "set/combat" in h


def test_actions_and_save_label():
    saved = monster_html.generate(_ankheg(), saved_id=5)
    assert "Save changes" in saved
    fresh = monster_html.generate(_ankheg())
    assert "Save monster" in fresh
    assert "dnd:///mon/import" in fresh and "dnd:///mon/new" in fresh


def test_html_is_escaped():
    m = Monster(name="Gnoll <b>& Flind", combat="save vs. death & <die>")
    h = monster_html.generate(m)
    assert "&lt;b&gt;" in h and "&amp;" in h
    assert "<b>&" not in h                        # the raw tag never leaks through


def test_variant_tag_only_when_present():
    assert '"tag"' in monster_html.generate(Monster(name="Black Bear", variant="Black"))
    assert '"tag"' not in monster_html.generate(Monster(name="Ankheg"))


def test_empty_monster_does_not_crash():
    h = monster_html.generate(Monster())
    assert "<!DOCTYPE html>" in h and "Stat Block" in h
    assert "—" in h                              # empty derived tiles show a dash


def test_import_picker_lists_families_and_standalone():
    families = [("Dragon", "MM/DD03842.htm",
                 [("MM/DDred.htm", "Red", 1), ("MM/DDblu.htm", "Blue", 1)])]
    standalone = [("MM/DD03797.htm", "Ankheg", 1), ("MM/DD03805.htm", "Bear", 4)]
    h = monster_html.generate_import_picker(
        families, standalone, saved=[(1, "My Goblin", "MM/DD03940.htm")])
    assert 'href="dnd:///mon/family/Dragon"' in h and ">2<" in h    # family entry + member count
    assert "dnd:///mon/pick/MM/DD03797.htm" in h and "Ankheg" in h  # standalone imports directly
    assert ">4<" in h                                              # a multi-creature page shows its count
    assert "My Goblin" in h and "dnd:///mon/load/1" in h           # saved section
    assert "function filt" in h                                    # client-side search filter


def test_family_picker_lists_members_and_general_link():
    h = monster_html.generate_family_picker(
        "Dragon", "MM/DD03842.htm",
        [("MM/DDred.htm", "Red Dragon", 1), ("MM/DDage.htm", "Age Tiers", 6)])
    assert "Red Dragon" in h and "dnd:///mon/pick/MM/DDred.htm" in h
    assert ">6<" in h                                              # a multi-creature member shows its count
    assert "General information" in h and 'href="dnd:///MM/DD03842.htm"' in h  # lore -> reader


def test_family_picker_omits_general_when_absent():
    h = monster_html.generate_family_picker("Giant", None, [("MM/DDf.htm", "Fire", 1)])
    assert "Fire" in h and "General information" not in h


def test_family_picker_groups_colon_subcategories():
    members = [("MM/1.htm", "Chromatic: Black Dragon", 1),
               ("MM/2.htm", "Chromatic: Red Dragon", 1),
               ("MM/3.htm", "Brown", 1)]
    h = monster_html.generate_family_picker("Dragon", None, members)
    assert 'class="subcat-h">Chromatic<' in h
    assert "Black Dragon" in h and "Red Dragon" in h    # shown by the text after the colon
    assert "Brown" in h                                 # a loose member with no subcategory


def test_variant_picker_groups_comma_subcategories_keeping_indices():
    names = ["Eel, Electric", "Eel, Giant", "Barracuda"]
    h = monster_html.generate_variant_picker("Fish", "MM/DDf.htm", names)
    assert 'class="subcat-h">Eel<' in h and "Electric" in h and "Giant" in h
    assert "Barracuda" in h                             # loose
    assert "dnd:///mon/pickvar/MM/DDf.htm/0" in h        # subcategorized items keep their index
    assert "dnd:///mon/pickvar/MM/DDf.htm/2" in h


def test_variant_picker_lists_indexed_choices():
    h = monster_html.generate_variant_picker(
        "Bear", "MM/DD03805.htm", ["Black Bear", "Polar Bear"])
    assert "Black Bear" in h and "Polar Bear" in h
    assert "dnd:///mon/pickvar/MM/DD03805.htm/0" in h
    assert "dnd:///mon/pickvar/MM/DD03805.htm/1" in h

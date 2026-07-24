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


def test_only_house_rule_ac_shown():
    h = monster_html.generate(_ankheg())
    assert "Overall 2," not in h                  # raw descending AC not shown
    assert "Overall 18, underside 16" in h        # every number converted in place


def test_plain_thaco_is_shown_and_edited_as_an_attack_bonus():
    m = _ankheg()
    m.thac0 = "17"                                # a bare number round-trips
    h = monster_html.generate(m)
    assert "Attack Bonus" in h and "set/thac0" in h
    assert 'value="3"' in h and ">17<" not in h


def test_a_thaco_that_cannot_round_trip_stays_raw_and_read_only():
    """A ranged or HD-conditional THAC0 has no single attack bonus, so the sheet shows
    what the MM wrote — read-only, with the derived base bonus as a badge. Editing it
    would write one number over the whole field (and over the tiers derived from it)."""
    h = monster_html.generate(_ankheg())          # THAC0 "17-13"
    assert 'value="17-13" readonly' in h          # the source text, intact
    assert "set/thac0" not in h                   # and no way to overwrite it
    assert "Atk +3" in h                          # the derived base bonus, as a badge

    m = _ankheg()
    m.thac0 = "3+3 HD: 17 4+4 HD: 15"             # the conditional form tiers read
    h = monster_html.generate(m)
    assert 'value="3+3 HD: 17 4+4 HD: 15" readonly' in h and "set/thac0" not in h


def test_damage_shown_as_dice():
    h = monster_html.generate(_ankheg())
    assert "3d6" in h and "d4" in h
    assert "3-18" not in h                         # the range form is gone


def test_initiative_override_control_is_editable():
    h = monster_html.generate(_ankheg())               # size L-H -> Huge, init +9
    assert 'class="init-ov"' in h and "monText('init'" in h
    assert 'value="9"' in h                             # the size-derived factor, editable
    m = _ankheg()
    m.initiative_override = 1
    assert 'class="init-ov" value="1"' in monster_html.generate(m)   # the override shows


def test_stat_fields_are_editable_hooks():
    h = monster_html.generate(_ankheg())
    assert "set/armor_class" in h and "set/size" in h
    assert "function monText" in h               # the dnd:///mon/ interaction helper
    assert "set/name" in monster_html.generate(Monster())   # a custom monster's name is editable


def test_imported_name_is_a_link_to_the_mm_page():
    h = monster_html.generate(_ankheg())         # has a source_page
    assert 'class="namelink"' in h and 'href="dnd:///MM/DD03797.htm"' in h
    assert "set/name" not in h                   # the imported name is a link, not an input


def test_imported_monster_hides_empty_prose_panels():
    m = Monster(name="Bird", source_page="MM/DDbird.htm",
                description="A small owl that hunts at night.")   # no combat/habitat/ecology
    h = monster_html.generate(m)
    assert "Description" in h and "hunts at night" in h
    assert ">Habitat / Society<" not in h and ">Ecology<" not in h   # empty panels hidden
    assert "set/habitat_society" not in h


def test_custom_monster_keeps_all_prose_panels_to_fill_in():
    m = Monster(name="My Homebrew")                                  # no source_page -> custom
    h = monster_html.generate(m)
    for field in ("set/description", "set/combat", "set/habitat_society", "set/ecology"):
        assert field in h                                           # every panel editable


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
    assert "dnd:///mon/roll20" in fresh                 # Export to Roll20 button


def test_html_is_escaped():
    m = Monster(name="Gnoll <b>& Flind", combat="save vs. death & <die>")
    h = monster_html.generate(m)
    assert "&lt;b&gt;" in h and "&amp;" in h
    assert "<b>&" not in h                        # the raw tag never leaks through


def test_empty_monster_does_not_crash():
    h = monster_html.generate(Monster())
    assert "<!DOCTYPE html>" in h and "Stat Block" in h
    assert "—" in h                              # empty derived tiles show a dash


def test_no_extra_tables_section_when_none():
    h = monster_html.generate(_ankheg())
    assert "Additional Tables" not in h and 'class="extras"' not in h


def test_renders_captured_extra_tables():
    m = _ankheg()
    m.extra_tables = [
        {"kind": "age", "header_rows": 2,
         "rows": [["Age", "AC", "Breath"], ["1", "4", "2d4+1"], ["12", "-4", "24d4+12"]]},
        {"kind": "attack_damage", "header_rows": 1,
         "rows": [["Attack", "Damage"], ["acid", "full"]]},
    ]
    h = monster_html.generate(m)
    assert "Additional Tables" in h
    assert "Age Progression" in h and "Attack Damage" in h
    assert "<th>Age</th>" in h                                # the two header rows are <th>
    assert "<td>24d4+12</td>" in h                            # the data row is <td>
    assert 'data-kind="age"' in h


def test_extra_table_cells_are_escaped():
    m = _ankheg()
    m.extra_tables = [{"kind": "other", "header_rows": 1,
                       "rows": [["Roll", "Effect"], ["1", "save vs. <death> & die"]]}]
    h = monster_html.generate(m)
    assert "&lt;death&gt;" in h and "&amp;" in h
    assert "<death>" not in h


def _mummy_age_table():
    return {"kind": "age", "header_rows": 1, "rows": [
        ["Age", "AC", "HD", "THAC0"],
        ["99 or less", "2", "8+3", "11"],
        ["500 or more", "-3", "13+3", "7"]]}


def test_combat_chips_render_abilities_and_saves():
    m = _ankheg()
    m.combat = "Its gaze turns foes to stone; save vs. petrification or be paralyzed."
    h = monster_html.generate(m)
    assert 'class="chips"' in h
    assert '<span class="chip">Gaze attack</span>' in h
    assert '<span class="chip">Petrification</span>' in h
    assert '<span class="chip save">Save vs. Petrification</span>' in h


def test_no_chips_row_when_prose_surfaces_nothing():
    m = _ankheg()
    m.combat = "It swings a big club at people."
    h = monster_html.generate(m)
    assert 'class="chips"' not in h


def test_special_abilities_block_renders_rows_with_facts():
    m = _ankheg()
    m.combat = "Anyone within 30 feet must save vs. petrification or turn to stone."
    h = monster_html.generate(m)
    assert '<div class="sb-h">Special Abilities</div>' in h   # a sub-block of the stat block
    assert '<span class="abil-name">Petrification</span>' in h
    assert '<span class="chip">30 feet</span>' in h
    assert '<span class="chip save">Save vs. Petrification</span>' in h
    assert "turn to stone" in h                     # the source sentence is shown
    # it lives inside the stat block section, not as a full-width card
    assert h.index('<div class="sb-h">Special Abilities') > h.index('class="statblock"')
    assert h.index('<div class="sb-h">Special Abilities') < h.index('class="prose-col"')


def test_no_abilities_block_without_extractable_mechanics():
    m = _ankheg()
    m.combat = "It is immune to charm. It fights without fear."
    h = monster_html.generate(m)
    assert '>Special Abilities</div>' not in h       # no sub-block (the CSS comment doesn't match)


def test_spell_like_abilities_render_as_capitalized_compendium_links():
    import monster_spells
    idx = monster_spells.build_index(["Charm Person", "Animate Dead", "Suggestion"])
    m = _ankheg()
    m.combat = "It can cast charm person and animate dead at will."
    h = monster_html.generate(m, spell_index=idx)
    assert '<div class="sb-h">Spell-like Abilities</div>' in h    # inside the stat block
    assert '<a class="chip spell" href="dnd:///spell/charm-person">Charm Person</a>' in h
    assert 'href="dnd:///spell/animate-dead">Animate Dead</a>' in h   # canonical capitalization


def test_no_spell_block_without_index_or_matches():
    m = _ankheg()
    m.combat = "It can cast charm person."
    assert '>Spell-like Abilities</div>' not in monster_html.generate(m)   # no index passed
    import monster_spells
    idx = monster_spells.build_index(["Charm Person"])
    m2 = _ankheg()
    m2.combat = "It just bites."
    assert '>Spell-like Abilities</div>' not in monster_html.generate(m2, spell_index=idx)


def test_breath_tile_appears_only_for_a_selected_dragon_age_tier():
    age = {"kind": "age", "header_rows": 2, "rows": [
        ["", "", "", "", "Breath", "", "", "", ""],
        ["Age", "Lgt", "Lgt", "AC", "Weapon", "Wizard", "MR", "Type", "Value"],
        ["1", "3-6", "2-5", "4", "2d4", "Nil", "Nil", "Nil", "4,000"],
        ["12", "96", "80", "-7", "24d4", "9", "45%", "Hx3", "20,000"]]}
    m = Monster(name="Dragon", armor_class="1 (base)", extra_tables=[age])
    assert 'class="tile-l">Breath<' not in monster_html.generate(m)   # no tier -> no breath tile
    m.selected_tier = 1
    h = monster_html.generate(m)
    assert 'class="tile-l">Breath<' in h and "24d4" in h              # the oldest age's breath


def test_related_creatures_section_renders():
    m = _ankheg()
    m.related_creatures = [{"name": "Archlich", "text": "A rare good-aligned lich."}]
    h = monster_html.generate(m)
    assert "Also Described on This Page" in h
    assert '<div class="rel-name">Archlich</div>' in h and "good-aligned lich" in h


def test_no_related_section_when_none():
    assert 'class="related"' not in monster_html.generate(_ankheg())


def test_no_tier_selector_for_a_non_scaling_monster():
    h = monster_html.generate(_ankheg())
    assert 'class="tierbar"' not in h and "monText('tier'" not in h


def test_tier_selector_lists_base_and_each_tier():
    m = Monster(name="Mummy", armor_class="2", extra_tables=[_mummy_age_table()])
    h = monster_html.generate(m)
    assert 'class="tiersel"' in h and "monText('tier'" in h
    assert "Base (as written)" in h
    assert "Age 99 (or less)" in h and "Age 500 (or more)" in h
    assert 'value="base" selected' in h                    # base is the default selection


def test_selected_tier_scales_combat_strip_and_locks_editing():
    m = Monster(name="Mummy", armor_class="2", thac0="11",
                extra_tables=[_mummy_age_table()], selected_tier=1)
    h = monster_html.generate(m)
    # tier 1 is "500 or more": AC -3 -> ascending 23, THAC0 7 -> attack bonus 13
    assert ">23<" in h and ">13<" in h
    assert 'value="1" selected' in h
    assert "Scaled to Age 500 (or more)" in h
    assert "set/armor_class" not in h and "set/thac0" not in h   # read-only while tiered
    assert "readonly" in h


def test_base_tier_keeps_the_stat_block_editable():
    m = Monster(name="Mummy", armor_class="2", thac0="11", extra_tables=[_mummy_age_table()])
    h = monster_html.generate(m)                           # selected_tier is None -> base
    assert "set/armor_class" in h and "set/thac0" in h


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


# ── a Size the Monstrous Manual never printed ────────────────────────────────
#
# The MM's compact summary grids (Bird, Fish, Insect, Mammal, Ooze) carry no Size
# column at all, so 92 of the 634 importable creatures have none. That is the source
# data rather than a parse failure -- but it is silently consequential: initiative
# speed factor derives from Size, so those sheets showed a bare em dash and the
# Roll20 export sent speed 0, with nothing saying why or what to do.

def test_missing_size_explains_itself_and_points_at_the_override():
    m = Monster(name="Blood Hawk", hit_dice="1+1", thac0="19", size="")
    html = monster_html.generate(m)
    assert monster_html.SIZE_ABSENT_HINT in html
    assert 'placeholder="set"' in html          # the box is the only way to get one
    assert "lists no Size" in html              # the tooltip says why


def test_a_creature_with_a_size_gets_no_hint():
    m = Monster(name="Ankheg", hit_dice="3", thac0="17", size="H (10' long)")
    html = monster_html.generate(m)
    assert monster_html.SIZE_ABSENT_HINT not in html
    assert 'placeholder="init"' in html         # the ordinary override affordance


def test_an_initiative_override_suppresses_the_hint():
    """Once the DM has supplied a speed factor the gap is closed; nagging about the
    absent Size would be noise."""
    m = Monster(name="Blood Hawk", hit_dice="1+1", thac0="19", size="",
                initiative_override=3)
    html = monster_html.generate(m)
    assert monster_html.SIZE_ABSENT_HINT not in html
    assert m.initiative_modifier() == 3


def test_the_hint_does_not_claim_a_size_the_sheet_would_show():
    """Guards against firing on whitespace-only Size, which renders as empty."""
    m = Monster(name="Thing", hit_dice="2", thac0="19", size="   ")
    assert monster_html.SIZE_ABSENT_HINT in monster_html.generate(m)

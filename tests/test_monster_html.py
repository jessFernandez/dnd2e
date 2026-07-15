"""Tests for monster_html.py — the DM monster sheet view (pure HTML render)."""
import monster_html
from monster import Monster


def _ankheg() -> Monster:
    return Monster(
        name="Ankheg", source_page="MM/DD03797.htm",
        climate_terrain="Temperate/Plains", armor_class="Overall 2, underside 4",
        thac0="17-13", hit_dice="3-8", no_of_attacks="1",
        damage_attack="3-18 (crush)", special_attacks="Squirt acid", size="L-H",
        description="A burrowing monster.", combat="It squirts acid to 30 feet.",
        habitat_society="Solitary broods.", ecology="Eats fresh meat.",
    )


def test_renders_name_and_source_link():
    h = monster_html.generate(_ankheg())
    assert "Ankheg" in h
    assert 'dnd:///MM/DD03797.htm' in h          # back-link to the MM page


def test_shows_house_rule_values():
    h = monster_html.generate(_ankheg())
    # attack bonus (20-THAC0), ascending AC (20-desc), and size-based initiative
    assert "3-7" in h                            # THAC0 17-13 -> bonus
    assert "Overall 18, underside 16" in h       # AC converted in place
    assert "+9" in h                             # size L-H -> Huge initiative


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

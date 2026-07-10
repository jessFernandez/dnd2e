"""Smoke tests for the HTML screen generators.

These are pure `generate()` functions we edit often (layout/spacing fixes), yet
they had no tests. Each check asserts the generator returns a well-formed,
non-trivial document containing the structure it's supposed to — enough to catch
a template break, a bad f-string, or a missing section.
"""
import actionsscreen_html
import askscreen_html
import charactermancer_html
import dmscreen_html
import splash_html
import spellsscreen_html
import toc_html
from charactermancer import Charactermancer


def _is_page(html: str):
    assert isinstance(html, str) and len(html) > 500
    assert "<style" in html and "</html>" in html.lower() or "</body>" in html.lower()


def test_dmscreen():
    html = dmscreen_html.generate()
    _is_page(html)
    assert "<table" in html                      # it's a table-heavy quick reference


def test_actionsscreen():
    html = actionsscreen_html.generate()
    _is_page(html)


def test_splash():
    html = splash_html.generate()
    _is_page(html)
    assert "2nd Edition" in html
    assert "dnd:///screen/spells" in html          # the Spells feature card we added
    assert "dnd:///screen/charactermancer" in html # Character Builder card (replaced the walkthrough)


def test_charactermancer_step_references():
    # The builder folds in the old walkthrough's value: per-step deep-links.
    html = charactermancer_html.generate(Charactermancer())
    _is_page(html)
    assert "References" in html
    assert 'href="dnd:///newtab/PHB/' in html           # abilities -> PHB, in a new tab
    # Proficiency, spell, and equipment steps point at in-app pages, not the PHB.
    nwp = charactermancer_html._step_refs("nonweapon")
    assert 'href="dnd:///newtab/proficiencies"' in nwp and "Codex of Worldly Craft" in nwp
    # The weapon step points at the PHB rules and the Combat & Tactics chapters.
    weapons = charactermancer_html._step_refs("weapons")
    assert 'href="dnd:///newtab/PHB/DD01526.htm"' in weapons     # Weapon Proficiencies
    assert 'href="dnd:///newtab/CT/DD02618.htm"' in weapons      # Specialization & Mastery
    assert 'href="dnd:///newtab/CT/DD02666.htm"' in weapons      # Unarmed Combat
    spells = charactermancer_html._step_refs("spells")
    assert 'href="dnd:///newtab/screen/spells"' in spells and "Spell Compendium" in spells
    equip = charactermancer_html._step_refs("equipment")
    assert 'href="dnd:///newtab/toc/ECO"' in equip and "Economics of the Realm" in equip


def test_spells_screen():
    spell = {
        "name": "Fireball", "caster": "wizard", "level": 3, "school": "Evocation",
        "components": "V, S, M", "range": "10 yds.", "casting_time": "3",
        "duration": "Instantaneous", "aoe": "20-ft. radius", "save": "1/2",
        "damage": "1d6/level", "materials": "bat guano", "description": "A ball of fire.",
        "residue": "Common", "source": "PHB p.191", "spheres": "", "specializations": "Invoker",
    }
    html = spellsscreen_html.generate([spell])
    _is_page(html)
    assert "Spell Compendium" in html
    assert "Fireball" in html and "<article class=\"card\"" in html
    # specialization filter data made it onto the card for JS filtering
    assert 'data-specs="|Invoker|"' in html


def test_spells_screen_empty():
    html = spellsscreen_html.generate([])
    _is_page(html)


# ── toc_html (extracted from MainWindow) ─────────────────────────────────────

def test_book_toc_links_and_house_rule_badge():
    chapters = [{
        "name": "Chapter 9: Combat", "page_url": "PHB/DD01661.htm",
        "entries": [("PHB/DD01661.htm", "Combat-- Chapter 9 (X)"),
                    ("PHB/DD01662.htm", "THAC0 (X)")],
    }]
    hr = {"Chapter 9": [("Combat", "THAC0 is replaced by attack bonus")]}
    html = toc_html.book_toc("Player's Handbook", "#5b9bd5", chapters, hr)
    _is_page(html)
    assert "Player's Handbook" in html
    assert 'href="dnd:///PHB/DD01661.htm"' in html
    assert "Chapter 9: Combat" in html
    assert "⚔ HR" in html                          # keyword matched the chapter
    assert "THAC0 is replaced by attack bonus" in html


def test_book_toc_no_house_rules_no_badge():
    chapters = [{"name": "A", "page_url": "PHB/x.htm", "entries": [("PHB/x.htm", "Armor")]}]
    html = toc_html.book_toc("PHB", "#5b9bd5", chapters, {})
    assert "⚔ HR" not in html


def test_house_rules_callout():
    html = toc_html.house_rules_callout([("Combat", "No THAC0")], "#c9a84c")
    assert "No THAC0" in html and "hrx" in html and "<details" in html


# ── Jarvis screen states ──────────────────────────────────────────────────────

def test_askscreen_all_states_render():
    for state in ("ready", "loading", "answer", "error"):
        html = askscreen_html.generate(
            state, models=["llama3.1"], question="how does thac0 work",
            answer_md="**Roll** a d20.", error="boom",
        )
        assert isinstance(html, str) and len(html) > 200


def test_askscreen_setup_without_ollama_explains_install():
    html = askscreen_html.generate("setup", ollama_ok=False)
    assert "Ollama" in html

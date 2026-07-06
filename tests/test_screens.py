"""Smoke tests for the HTML screen generators.

These are pure `generate()` functions we edit often (layout/spacing fixes), yet
they had no tests. Each check asserts the generator returns a well-formed,
non-trivial document containing the structure it's supposed to — enough to catch
a template break, a bad f-string, or a missing section.
"""
import actionsscreen_html
import askscreen_html
import chargen_html
import dmscreen_html
import splash_html
import spellsscreen_html
import toc_html


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


def test_chargen():
    html = chargen_html.generate()
    _is_page(html)
    assert "Ability Scores" in html               # step 1 of the walkthrough


def test_splash():
    html = splash_html.generate()
    _is_page(html)
    assert "2nd Edition" in html
    assert "dnd:///screen/spells" in html         # the Spells feature card we added


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

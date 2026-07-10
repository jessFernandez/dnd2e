"""charactermancer_common.py — chrome shared by the builder's HTML modules.

The builder's view grew past one file: `charactermancer_html.py` owns the document
shell, the progress rail and most steps, while `charactermancer_profs_html.py` owns
the two proficiency steps. The handful of primitives both need live here so neither
imports the other.

Pure string templating, Qt-free — see `charactermancer_html` for the layer rules.
(Not to be confused with `proficiencies_html.py`, which renders the *Codex of
Worldly Craft* reference screen rather than anything in the builder.)
"""
import html

#: The builder's gold. Also read by app.py to tint the sidebar's builder entry.
ACCENT = "#c9a84c"

#: Ability name -> the three-letter form the sheet and the step headers use.
ABBR = {"Strength": "Str", "Dexterity": "Dex", "Constitution": "Con",
        "Intelligence": "Int", "Wisdom": "Wil", "Charisma": "Cha",
        "Perception": "Per"}


def esc(s) -> str:
    """HTML-escape a value for interpolation into a template."""
    return html.escape(str(s), quote=True)


def budget_bar(used: int, total: int, label: str, unit: str = "slots used",
               over_note: str = "") -> str:
    """A spent/remaining bar. Going over budget is reachable by dropping a level,
    so the bar turns red and explains itself rather than quietly reading "-2 left"."""
    left = total - used
    pct = 0 if total <= 0 else min(100, round(used / total * 100))
    over = left < 0
    cls = " over" if over else ""
    note = (f'<div class="budget-over">Over budget by {-left}. '
            f'{over_note}</div>') if over and over_note else ""
    return (
        f'<div class="budget{cls}">'
        f'<div class="budget-top"><span>{label}</span>'
        f'<span class="budget-num">{left} left</span></div>'
        f'<div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>'
        f'<div class="budget-sub">{used} of {total} {unit}</div>'
        f'{note}'
        '</div>'
    )

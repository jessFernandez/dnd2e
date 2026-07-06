"""
build_economics.py — Build the 'Economics of the Realm' homebrew book.
Reads CSVs from ./economics_csv/ and inserts pages + toc_entries into dnd2e.db.
Run once, or re-run to rebuild (it replaces existing ECO entries).
"""

import csv, io, re, sqlite3
from html import escape
from pathlib import Path

DB_PATH = Path(__file__).parent / "dnd2e.db"
CSV_DIR = Path(__file__).parent / "economics_csv"

BOOK_CODE = "ECO"
BOOK_NAME = "Economics of the Realm"

ACCENT = "#c9a84c"    # gold

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_csv(filename):
    path = CSV_DIR / filename
    text = path.read_text(encoding="utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def trim_rows(rows, *, skip=1, cols=None):
    """Drop the header row(s) and trailing empty columns."""
    data = rows[skip:]
    if cols:
        data = [r[:cols] for r in data]
    elif data:
        # Auto-detect width: last column that has any content
        max_w = max(
            (next((i for i in range(len(r)-1, -1, -1) if r[i].strip()), -1) + 1)
            for r in data
        )
        data = [r[:max_w] for r in data]
    return [r for r in data if any(c.strip() for c in r)]


def th(text, right=False):
    align = ' style="text-align:right"' if right else ''
    return f'<th{align}>{escape(text)}</th>'


def td(text, right=False, cls=""):
    align = ' style="text-align:right"' if right else ''
    klass = f' class="{cls}"' if cls else ''
    return f'<td{align}{klass}>{escape(text)}</td>'


def build_table(headers, rows, right_cols=(), note_cols=()):
    """Return an HTML <table> string."""
    head = ''.join(th(h, right=(i in right_cols)) for i, h in enumerate(headers))
    body = ''
    for row in rows:
        cells = ''
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else ''
            cells += td(val, right=(i in right_cols), cls='note' if i in note_cols else '')
        body += f'<tr>{cells}</tr>\n'
    return f'<table><thead><tr>{head}</tr></thead><tbody>\n{body}</tbody></table>'


def page_html(chapter_num, title, description, table_html, footer=''):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)} — {escape(BOOK_NAME)}</title>
<style>
  body {{
    font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
    padding: 28px 36px;
    max-width: 980px;
    line-height: 1.5;
  }}
  .breadcrumb {{ color: #6b7280; font-size: 11px; letter-spacing: .06em;
    text-transform: uppercase; margin-bottom: 10px; }}
  h1 {{ font-size: 1.75em; color: {ACCENT}; border-bottom: 2px solid {ACCENT}55;
    padding-bottom: 8px; margin: 0 0 6px; }}
  .desc {{ color: #b0b4c8; font-size: 13.5px; margin: 14px 0 22px;
    background: #1e2130; border-left: 3px solid {ACCENT}88;
    padding: 12px 16px; border-radius: 0 6px 6px 0; line-height: 1.7; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }}
  th {{ background: #17192a; color: {ACCENT}; text-align: left; padding: 8px 11px;
    font-size: 10.5px; letter-spacing: .08em; text-transform: uppercase;
    border-bottom: 2px solid #3a3e50; white-space: nowrap; }}
  td {{ padding: 6px 11px; border-bottom: 1px solid #2a2e3c;
    vertical-align: top; color: #c8cad8; }}
  tr:hover td {{ background: #2d3040; }}
  tr:nth-child(even) td {{ background: #252836; }}
  tr:nth-child(even):hover td {{ background: #2d3040; }}
  td.note {{ color: #8a8fa8; font-style: italic; font-size: 12px; }}
  .footer {{ margin-top: 28px; color: #4b5563; font-size: 11.5px;
    border-top: 1px solid #2a2e3c; padding-top: 14px; font-style: italic; }}
  .wip {{ background: #2a1a00; border: 1px solid #8a5a00; color: #d4943a;
    padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 20px; }}
</style>
</head>
<body>
<div class="breadcrumb">{escape(BOOK_NAME)}&nbsp;&nbsp;·&nbsp;&nbsp;Chapter {chapter_num}</div>
<h1>{escape(title)}</h1>
<div class="desc">{description}</div>
{table_html}
{footer}
</body>
</html>"""


# ── Introduction ──────────────────────────────────────────────────────────────

INTRO_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Introduction — {escape(BOOK_NAME)}</title>
<style>
  body {{
    font-family: "Trebuchet MS", "Segoe UI", system-ui, sans-serif;
    padding: 28px 36px; max-width: 820px; line-height: 1.7;
  }}
  .book-tag {{ display: inline-block; background: {ACCENT}20; color: {ACCENT};
    font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
    padding: 3px 10px; border-radius: 4px; margin-bottom: 14px; }}
  h1 {{ font-size: 2.2em; color: #e4e6f0; margin: 0 0 6px; font-weight: 800; }}
  .divider {{ height: 3px; width: 48px; background: {ACCENT}; border-radius: 2px;
    margin: 14px 0 28px; }}
  h2 {{ color: {ACCENT}; font-size: 1.1em; margin-top: 28px; margin-bottom: 6px;
    letter-spacing: .04em; }}
  p {{ color: #c0c2d0; font-size: 14px; margin: 0 0 14px; }}
  .currency-box {{ background: #17192a; border: 1px solid {ACCENT}44;
    border-radius: 8px; padding: 16px 20px; margin: 20px 0; }}
  .currency-box table {{ width: auto; border-collapse: collapse; font-size: 13px; }}
  .currency-box td {{ padding: 4px 16px 4px 0; color: #c8cad8; border: none; background: none; }}
  .currency-box td:first-child {{ color: {ACCENT}; font-weight: 600; min-width: 130px; }}
  .chapter-list {{ columns: 2; column-gap: 32px; margin: 16px 0 0; padding: 0;
    list-style: none; font-size: 13.5px; color: #c0c2d0; }}
  .chapter-list li {{ margin-bottom: 6px; padding-left: 14px; position: relative; }}
  .chapter-list li::before {{ content: "◆"; color: {ACCENT}; font-size: 8px;
    position: absolute; left: 0; top: 4px; }}
  .chapter-list strong {{ color: #e4e6f0; }}
</style>
</head>
<body>
<div class="book-tag">Homebrew Supplement</div>
<h1>{escape(BOOK_NAME)}</h1>
<div class="divider"></div>

<p>
  Trade is the lifeblood of civilization. From the humblest copper coin pressed into a baker's
  hand to the vast merchant fleets that carry spices across continents, economics shapes every
  corner of the realm — and every decision an adventurer makes. This supplement provides detailed
  pricing, availability, and economic context for the campaign, going far beyond what the core
  rulebooks offer.
</p>
<p>
  Whether you are outfitting a newly-minted first-level character, negotiating with a merchant
  guild, trying to figure out what a week of inn keep will cost the party, or researching the
  going rate for a hired sword, this guide has you covered.
</p>

<h2>The Currency System</h2>
<p>
  All prices in this guide are listed in <strong>copper pieces (cp)</strong>, the base unit of
  currency in this campaign. Unlike settings that default to a gold-piece economy, copper is the
  coin most commonly exchanged between common folk. A labourer earns 10 cp a day; a fine dinner
  costs 5 cp; a sword costs thousands.
</p>
<div class="currency-box">
  <table>
    <tr><td>1 Platinum Piece (pp)</td><td>=&nbsp; 1,000 cp</td></tr>
    <tr><td>1 Gold Piece (gp)</td><td>=&nbsp; 100 cp</td></tr>
    <tr><td>1 Electrum Piece (ep)</td><td>=&nbsp; 50 cp</td></tr>
    <tr><td>1 Silver Piece (sp)</td><td>=&nbsp; 10 cp</td></tr>
    <tr><td>1 Copper Piece (cp)</td><td>=&nbsp; 1 cp</td></tr>
  </table>
</div>

<h2>A Note on Prices</h2>
<p>
  Listed prices represent fair market value in a medium-sized town under normal conditions.
  Supply and demand, local shortages, political upheaval, and a merchant's personal assessment
  of a customer's wealth can all shift prices significantly. The DM is encouraged to apply a
  25–50% modifier in either direction based on circumstances. Haggling may reduce prices by
  up to 20% with a successful Charisma check.
</p>
<p>
  Prices are listed for serviceable, standard-quality goods. Masterwork items typically cost
  two to five times the listed price and confer bonuses at the DM's discretion.
</p>

<h2>How to Use This Book</h2>
<p>
  Each chapter covers a category of goods or services. Items are listed with their cost in
  copper pieces, weight in pounds, and relevant notes. Where applicable, construction time,
  seasonal availability, and special rules are included.
</p>

<h2>Chapters</h2>
<ul class="chapter-list">
  <li><strong>Chapter 2: Gear &amp; Equipment</strong> — Tools, containers, and sundry supplies</li>
  <li><strong>Chapter 3: Armor</strong> — Protection from gambeson to full plate</li>
  <li><strong>Chapter 4: Weapons</strong> — Blades, bows, and bludgeons</li>
  <li><strong>Chapter 5: Lodging &amp; Tavern Costs</strong> — A warm bed and a cold pint</li>
  <li><strong>Chapter 6: Animals</strong> — Mounts, livestock, and companions</li>
  <li><strong>Chapter 7: Animal Gear</strong> — Saddles, barding, and harnesses</li>
  <li><strong>Chapter 8: Services</strong> — What others will do for coin</li>
  <li><strong>Chapter 9: Clothing</strong> — From rags to embroidered finery</li>
  <li><strong>Chapter 10: Transportation</strong> — Land and water vehicles</li>
  <li><strong>Chapter 11: Food &amp; Provisions</strong> — Seasonal availability and pricing</li>
  <li><strong>Chapter 12: Employment &amp; Wages</strong> — What common folk earn</li>
  <li><strong>Chapter 13: Spell Components</strong> — The material cost of magic</li>
  <li><strong>Chapter 14: Alchemy</strong> — Potions, poisons, and peculiarities</li>
  <li><strong>Chapter 15: Blackmarket</strong> — Goods requiring discretion</li>
  <li><strong>Chapter 16: Metals &amp; Materials</strong> — Relative costs of metals</li>
  <li><strong>Chapter 17: Magic Tools</strong> — Enchanted items of utility</li>
</ul>

</body>
</html>"""


# ── Chapter builders ──────────────────────────────────────────────────────────

def build_gear():
    rows = trim_rows(load_csv("Gear.csv"), cols=4)
    table = build_table(
        ["Gear", "Cost (cp)", "Weight (lb)", "Notes"],
        rows, right_cols=(1, 2), note_cols=(3,)
    )
    desc = (
        "The tools, containers, and sundry goods that adventurers rely upon day to day. "
        "Prices reflect standard quality; exceptional craftwork may command two to five times "
        "the listed price. All weights are for the empty item unless otherwise noted."
    )
    return page_html(2, "Gear & Equipment", desc, table)


def build_armor():
    rows = trim_rows(load_csv("Armor_-_Partial.csv"), cols=6)
    table = build_table(
        ["Armor", "Cost (cp)", "Weight (lb)", "AC Bonus", "Weeks to Make", "Notes"],
        rows, right_cols=(1, 2, 3, 4), note_cols=(5,)
    )
    desc = (
        "Body protection crafted from padded gambeson, hardened leather, chainmail rings, "
        "and tempered steel plate. The <em>AC Bonus</em> is added to a base AC of 10; "
        "multiple pieces stack at DM discretion. <em>Weeks to Make</em> assumes a skilled "
        "smith working full days. Prices are for standard-quality work."
    )
    return page_html(3, "Armor", desc, table)


def build_weapons():
    rows = trim_rows(load_csv("Weapons.csv"), cols=12)
    table = build_table(
        ["Weapon", "Cost (cp)", "Wt.", "Sz", "Type", "Spd", "Damage",
         "Reach", "Range (yds)", "RoF", "Days to Make", "Notes"],
        rows, right_cols=(1, 2, 5, 9, 10), note_cols=(11,)
    )
    desc = (
        "From crude clubs to masterwork blades. <strong>Speed</strong> determines initiative "
        "order (lower = faster). <strong>Size</strong>: S/M/L. "
        "<strong>Type</strong>: B = Bludgeoning, P = Piercing, S = Slashing. "
        "<strong>Range</strong> shows Short / Medium / Long in yards. "
        "<strong>RoF</strong> = attacks per round. "
        "<em>Days to Make</em> assumes a skilled weaponsmith."
    )
    return page_html(4, "Weapons", desc, table)


def build_lodging():
    raw = load_csv("Inn_Costs.csv")
    # First col header is blank; manually set headers
    rows = trim_rows(raw, cols=4)
    # Col 2 is always empty — drop it
    cleaned = [[r[0], r[1], r[3] if len(r) > 3 else ''] for r in rows]
    table = build_table(["Item", "Cost (cp)", "Notes"], cleaned,
                        right_cols=(1,), note_cols=(2,))
    desc = (
        "The price of comfort on the road. Inn costs cover one night; meal quality scales "
        "with the room. Alcohol is priced by the serving and by bulk barrel — "
        "buying by the barrel saves roughly 60%."
    )
    return page_html(5, "Lodging & Tavern Costs", desc, table)


def build_animals():
    raw = load_csv("Animals.csv")
    rows = trim_rows(raw, cols=7)
    table = build_table(
        ["Animal", "Cost (cp)", "Monthly Upkeep (cp)", "Weight (lb)",
         "Move Rate", "Lifting Encumbrance (lb)", "Pulling Encumbrance (lb)"],
        rows, right_cols=(1, 2, 3), note_cols=()
    )
    desc = (
        "Beasts of burden, war mounts, livestock, and companions. Monthly upkeep includes "
        "feed but not stabling (see Chapter 8: Services). Encumbrance columns show "
        "Maximum / Standard / Light load in pounds. Movement rate is in yards per round."
    )
    return page_html(6, "Animals", desc, table)


def build_animal_gear():
    rows = trim_rows(load_csv("Animal_Gear.csv"), cols=4)
    table = build_table(
        ["Gear", "Cost (cp)", "Weight (lb)", "Notes"],
        rows, right_cols=(1, 2), note_cols=(3,)
    )
    desc = "Saddles, harnesses, barding, and other equipment for your mounts and work animals."
    return page_html(7, "Animal Gear", desc, table)


def build_services():
    raw = load_csv("Services.csv")
    rows = trim_rows(raw, cols=4)
    # Col 3 is occasional notes
    table = build_table(["Service", "Cost (cp)", "Per", "Notes"],
                        rows, right_cols=(1,), note_cols=(3,))
    desc = (
        "The cost of skilled and unskilled labour by the task. Prices assume a typical "
        "urban setting; rural areas may differ. Where <em>Expenses</em> is noted, "
        "travel and material costs are not included in the listed price."
    )
    return page_html(8, "Services", desc, table)


def build_clothing():
    rows = trim_rows(load_csv("Clothing.csv"), cols=3)
    # Drop rows where both cost and weight are blank (incomplete entries)
    rows = [r for r in rows if len(r) > 1 and r[1].strip()]
    table = build_table(["Clothing", "Cost (cp)", "Weight (lb)"],
                        rows, right_cols=(1, 2))
    desc = (
        "From a peasant's rough-spun tunic to a merchant's embroidered silks, clothing "
        "signals social standing as much as it provides warmth. Prices are for good but "
        "not exceptional work; haute couture commands five to twenty times more."
    )
    return page_html(9, "Clothing", desc, table)


def build_transport():
    rows = trim_rows(load_csv("Transpo.csv"), cols=7)
    table = build_table(
        ["Vehicle", "Cost (cp)", "Weight (lb)", "Max Load (lb)", "Passengers", "Type", "Notes"],
        rows, right_cols=(1, 2, 3, 4), note_cols=(6,)
    )
    desc = (
        "Land and water vehicles for moving people and cargo. "
        "<em>Max Load</em> is total carrying capacity including passengers and crew. "
        "<em>Passengers</em> excludes the driver or crew. Boats require a crew of at "
        "least 2 unless noted as single-person craft."
    )
    return page_html(10, "Transportation", desc, table)


def build_food():
    rows = trim_rows(load_csv("Food.csv"), cols=8)
    table = build_table(
        ["Food Item", "Cost (cp)", "Weight (lb)",
         "Spring", "Summer", "Autumn", "Winter", "Notes"],
        rows, right_cols=(1, 2), note_cols=(7,)
    )
    desc = (
        "Seasonal availability affects the price of fresh produce. An <strong>x</strong> "
        "in a season column indicates the item is readily available that season. "
        "Prices listed are for standard market rates; bulk purchase or harvest glut "
        "may reduce costs by 25–50%. Off-season goods may cost double or more."
    )
    return page_html(11, "Food & Provisions", desc, table)


def build_jobs():
    raw = load_csv("Jobs.csv")
    # Actual columns: Job, Daily, Weekly, Monthly, Yearly, Type, Notes
    rows = trim_rows(raw, cols=7)
    # Sort by type then job name for readability
    rows.sort(key=lambda r: (r[5] if len(r) > 5 else '', r[0]))
    table = build_table(
        ["Job", "Daily (cp)", "Weekly (cp)", "Monthly (cp)", "Yearly (cp)", "Category", "Notes"],
        rows, right_cols=(1, 2, 3, 4), note_cols=(6,)
    )
    desc = (
        "The going rate for common labour, skilled tradespeople, professionals, and servants. "
        "Wages are guidelines — a reputable worker may charge more; a desperate one may "
        "accept less. Room and board are not included unless noted. "
        "<em>Weekly = Daily × 6; Monthly = Daily × 25; Yearly = Daily × 300.</em>"
    )
    footer = (
        '<div class="footer">Warrior wages follow the same multipliers: '
        'Daily (X), Weekly (6×X), Monthly (25×X), Yearly (300×X) — '
        'negotiate based on danger level and specialisation.</div>'
    )
    return page_html(12, "Employment & Wages", desc, table, footer)


def build_spell_components():
    raw = load_csv("Spell_Components.csv")
    # First 3 rows are legend; row index 3 is the real header
    header_row = raw[3]
    useful_headers = ["Item", "Animal", "Plant", "Mineral", "Rarity Group",
                      "Other", "Acquisition", "Scarcity", "Cost (cp)",
                      "Weight (lb)", "Expires (days)", "Notes"]
    rows = trim_rows(raw, skip=4, cols=12)
    table = build_table(useful_headers, rows,
                        right_cols=(8, 9, 10), note_cols=(11,))
    legend = (
        '<div class="footer">'
        '<strong>Acquisition:</strong> Auto = found automatically during relevant activity; '
        'FS = Field Search (wild foraging); TM = Town or Market; SO = Special Order (1d4 weeks).<br>'
        '<strong>Scarcity availability by settlement:</strong> '
        'Common — Village 80%, Town 90%, City 100%, +Magic Shop +50%; '
        'Uncommon — 40% / 60% / 80% / +50%; '
        'Rare — 0% / 20% / 40% / +50%.<br>'
        'Field Search times: Common 1d6 turns (75% chance, +10/turn); '
        'Uncommon 3d6 turns (50%, +5/turn); Rare 1d4+1 hours (25%, +2/turn).<br>'
        'Components can usually be sold to magic shops for ~50% of listed cost. '
        'Rarer components may fetch only 20% or less.'
        '</div>'
    )
    desc = (
        "The material reagents consumed by magical workings. Availability varies by "
        "settlement size and scarcity rating. Most free (0 cp) components can be found "
        "automatically during normal activity or travel. Powders generally cost 1.5–2× "
        "the base component price. See the legend below for full acquisition rules."
    )
    return page_html(13, "Spell Components", desc, table, legend)


def build_alchemy():
    rows = trim_rows(load_csv("Alchemy.csv"), cols=6)
    table = build_table(
        ["Item", "Cost (cp)", "Weight (lb)", "Effects", "Side Effects", "Rare Ingredients"],
        rows, right_cols=(1, 2), note_cols=(4, 5)
    )
    desc = (
        "Brewed and distilled substances, from mundane preparations to exotic concoctions. "
        "Side effects occur on a failed Constitution saving throw (DC at DM discretion). "
        "Rare ingredients may be difficult to source and can double or triple the listed price. "
        "Most alchemical items have a shelf life of 6–12 months unless otherwise specified."
    )
    return page_html(14, "Alchemy", desc, table)


def build_blackmarket():
    rows = trim_rows(load_csv("Blackmarket.csv"), cols=4)
    table = build_table(
        ["Goods / Service", "Cost (cp)", "Weight (lb)", "Notes"],
        rows, right_cols=(1, 2), note_cols=(3,)
    )
    desc = (
        "Goods and services available only through criminal intermediaries. All prices are "
        "approximate — black market rates fluctuate with risk, demand, and how well the "
        "contact trusts the buyer. Engaging in these transactions may attract the attention "
        "of thieves' guilds, city watch, or those with a vested interest in the transaction's "
        "secrecy. Assassination prices represent minimums for professionals; target prominence, "
        "security, and timeline all affect the final fee."
    )
    return page_html(15, "Blackmarket", desc, table)


def build_metals():
    raw = load_csv("Metals.csv")
    # Useful columns: 0 (metal name), 1 (relative to copper), 11 (cp/lb), 12 (density), 13 (raw materials cp/lb)
    data_rows = trim_rows(raw, skip=1, cols=14)
    # Keep only rows that look like metal entries (col 0 non-empty, col 1 is a number)
    metal_rows = []
    for r in data_rows:
        if r[0].strip() and r[1].strip() and re.match(r'^[\d.]+$', r[1].strip()):
            metal_rows.append([r[0], r[1], r[11] if len(r) > 11 else '',
                                r[12] if len(r) > 12 else '', r[13] if len(r) > 13 else ''])
    table = build_table(
        ["Metal", "Relative Cost (×copper)", "cp per Pound", "Density (vs. Copper)", "Raw Materials cp/lb"],
        metal_rows, right_cols=(1, 2, 3, 4)
    )
    desc = (
        "Relative costs and properties of metals used in crafting weapons, armor, and goods. "
        "To price an item made from an exotic metal: take the copper-equivalent item cost, "
        "multiply by the metal's <em>Relative Cost</em> multiplier. "
        "Labor is 10% of the exotic material value, or the standard item price — "
        "whichever is greater. Provide the raw metal; the smith supplies the labor."
    )
    footer = (
        '<div class="footer">'
        'Example: A copper arming sword costs 3,000 cp. '
        'A silver arming sword costs 3,000 × 10 = 30,000 cp in materials, '
        'plus 3,000 cp labor (the greater of 10% of 30,000 or 3,000) = <strong>33,000 cp</strong>.'
        '</div>'
    )
    return page_html(16, "Metals & Materials", desc, table, footer)


def build_magic_tools():
    raw = load_csv("Magic_Tools.csv")
    # Skip the "UNDER CONSTRUCTION" header row; filter stat-block rows
    STAT_FIELDS = {"Name", "Level", "Damage", "Range", "Casting Time",
                   "Duration", "Save", "AoE", "Materials", "Description", "School"}
    rows = []
    for r in raw[1:]:
        first = r[0].strip() if r else ''
        if first and first not in STAT_FIELDS and any(c.strip() for c in r[:5]):
            rows.append(r[:5])
    table = build_table(
        ["Item", "Cost (cp)", "Caster", "Spell", "Description"],
        rows, right_cols=(1,), note_cols=(4,)
    )
    wip = '<div class="wip">⚠ This chapter is a work in progress. Additional items will be added over time.</div>'
    desc = (
        "Enchanted items of everyday utility — not weapons of war, but tools of convenience "
        "that have found their way into the hands of merchants, scholars, and well-heeled "
        "adventurers. Each item is the product of a permanent enchantment and is priced "
        "accordingly."
    )
    return page_html(17, "Magic Tools", desc, wip + table)


# ── Database insertion ────────────────────────────────────────────────────────

CHAPTERS = [
    # (page_slug, chapter_num, title, html_func_or_html)
    ("eco_00", 0,  "Introduction",           INTRO_HTML),
    ("eco_01", 1,  "Gear & Equipment",        build_gear),
    ("eco_02", 2,  "Armor",                   build_armor),
    ("eco_03", 3,  "Weapons",                 build_weapons),
    ("eco_04", 4,  "Lodging & Tavern Costs",  build_lodging),
    ("eco_05", 5,  "Animals",                 build_animals),
    ("eco_06", 6,  "Animal Gear",             build_animal_gear),
    ("eco_07", 7,  "Services",                build_services),
    ("eco_08", 8,  "Clothing",                build_clothing),
    ("eco_09", 9,  "Transportation",          build_transport),
    ("eco_10", 10, "Food & Provisions",       build_food),
    ("eco_11", 11, "Employment & Wages",      build_jobs),
    ("eco_12", 12, "Spell Components",        build_spell_components),
    ("eco_13", 13, "Alchemy",                 build_alchemy),
    ("eco_14", 14, "Blackmarket",             build_blackmarket),
    ("eco_15", 15, "Metals & Materials",      build_metals),
    ("eco_16", 16, "Magic Tools",             build_magic_tools),
]


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Wipe existing ECO data
    c.execute("DELETE FROM toc_entries WHERE book_code = ?", (BOOK_CODE,))
    c.execute("DELETE FROM pages WHERE book_code = ?", (BOOK_CODE,))
    c.execute("DELETE FROM pages_fts WHERE page_url LIKE 'ECO/%'")

    for slug, chap_num, title, html_src in CHAPTERS:
        page_url = f"ECO/{slug}.htm"
        html = html_src() if callable(html_src) else html_src

        # Strip tags for plain-text FTS
        plain = re.sub(r'<[^>]+>', ' ', html)
        plain = re.sub(r'\s+', ' ', plain).strip()

        c.execute(
            """INSERT OR REPLACE INTO pages
               (book_code, book_name, page_id, page_url, title, content_text, content_html)
               VALUES (?,?,?,?,?,?,?)""",
            (BOOK_CODE, BOOK_NAME, slug, page_url, title, plain, html),
        )
        c.execute(
            "INSERT OR REPLACE INTO pages_fts (page_url, title, content_text) VALUES (?,?,?)",
            (page_url, title, plain),
        )

        if chap_num == 0:
            # Introduction: plain entry, no chapter marker format
            subtopic = f"Introduction-- Chapter 1 ({BOOK_NAME})"
        else:
            subtopic = f"{title}-- Chapter {chap_num + 1} ({BOOK_NAME})"

        c.execute(
            "INSERT INTO toc_entries (topic, subtopic, book_code, page_url) VALUES (?,?,?,?)",
            (title, subtopic, BOOK_CODE, page_url),
        )
        print(f"  OK Chapter {chap_num + 1:2d}: {title}")

    conn.commit()
    conn.close()
    print(f"\nDone — {len(CHAPTERS)} pages inserted into dnd2e.db.")
    print("Now add ECO to app.py BOOK_ORDER and restart.")


if __name__ == "__main__":
    main()

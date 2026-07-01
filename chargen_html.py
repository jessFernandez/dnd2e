"""chargen_html.py — Step-by-step AD&D 2E character creation walkthrough with PHB links."""
from html import escape as e

ACCENT = "#c9a84c"
ACCENT_DIM = "#7a6020"
ACCENT_BG  = "#1e1a08"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _phb_link(label, page_url, note=""):
    """A clickable chip that navigates to a PHB page."""
    title = f' title="{e(note)}"' if note else ""
    return (
        f'<a class="phb-link" href="dnd:///{e(page_url)}"{title}>'
        f'<span class="phb-badge">PHB</span>{e(label)}</a>'
    )


def _rules(items):
    rows = "".join(f'<div class="rule-row"><span class="bullet">▸</span><span>{e(item)}</span></div>' for item in items)
    return f'<div class="rule-list">{rows}</div>'


def _links(*pairs):
    """pairs = (label, page_url) or (label, page_url, note)"""
    items = "".join(_phb_link(*p) for p in pairs)
    return f'<div class="link-row">{items}</div>'


def _class_table(rows):
    """rows = [(class_name, page_url, req_str)]"""
    cells = ""
    for name, url, req in rows:
        cells += (
            f'<div class="class-card">'
            f'<a class="class-link" href="dnd:///{e(url)}">{e(name)}</a>'
            f'<div class="class-req">{e(req)}</div>'
            f'</div>'
        )
    return f'<div class="class-grid">{cells}</div>'


def _step(num, title, subtitle, body_html, *, optional=False):
    opt_badge = '<span class="opt-badge">Optional</span>' if optional else ""
    return f"""
<div class="step" id="step-{num}">
  <div class="step-header">
    <div class="step-title-line">
      <span class="step-num">{num}</span>
      <span class="step-title">{e(title)}</span>{opt_badge}
    </div>
    <div class="step-sub">{e(subtitle)}</div>
  </div>
  <div class="step-body">
    {body_html}
  </div>
</div>"""


# ── Steps ──────────────────────────────────────────────────────────────────────

def _step1():
    body = (
        '<p class="step-desc">Roll 3d6 six times and record each total. '
        'These are your six ability scores: Strength, Dexterity, Constitution, Intelligence, Wisdom, and Charisma. '
        'Your DM may allow an alternative rolling method.</p>'
        + _rules([
            "Method I (standard): Roll 3d6 straight for each score in order",
            "Method II: Roll 3d6 twelve times, keep the six best rolls — assign freely",
            "Method III: Roll 3d6 six times per ability score, keep the highest roll for each",
            "Method IV: Roll 3d6 twenty-four times, arrange into six groups of four, drop the lowest in each group",
            "Method V: Roll 7d6 six times, drop the three lowest dice from each roll",
            "If no score is 15 or higher, or two or more scores are 8 or lower, you may discard and re-roll (DM option)",
        ])
        + _links(
            ("Rolling Ability Scores", "PHB/DD01422.htm"),
            ("Alternative Rolling Methods", "PHB/DD01423.htm"),
            ("What the Numbers Mean", "PHB/DD01437.htm"),
        )
    )
    return _step(1, "Roll Ability Scores", "Determine your character's raw potential", body)


def _step2():
    body = (
        '<p class="step-desc">Choose your character\'s race. Your race determines language options, '
        'racial ability bonuses and penalties, special abilities, and which classes are available to you. '
        'Check the minimum/maximum ability score requirements before committing.</p>'
        + _rules([
            "Humans may be any class with no level limits",
            "Demihumans (Elves, Dwarves, etc.) have class restrictions and level caps",
            "Your rolled scores must meet the racial minimums before bonuses are applied",
            "Multi-class options are only available to non-human races",
        ])
        + _links(
            ("Racial Overview & Requirements", "PHB/DD01438.htm"),
            ("Min/Max Scores Table", "PHB/DD01440.htm"),
            ("Class Restrictions & Level Limits", "PHB/DD01443.htm"),
        )
        + '<p class="section-label" style="margin-top:14px">Choose a Race</p>'
        + _class_table([
            ("Dwarf",     "PHB/DD01445.htm", "Con 12+ · Str/Cha limits"),
            ("Elf",       "PHB/DD01447.htm", "Dex 7+, Con 8+ · Str limit"),
            ("Gnome",     "PHB/DD01448.htm", "Con 8+ · Str limit"),
            ("Half-Elf",  "PHB/DD01449.htm", "Most flexible demihuman"),
            ("Halfling",  "PHB/DD01450.htm", "Str max 17 · many Dex bonuses"),
            ("Human",     "PHB/DD01451.htm", "No restrictions — any class"),
        ])
    )
    return _step(2, "Choose a Race", "Race shapes your abilities, languages, and class options", body)


def _step3():
    body = (
        '<p class="step-desc">Apply your race\'s ability score adjustments. '
        'Then set your character\'s age, height, and weight. '
        'Very young or very old characters suffer penalties; '
        'some races grant infravision, detect secret doors, or other innate abilities.</p>'
        + _rules([
            "Apply racial Ability Adjustments — these can push a score above the racial maximum",
            "Note all racial special abilities (infravision, stonecunning, charm resistance, etc.)",
            "Choose or roll starting age using Table 11 — this determines your age category",
            "Determine height and weight (roll on Table 10 or choose within the range)",
            "Note any bonus languages granted by your race (in addition to your Intelligence allowance)",
        ])
        + _links(
            ("Racial Ability Adjustments", "PHB/DD01441.htm"),
            ("Adjustments Table (Table 8)", "PHB/DD01442.htm"),
            ("Other Details — Height, Weight, Age", "PHB/DD01452.htm"),
            ("Height & Weight Table (Table 10)", "PHB/DD01453.htm"),
            ("Age Table (Table 11)", "PHB/DD01454.htm"),
            ("Aging Effects (Table 12)", "PHB/DD01455.htm"),
        )
    )
    return _step(3, "Apply Racial Adjustments & Record Details", "Bonuses, penalties, languages, and physical traits", body)


def _step4():
    body = (
        '<p class="step-desc">Choose your character class. Your class defines your role, '
        'abilities, and advancement. Check that your ability scores meet the class minimums '
        'before choosing. Some races cannot take certain classes.</p>'
        + _rules([
            "Your HIGHEST ability score should match (or exceed) the class prime requisite for best XP gain",
            "If the prime requisite is 16+, you gain +10% XP; 6 or less = −10% XP penalty",
            "Priests must have Wisdom 9+; Wizards must have Intelligence 9+",
            "Paladins need Strength 12, Wisdom 13, Intelligence 9, Charisma 17 — the strictest requirements",
            "Check Table 13 for exact minimums for every class",
        ])
        + _links(
            ("Class Overview", "PHB/DD01456.htm"),
            ("Class Ability Minimums (Table 13)", "PHB/DD01458.htm"),
            ("Multi-Class / Dual-Class Rules", "PHB/DD01511.htm"),
        )
        + '<p class="section-label" style="margin-top:14px">Warriors</p>'
        + _class_table([
            ("Fighter",  "PHB/DD01462.htm", "Str 9"),
            ("Paladin",  "PHB/DD01464.htm", "Str 12, Wis 13, Int 9, Cha 17"),
            ("Ranger",   "PHB/DD01466.htm", "Str 13, Dex 13, Con 14, Wis 14"),
        ])
        + '<p class="section-label" style="margin-top:10px">Wizards</p>'
        + _class_table([
            ("Mage",               "PHB/DD01472.htm", "Int 9"),
            ("Specialist Wizard",  "PHB/DD01475.htm", "Higher Int + school reqs"),
            ("Illusionist",        "PHB/DD01476.htm", "Dex 16, Int 15"),
        ])
        + '<p class="section-label" style="margin-top:10px">Priests</p>'
        + _class_table([
            ("Cleric",             "PHB/DD01480.htm", "Wis 9"),
            ("Druid",              "PHB/DD01489.htm", "Wis 12, Cha 15"),
            ("Priest of Mythos",   "PHB/DD01481.htm", "Wis 9 + DM-defined"),
        ])
        + '<p class="section-label" style="margin-top:10px">Rogues</p>'
        + _class_table([
            ("Thief", "PHB/DD01500.htm", "Dex 9"),
            ("Bard",  "PHB/DD01508.htm", "Dex 12, Int 13, Cha 15"),
        ])
        + _links(
            ("Warrior XP Table (Table 14)", "PHB/DD01460.htm"),
            ("Wizard XP Table (Table 20)", "PHB/DD01470.htm"),
            ("Priest XP Table (Table 23)", "PHB/DD01478.htm"),
            ("Rogue XP Table (Table 25)", "PHB/DD01499.htm"),
            ("Specialist Requirements (Table 22)", "PHB/DD01474.htm"),
        )
    )
    return _step(4, "Choose a Class", "Defines your role, HD, THAC0, saves, and abilities", body)


def _step5():
    body = (
        '<p class="step-desc">Based on your class and Constitution score, calculate your starting hit points. '
        'Roll your Hit Die once. Constitution modifiers (positive or negative) are added to each die roll.</p>'
        + _rules([
            "Fighter / Paladin / Ranger: d10 per level",
            "Cleric / Druid / Priest of Mythos: d8 per level",
            "Thief / Bard: d6 per level",
            "Wizard (all): d4 per level",
            "Constitution HP adjustment applies to every Hit Die roll (Warriors: full bonus always)",
            "Con 15 = +1 HP/die · Con 16 = +2 · Con 17 = +3 (Warriors only) · Con 18 = +4 (Warriors only)",
            "Negative Con penalties (Con 6 = −1, Con 5 = −2, Con 4 = −3, Con 3 = −4) apply to all classes",
            "Minimum 1 HP per die after all modifiers",
        ])
        + _links(
            ("Constitution Table (Table 3)", "PHB/DD01430.htm"),
            ("Warrior Levels & HD (Table 14)", "PHB/DD01460.htm"),
            ("Wizard Levels & HD (Table 20)", "PHB/DD01470.htm"),
            ("Priest Levels & HD (Table 23)", "PHB/DD01478.htm"),
            ("Rogue Levels & HD (Table 25)", "PHB/DD01499.htm"),
        )
    )
    return _step(5, "Roll Hit Points", "Your Constitution score modifies every Hit Die", body)


def _step6():
    body = (
        '<p class="step-desc">Choose your character\'s alignment — the moral and ethical framework '
        'they live by. Alignment affects interactions with magic items, clerical powers, '
        'and how NPCs react to your character.</p>'
        + _rules([
            "Nine alignments: LG, NG, CG, LN, TN, CN, LE, NE, CE",
            "Paladins must be Lawful Good — this is non-negotiable",
            "Rangers must be Good (LG, NG, or CG)",
            "Druids must be True Neutral (TN)",
            "Bards must be Neutral in at least one axis",
            "Clerics must match their deity's alignment (or be within one step for most mythoi)",
            "Changing alignment is a serious in-game event with mechanical consequences",
        ])
        + _links(
            ("Alignment Overview", "PHB/DD01515.htm"),
            ("Alignment Combinations (Nine Types)", "PHB/DD01518.htm"),
            ("Playing Your Alignment", "PHB/DD01520.htm"),
            ("Changing Alignment", "PHB/DD01521.htm"),
        )
    )
    return _step(6, "Choose an Alignment", "Your moral and ethical philosophy", body)


def _step7():
    body = (
        '<p class="step-desc">Assign weapon and non-weapon proficiency slots. '
        'Weapon proficiencies determine which weapons you can use without penalty. '
        'Non-weapon proficiencies represent skills and background knowledge.</p>'
        + _rules([
            "Each class starts with a set number of weapon slots and non-weapon slots (see Table 34)",
            "Using a non-proficient weapon: −2 to hit for Warriors, −3 for Priests, −3 for Rogues, −5 for Wizards",
            "Warriors may take Weapon Specialization (costs 2 slots) — Fighter-only, one weapon only",
            "Non-weapon proficiencies use a group system; cross-group profs cost one extra slot",
            "Additional slots are gained as you level up — note how often for your class",
            "Secondary Skills (simpler alternative to NWPs) may be chosen instead if the DM allows",
        ])
        + _links(
            ("Proficiency Overview", "PHB/DD01522.htm"),
            ("Proficiency Slots (Table 34)", "PHB/DD01524.htm"),
            ("Weapon Proficiencies", "PHB/DD01526.htm"),
            ("Weapon Specialization", "PHB/DD01530.htm"),
            ("Non-Weapon Proficiency Groups (Table 37)", "PHB/DD01538.htm"),
            ("NWP Crossover Costs (Table 38)", "PHB/DD01539.htm"),
            ("NWP Descriptions (A–Z)", "PHB/DD01541.htm"),
            ("Secondary Skills (Table 36)", "PHB/DD01536.htm"),
        )
    )
    return _step(7, "Choose Proficiencies", "Weapon proficiencies and background skills", body, optional=True)


def _step8():
    body = (
        '<p class="step-desc">Roll your starting gold based on your class, then spend it on equipment. '
        'Choose armor that matches your class restrictions, weapons you are proficient with, '
        'and adventuring gear for your first expedition.</p>'
        + _rules([
            "Starting gold is rolled on Table 43 — different dice per class group",
            "Fighters / Paladins / Rangers: 5d4 × 10 gp",
            "Wizards / Specialists: 2d4 × 10 gp",
            "Priests / Druids: 3d6 × 10 gp",
            "Rogues (Thief / Bard): 2d6 × 10 gp",
            "Wizards cannot wear armor; Druids are limited to leather, padded, and shields",
            "Note your base AC: no armor = AC 10; adjust for Dexterity reaction/defense bonus",
            "Calculate encumbrance — your Strength determines weight allowances",
        ])
        + _links(
            ("Starting Money Overview", "PHB/DD01612.htm"),
            ("Starting Gold by Class (Table 43)", "PHB/DD01613.htm"),
            ("Equipment Lists (Table 44)", "PHB/DD01614.htm"),
            ("Armor Costs", "PHB/DD01623.htm"),
            ("Weapons List", "PHB/DD01624.htm"),
            ("Miscellaneous Gear", "PHB/DD01629.htm"),
            ("Missile Weapon Ranges (Table 45)", "PHB/DD01625.htm"),
        )
    )
    return _step(8, "Buy Starting Equipment", "Roll gold, then outfit your character", body)


def _step9():
    body = (
        '<p class="step-desc">If your character is a wizard (mage, specialist, illusionist), '
        'you start with four spells in your spellbook: Read Magic plus three chosen spells from 1st level. '
        'If you are a cleric, druid, or bard, you can cast any spell of the appropriate level — '
        'you do not prepare a fixed list at 1st level the same way.</p>'
        + _rules([
            "Wizards: receive Read Magic + 3 spells at 1st level; record these in your spellbook",
            "Wizards can only cast spells from their spellbook (must memorize them each day)",
            "Specialists: +1 spell per level from their school; cannot learn opposition school spells",
            "Clerics / Druids: pray each morning to receive all spells of the appropriate level",
            "Bards: use Wizard spell list; check Table 32 for spells per day",
            "Paladins: gain spell access at level 9 (1st level Priest spells only)",
            "Rangers: gain spell access at level 8 (1st level Druid spells only)",
            "Verify Intelligence score allows learning the desired number and level of spells (Table 4)",
        ])
        + _links(
            ("Magic Chapter Overview", "PHB/DD01646.htm"),
            ("Wizard Spell Progression (Table 21)", "PHB/DD01471.htm"),
            ("Priest Spell Progression (Table 24)", "PHB/DD01479.htm"),
            ("Bard Spell Progression (Table 32)", "PHB/DD01509.htm"),
            ("Paladin Spells (Table 17)", "PHB/DD01465.htm"),
            ("Ranger Spells (Table 18)", "PHB/DD01467.htm"),
            ("Intelligence & Spell Learning (Table 4)", "PHB/DD01432.htm"),
            ("Wizard Spell List (Appendix 1)", "PHB/DD01790.htm"),
            ("Priest Spell List (Appendix 4)", "PHB/DD02120.htm"),
        )
    )
    return _step(9, "Choose Starting Spells", "For arcane and divine spellcasters only", body, optional=True)


def _step10():
    body = (
        '<p class="step-desc">Determine your THAC0 (To Hit Armor Class 0) and saving throws. '
        'These are set by your class and level — at 1st level they come directly from your class tables. '
        'For Thieves, also distribute thieving skill points.</p>'
        + _rules([
            "THAC0 at 1st level: Warriors = 20, Priests = 20, Rogues = 20, Wizards = 20",
            "All classes start at THAC0 20 at 1st level; Warriors improve fastest (−1 per level)",
            "Strength Hit Probability adjustment modifies all melee attack rolls",
            "Saving throw categories: PPD, RSW, PP, BW, Spell — see your class table",
            "Thieves: distribute 60 bonus points among thieving skills (max 30 to any one skill at 1st level)",
            "Thieving skill base scores are modified by race (Table 27) and Dexterity (Table 28)",
        ])
        + _links(
            ("Warrior THAC0 (Table 14)", "PHB/DD01460.htm"),
            ("Wizard THAC0 (Table 20)", "PHB/DD01470.htm"),
            ("Priest THAC0 (Table 23)", "PHB/DD01478.htm"),
            ("Rogue THAC0 (Table 25)", "PHB/DD01499.htm"),
            ("Thief Skill Bases (Table 26)", "PHB/DD01501.htm"),
            ("Thief Racial Adjustments (Table 27)", "PHB/DD01502.htm"),
            ("Thief Dexterity Adjustments (Table 28)", "PHB/DD01503.htm"),
        )
    )
    return _step(10, "Record THAC0, Saves & Thief Skills", "Combat accuracy, resistances, and class-specific skills", body)


def _step11():
    body = (
        '<p class="step-desc">Fill in the finishing touches that make your character a person, '
        'not just a stat block. Choose languages, name your character, note their background, '
        'and record all remaining derived values.</p>'
        + _rules([
            "Languages: Common + racial tongue + number of extra languages equal to your Intelligence language allowance",
            "Charisma sets your Maximum Henchmen (Table 6) and NPC Loyalty Base (Table 6)",
            "Write down your base movement rate (MV): Human = 12, Dwarf/Gnome/Halfling = 6, Elf = 12",
            "Note class-specific starting features (e.g., Ranger's tracking, Paladin's Lay on Hands, Bard abilities)",
            "Set your starting XP to 0 and note the amount needed to reach level 2",
            "Review your character for any rule conflicts before play begins",
        ])
        + _links(
            ("Intelligence & Languages (Table 4)", "PHB/DD01432.htm"),
            ("Charisma (Table 6)", "PHB/DD01436.htm"),
            ("Other Details — Misc. Characteristics", "PHB/DD01452.htm"),
            ("Bard Abilities (Table 33)", "PHB/DD01510.htm"),
            ("Ranger Abilities (Table 18)", "PHB/DD01467.htm"),
            ("Paladin Details", "PHB/DD01464.htm"),
        )
    )
    return _step(11, "Finishing Touches", "Languages, personality, movement, and special features", body)


# ── Assemble ───────────────────────────────────────────────────────────────────

def generate() -> str:
    steps = [
        _step1(), _step2(), _step3(), _step4(),
        _step5(), _step6(), _step7(), _step8(),
        _step9(), _step10(), _step11(),
    ]

    nav_items = ""
    for i, label in enumerate([
        "Ability Scores", "Choose Race", "Racial Details",
        "Choose Class", "Hit Points", "Alignment",
        "Proficiencies", "Equipment", "Spells",
        "THAC0 & Saves", "Finishing Touches",
    ], 1):
        nav_items += f'<a class="nav-step" href="#step-{i}">{i}. {e(label)}</a>'

    css = f"""
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{ background: #1a1c26; font-family: "Segoe UI", system-ui, sans-serif;
             font-size: 13px; color: #c8cad8; }}

      /* ── Top Bar ── */
      .top-bar {{ position: sticky; top: 0; z-index: 100; background: #13151f;
                  border-bottom: 1px solid #2a2d3e; padding: 10px 14px;
                  display: flex; flex-direction: column; gap: 8px; }}
      .search-row {{ display: flex; gap: 8px; align-items: center; }}
      #search {{ flex: 1; background: #23263a; border: 1px solid #383c52;
                 border-radius: 6px; color: #e0e2f0; padding: 7px 12px;
                 font-size: 13px; outline: none; }}
      #search:focus {{ border-color: {ACCENT}; }}
      #clear-btn {{ background: #23263a; border: 1px solid #383c52; border-radius: 6px;
                    color: #9ca3c0; padding: 6px 12px; cursor: pointer; font-size: 12px; }}
      .step-nav {{ display: flex; gap: 5px; flex-wrap: wrap; }}
      .nav-step {{ background: #1e2138; border: 1px solid #2a2e45; border-radius: 5px;
                   color: #7a84a8; padding: 3px 9px; font-size: 10.5px; font-weight: 600;
                   text-decoration: none; letter-spacing: .03em; transition: all .12s; }}
      .nav-step:hover {{ background: #252a42; color: {ACCENT}; border-color: {ACCENT_DIM}; }}

      /* ── Steps ── */
      .steps {{ max-width: 860px; margin: 0 auto; padding: 18px 16px 40px; }}

      .step {{ background: #21243a; border: 1px solid #2a2e45; border-radius: 8px;
               margin-bottom: 14px; overflow: hidden; }}

      .step-header {{ padding: 13px 16px; background: #1c1f32;
                      border-bottom: 1px solid #2a2e45; }}
      .step-num {{ width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
                   background: {ACCENT_BG}; border: 2px solid {ACCENT_DIM};
                   color: {ACCENT}; font-size: 15px; font-weight: 800;
                   display: flex; align-items: center; justify-content: center; }}
      .step-title-line {{ display: flex; align-items: center; gap: 20px; }}
      .step-title {{ font-size: 16.5px; font-weight: 700; color: #e8eaf0;
                     letter-spacing: .03em; }}
      .step-sub {{ font-size: 12px; color: #5a6080; margin: 5px 0 0 54px;
                   font-style: italic; line-height: 1.4; }}
      .opt-badge {{ background: #1f1430; border: 1px solid #5c3a8a; border-radius: 4px;
                    color: #a76bcc; font-size: 9.5px; font-weight: 700; padding: 2px 6px;
                    letter-spacing: .06em; text-transform: uppercase; }}

      .step-body {{ padding: 16px; display: flex; flex-direction: column; gap: 12px; }}

      .step-desc {{ color: #b0b4cc; line-height: 1.65; font-size: 12.5px; }}

      /* ── Rules list ── */
      .rule-list {{ display: flex; flex-direction: column; gap: 3px; }}
      .rule-row {{ display: flex; gap: 8px; align-items: baseline; padding: 5px 10px;
                   border-radius: 4px; font-size: 12px; line-height: 1.55; color: #c0c4d8; }}
      .rule-row:nth-child(odd) {{ background: #1e2138; }}
      .bullet {{ color: {ACCENT_DIM}; flex-shrink: 0; font-size: 10px; }}

      /* ── Section label ── */
      .section-label {{ color: #5a6080; font-size: 10px; font-weight: 700;
                        letter-spacing: .09em; text-transform: uppercase; margin-bottom: 6px; }}

      /* ── Class grid ── */
      .class-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }}
      .class-card {{ background: #1c1f32; border: 1px solid #2a2e45; border-radius: 6px;
                     padding: 10px 12px; }}
      .class-link {{ color: {ACCENT}; text-decoration: none; font-weight: 700;
                     font-size: 13px; display: block; margin-bottom: 4px; }}
      .class-link:hover {{ color: #e8c26e; text-decoration: underline; }}
      .class-req {{ color: #5a6080; font-size: 11px; font-style: italic; }}

      /* ── PHB link chips ── */
      .link-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
      .phb-link {{ display: inline-flex; align-items: center; gap: 7px;
                   background: #1c1f32; border: 1px solid {ACCENT_DIM};
                   border-radius: 6px; padding: 6px 11px 6px 7px; color: #c2aa68;
                   text-decoration: none; font-size: 11.5px; font-weight: 600;
                   line-height: 1; transition: all .12s; white-space: nowrap; }}
      .phb-link:hover {{ background: {ACCENT_BG}; border-color: {ACCENT}; color: {ACCENT}; }}
      .phb-badge {{ display: inline-flex; align-items: center; justify-content: center;
                    background: {ACCENT_DIM}; color: #f0dca0; font-size: 8.5px; font-weight: 800;
                    border-radius: 3px; padding: 3px 5px; line-height: 1; letter-spacing: .08em; }}

      /* ── Search hidden ── */
      .step[style*="display:none"], .step[style*="display: none"] {{ display: none !important; }}
    """

    script = """
      const steps = Array.from(document.querySelectorAll('.step'));
      document.getElementById('search').addEventListener('input', function() {
        const q = this.value.toLowerCase();
        steps.forEach(s => {
          s.style.display = (!q || s.textContent.toLowerCase().includes(q)) ? '' : 'none';
        });
      });
      document.getElementById('clear-btn').addEventListener('click', function() {
        document.getElementById('search').value = '';
        steps.forEach(s => s.style.display = '');
      });
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Character Creation — AD&D 2nd Edition</title>
<style>{css}</style>
</head>
<body>
<div class="top-bar">
  <div class="search-row">
    <input id="search" type="text" placeholder="Search steps, classes, rules…" autocomplete="off">
    <button id="clear-btn">Clear</button>
  </div>
  <div class="step-nav">{nav_items}</div>
</div>
<div class="steps">
{"".join(steps)}
</div>
<script>{script}</script>
</body>
</html>"""

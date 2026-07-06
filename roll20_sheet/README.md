# Roll20 2e sheet (adopted community sheet + app import)

The campaign's Roll20 character sheet: the fuller community AD&D 2e sheet
(TheAaronSheet-based) that matches the house rules — **ascending AC, attack bonus
(no THAC0), Perception as a 7th stat, initiative `1d10 + weapon speed / casting time`
to the turn tracker**, and it calls Wisdom **"Willpower"** — with a whole-character
import bolted on so the app's Character Builder fills it in one paste.

## Files
- **`sheet.html`** — the **complete** sheet: layout + roll templates + all worker
  scripts (TheAaronSheet, the ability/gear/save/stat workers) **and** the bulk-import
  worker + the Settings-tab Import box, all in one file. Paste into Roll20's **HTML** box.
- **`sheet.css`** — styling. Paste into Roll20's **CSS** box.

## Install (Pro required — you have it)
1. In your game: **Settings → Game Settings → Character Sheet Template → Custom**.
2. Paste **`sheet.html`** into the **HTML Layout** box.
3. Paste **`sheet.css`** into the **CSS Styling** box. Save.

## Exporting a character from the app
1. Build a character → **Review** → **⎘ Export to Roll20**. The JSON is copied to your clipboard.
2. On a **freshly-created** Roll20 character, open the **Settings** tab → **Import from the
   Character Builder**, paste, click **Import character**. All fields plus the Weapons /
   Proficiencies / Gear / Spell rows fill in, and the sheet's workers compute ability mods,
   AC, and encumbrance.

## Import field mapping (app JSON → sheet attribute)
The app emits a clean JSON ([roll20_export.py](../roll20_export.py)); the import worker (inside
`sheet.html`, `on("clicked:importall")`) maps it:

| App JSON | Sheet attribute | Notes |
|---|---|---|
| `character_name` / `player_race` / `player_class` / `player_level` | `character_name` / `race` / `classes` / `level` | |
| `alignment` / `gender` | `alignment` / `sex` | |
| `strength` (+ `strength_exceptional`) | `strength` | 18/xx → the sheet's decimal (18.50…18.999) |
| `dexterity` `constitution` `intelligence` `charisma` `perception` | same names | |
| `willpower` | `willpower` | = the app's Wisdom score |
| `hp` / `hp_max` | `hp` / `hp_max` | starts full |
| `attack_base` | `attackbase` | 20 − THAC0 |
| `armor_base` / `armor_bonus` | `acbase` / `acarmor` | sheet adds Dex → ascending AC |
| `move` | `speed` | |
| `save_ppd` `save_rsw` `save_pp` `save_bw` `save_spell` | `saveppd` `saversw` `savepp` `savebw` `saves` | |
| `gp` / `sp` / `cp` | `wealthgp` / `wealthsp` / `wealthcp` | from `money_cp` |
| `weapons[]` | `repeating_weapons` (`wname` `whit` `wdambase` `wspeed` `wtype` `wrange`) | damage normalized to `NdM` |
| `weapon_profs[]` | `repeating_wps` (`wpsname`) | trained-with list |
| `nwp[]` | `repeating_nwp` (`nwpname` `nwpattr`=`@{stat}` `nwpbase`) | total = stat + base |
| `gear[]` | `repeating_gear1` (`g1name` `g1quantity` `g1weight` `g1cost`) | |
| `spells[]` | `repeating_spells{level}` (`spellName` `spellSchool` `spellRange` `spellCastingTime`) | routed by level; casting time feeds spell initiative |

## Notes / provenance
- The base sheet + TheAaronSheet worker library are reproduced from the community "2.neal"
  2e sheet (by its author; TheAaronSheet © The Aaron). Only the **Import** box and the
  `importall` worker are our additions.
- The sheet's original *per-spell* JSON-paste importers were left out — the whole-character
  Import supersedes them. (The per-spell JSON field still shows on each spell row but is inert;
  ask if you want that legacy feature restored.)

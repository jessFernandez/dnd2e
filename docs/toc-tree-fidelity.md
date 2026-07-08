# Feature plan: faithful nested TOC tree (match the original site)

Status: **DONE (2026-07-08)** · Last updated: 2026-07-08

## Outcome

Implemented via the site's real tree source, not a heuristic:

- The site builds its sidebar from a nested XML (`pw_toc_6.xml`), loaded by a JS
  tree widget — **not** the flat alphabetical index (`pw_index_4.htm`) the original
  scraper read. That was the whole reason the old `topic` data never matched.
- `scripts/build_toc_tree.py` fetches + parses that XML into a new **`toc_tree`**
  table (id, parent_id, position, name, page_url; folders have a NULL page_url).
- `db.toc_tree` + `toc.build_tree` (pure, tested) reconstruct the nesting;
  `app.py._load_topics` renders it (arbitrary depth), falling back to the flat
  `toc_entries` layout if `toc_tree` is absent.
- The tree references ~1,180 finer-grained pages the old alphabetical scrape
  missed (PHB +558, TM +332, …), so those were scraped into `pages`/`pages_fts` —
  a bonus content gain, and required so tree links resolve.

Verified the reconstructed CT / PHB trees match the site screenshots exactly.

The original analysis that led here is kept below for context.

---


The browse sidebar renders **Book → Chapter → flat pages**. The original site
(regalgoblins.com/2erules) renders a deeper tree: each chapter contains **named
sub-folders** (e.g. Chapter 3 → *Battlefields*, *Terrain Types*, *Generating a
Battlefield* …, each holding its pages). We want to match that.

## Why the obvious approach doesn't work (and was reverted)

An attempt to derive the nesting from the existing `toc_entries.topic` column was
built and **reverted 2026-07-07** because it's inconsistent across books:

- The scraper's `parse_toc` ([scripts/scraper.py](../scripts/scraper.py)) walks the
  source TOC **linearly**: every `<strong>` sets the "current topic" and each
  following `<span onclick="sF('BOOK#PAGE')">` link becomes a subtopic under it.
  So `topic` is just *"the last bold heading before this link"* — a flat, one-level
  heading list, **not** the site's real nested folder tree.
- That heading list happens to line up with the tree in the **PHB** (topics like
  `Warriors` map to folders) but is polluted in **Combat & Tactics**: many pages
  have their *entire subtopic as their topic*
  (`topic='Dungeons or Caves-- Basic Battlefield (Combat and Tactics)'`), so they
  can't group, while a shared `topic='Battlefields'` is spread over
  **non-consecutive** rows. Result: misleading partial nesting, arguably worse
  than a clean flat list.
- The real grouping signal in CT is the **subtopic suffix** (`-- Terrain Type`,
  `-- Basic Battlefield`) — a *different* signal than the PHB uses. **No single
  heuristic over the current data matches the site across all books**, because the
  site's tree was flattened away at scrape time.

## The real fix: re-scrape the hierarchy

The site clearly has the nested structure (it renders the folder tree); the
scraper just didn't capture it. Plan:

1. **Inspect the source TOC first (feasibility gate).** Confirm regalgoblins.com
   is still reachable and check how its TOC encodes the tree — nested `<ul>`/`<li>`,
   indentation/depth classes, or a separate tree data source (JSON). This decides
   whether re-scraping can recover the hierarchy at all.
2. **Capture depth/parent in the scrape.** Enhance `parse_toc` to record each
   entry's parent (or nesting depth) instead of only the last bold heading.
3. **Schema.** Add a `parent_id` (or `depth`) column to `toc_entries`; keep the
   existing columns so nothing else breaks. Regenerate `dnd2e.db`.
4. **Render.** Update `toc.py` to build the real nested tree from parent/depth and
   `app.py._load_topics` to render arbitrary-depth folders (and generalize
   `_sync_tree_selection` to expand all ancestors — a one-line loop).
5. **Verify** against several books (PHB, CT, DMG, MM) — not just one — since the
   whole point is cross-book fidelity.

## What the reverted attempt got right (reusable when we return)

The rendering approach was sound and can be reused once the data is real:
- keep `chapter["entries"]` flat for Prev/Next reading order, add a nested view
  alongside it;
- fold a group into a folder only when it has >1 page (single pages stay leaves);
- `_sync_tree_selection` must walk **all** ancestors, not a fixed 2 levels.

The blocker was never the rendering — it's that the source data doesn't carry the
tree. Fix the scrape, then the rest is straightforward.

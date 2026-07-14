# Navigation controller extraction — plan

**Status:** planned. Phase 1 in progress.

## Goal

Move the navigation *decisions* — link parsing, destination classification, link
routing, and the browse-pane show/hide policy — out of `MainWindow` and into
pure, Qt-free functions, leaving the Qt methods as thin "compute the decision,
perform the side effect" shells. This mirrors how `ask_controller.py` was pulled
out of the `_ask_*` methods: the pure logic becomes directly testable, and
`app.py` shrinks toward orchestration only.

## Where it lands

**Extend `navigation.py`** — do **not** add a new module. It already exists, is
the pure home of `History`, is imported by `app.py`, and is already listed in
`dnd2e.spec`. A parallel `nav_controller.py` would be a confusing near-duplicate.
So `navigation.py` becomes the single pure navigation module: state machine **+**
grammar **+** routing **+** pane policy. No `dnd2e.spec` change needed.

## What moves vs. what stays

| Concern | Today (`app.py`) | After |
|---|---|---|
| History state machine | `navigation.History` | unchanged |
| Link path → destination | `_link_to_destination` (static) | `navigation.link_to_destination(path)` |
| Full-width classification | `_takes_full_width` + `_FULLWIDTH_SCREENS` | `navigation.takes_full_width(dest)` + constant |
| Destination kind (dispatch) | implicit in `_render_destination` if-ladder | `navigation.classify(dest) -> Kind` |
| Raw link → intended action | `_on_content_navigate` if-ladder | `navigation.route_link(url, ...) -> Route` |
| Pane policy (reveal/hide) | spread across 3 methods | `navigation.pane_action(dest, trigger) -> Pane` |
| Rendering, show/hide sidebar, tab open, history push | Qt methods | **stay in `app.py`** (thin) |

## New pure API (sketch)

```python
# navigation.py
FULLWIDTH_SCREENS = frozenset({"splash", "dmscreen", "actions",
                               "spells", "charactermancer", "ask"})

def link_to_destination(path: str) -> str: ...      # "toc/PHB" -> "toc:PHB"
def takes_full_width(dest: str) -> bool: ...        # the predicate from cleanup #2
def classify(dest: str) -> Kind: ...                # SCREEN | TOC | PAGE | PROFICIENCIES | ASK ...

# The link if-ladder becomes a pure tagged return the Qt layer switches on:
#   Ask(q) | AskSetModel(m) | AskRefresh | AskStop | CmAction(s) | NewTab(dest) | Navigate(dest)
def route_link(url: str, *, on_jarvis_page: bool) -> Route: ...

# The tri-part pane policy as one truth table instead of three scattered ifs:
class Trigger(Enum): LINK; NAVIGATE; TAB_CHANGE
class Pane(Enum): OPEN; CLOSE; LEAVE
def pane_action(dest: str, trigger: Trigger) -> Pane: ...
```

`pane_action` is the payoff — the whole policy in one place: `LINK`+book→`OPEN`,
`NAVIGATE`/`TAB_CHANGE`+full-width→`CLOSE`, everything else→`LEAVE`.
`_reveal_nav_for`, `_navigate`'s hide, and `_on_tab_changed` all collapse to
"compute `pane_action`, then open/close/nothing."

## Migration — phased, each step ships green

1. **Grammar.** Move `link_to_destination` + `takes_full_width` + the constant
   into `navigation.py`; `app.py` delegates via thin wrappers so nothing else
   changes. Add direct tests. *Small, near-zero risk.*
2. **Pane policy.** Introduce `Trigger`/`Pane` + `pane_action`; rewrite the three
   pane sites to use it. Port the `test_nav_reveal.py` decision assertions onto
   `pane_action` directly (they simplify — no SimpleNamespace for the decision).
   *Small.*
3. **Link routing.** Introduce `Route` + `route_link`; shrink `_on_content_navigate`
   to a `match route_link(...)` that performs side effects. Biggest single step —
   the long if-ladder. *Medium; review carefully.*
4. **(Optional) Dispatch.** Have `_render_destination` consult `classify()` instead
   of re-parsing prefixes. *Polish; skip if it doesn't pull its weight.*

## Test plan

Most new tests become pure function tests (no Qt stand-ins): table-driven tests
for `pane_action` over dest×trigger, `route_link` over every prefix, `classify`,
and `link_to_destination`. The existing `test_nav_reveal.py` wiring tests stay as
a thin integration check that `MainWindow` performs the right side effect per
decision — but shrink.

## Risks / non-goals

- `route_link` is the risk surface: the special routes (`ask/`, `ask-setmodel/`,
  `cm/`, `newtab/`, the jarvis-page branch) must map exactly, including
  `unquote`/`.strip()` handling. Mitigation: do phase 3 alone, in its own commit,
  with `route_link` tests written **before** touching `_on_content_navigate`.
- **Not** touching `History`, rendering, session save/restore, or the tree widget.
  Decisions only.
- No `dnd2e.spec` change (extending an already-listed module).

## Effort

~½ day. Phases 1–2 are ~an hour and safe; phase 3 is the real work and wants the
`route_link` tests first. Land as 2–3 commits (grammar+policy, then routing),
separate from the icon / nav-reveal work.

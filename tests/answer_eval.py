"""Answer-quality evaluation for Jarvis — the whole-pipeline gate.

Retrieval eval (test_retrieval_eval.py) checks the right page is *found*. This
checks the generated answer is actually *good*: it (a) cites the correct rule
page and (b) states the must-have facts. It runs the real pipeline against a
local Ollama model, so it's slow and non-deterministic — a deliberate harness,
not part of the fast unit suite.

Run:  python tests/answer_eval.py [N]      (N = limit to first N cases)

Fact checks are lenient (any synonym in a group satisfies it); the goal is to
catch wrong/empty/ungrounded answers and track quality as we tune the prompt,
not to grade prose.
"""
import os
import re
import sys
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # repo root

import rules_agent
from rules_agent import AskWorker, ollama_status, pick_default_model
from golden_retrieval import GOLDEN

DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")
GOLD = dict(GOLDEN)   # question -> gold page_urls

# question -> fact groups; the answer must contain ≥1 phrase from EACH group.
ANSWER_CASES = [
    ("how does thac0 work",
     [["thac0"], ["armor class", " ac ", "ac)"], ["d20", "20-sided", "roll"],
      ["subtract", "minus", "- ac", "target number", "to hit", "to-hit"]]),
    ("how do i roll for stats",
     [["3d6", "three six-sided", "three d6"], ["six ", "6 ability", "each ability"],
      ["strength", "dexterity", "ability score"]]),
    ("what are saving throws",
     [["saving throw", "save"], ["d20", "roll", "20-sided"],
      ["equal", "higher", "meet", "exceed", "or greater", "greater than"]]),
    ("how does initiative work",
     [["initiative"], ["1d10", "d10", "die", "dice", "roll"],
      ["low", "lower", "lowest", "first", "before"]]),
    ("how does turning undead work",
     [["turn"], ["undead"], ["priest", "cleric"], ["2d6", "roll", "table", "d20"]]),
    ("how do i cast a spell",
     [["spell"], ["cast"],
      ["component", "verbal", "somatic", "material", "memoriz", "initiative", "casting time"]]),
    ("how does surprise work",
     [["surprise"], ["1d10", "d10", "roll", "die"]]),
    ("how does infravision work",
     [["infravision"], ["60", "sixty", "heat", "warm", "dark"]]),
    ("what does charisma do",
     [["charisma"], ["reaction", "henchmen", "loyalty", "follower", "leadership", "npc"]]),
    ("how does falling damage work",
     [["fall"], ["1d6", "d6", "die"], ["10", "ten", "foot", "feet"]]),
    ("how does poison work",
     [["poison"], ["saving throw", "save"], ["strength", "onset", "damage", "death", "die"]]),
    ("how do i multiclass",
     [["multi-class", "multiclass", "multi class"], ["experience", "xp", "level"],
      ["divide", "split", "share", "evenly", "equally", "between"]]),
]

_URL_RE = re.compile(r"dnd:///([A-Za-z0-9/._#\-]+)")


def cited_pages(answer: str):
    out = set()
    for m in _URL_RE.finditer(answer):
        out.add(m.group(1).split("#", 1)[0])
    return out


def fact_score(answer: str, groups):
    low = answer.lower()
    hit = sum(1 for g in groups if any(p.lower() in low for p in g))
    return hit, len(groups)


def looks_refused(answer: str) -> bool:
    low = answer.lower()
    return any(p in low for p in (
        "no information", "does not contain", "doesn't contain",
        "not provided", "cannot answer", "can't answer", "no relevant",
    )) and len(answer) < 400


def main():
    if not os.path.exists(DB):
        print("rulebook DB not found:", DB); return
    ok, models = ollama_status(timeout=2.0)
    if not ok or not models:
        print("Ollama not running / no models installed — start Ollama and pull a model."); return
    # Model: JARVIS_MODEL env overrides; else the app's default pick.
    want = os.environ.get("JARVIS_MODEL", "").strip()
    model = next((m for m in models if m.startswith(want)), want) if want else pick_default_model(models)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(ANSWER_CASES)
    cases = ANSWER_CASES[:limit]
    print(f"model: {model}   cases: {len(cases)}\n")

    cite_hits = grounded = 0
    fact_num = fact_den = 0
    for q, groups in cases:
        gold = set(GOLD.get(q, ()))
        worker = AskWorker(DB, model, q)
        answer = worker.answer_sync()
        cited = cited_pages(answer)
        cite_hit = bool(cited & gold)
        hit, tot = fact_score(answer, groups)
        refused = looks_refused(answer)
        cite_hits += cite_hit
        grounded += (not refused)
        fact_num += hit; fact_den += tot
        flag = "ok " if (cite_hit and hit == tot and not refused) else "!! "
        print(f"{flag} facts {hit}/{tot}  cite {'Y' if cite_hit else 'n'}"
              f"{'  REFUSED' if refused else ''}  | {q}")
        if flag == "!! ":
            miss = [g for g in groups if not any(p.lower() in answer.lower() for p in g)]
            if miss:
                print(f"       missing facts: {miss}")
            if not cite_hit:
                print(f"       cited {sorted(cited) or '—'}; wanted any of {sorted(gold)}")
    n = len(cases)
    print("\n" + "-" * 60)
    print(f"citation accuracy = {cite_hits/n:.0%}   fact coverage = {fact_num/fact_den:.0%}   "
          f"grounded (not refused) = {grounded/n:.0%}   (n={n})")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # emoji-safe console
    main()

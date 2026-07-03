"""Retrieval evaluation: does a plain-English question surface the right rule page?

This is the quality gate for Jarvis answers — RAG answer quality is bottlenecked
by retrieval, so each case asserts the deterministic (model-free) keyword search
lands a relevant page in the top results. Extend CASES as new gaps are found.
"""
import os
import pytest
import rules_agent
from rules_agent import AskWorker

DB = os.path.join(os.path.dirname(rules_agent.__file__), "dnd2e.db")

# (question, [acceptable keywords]) — pass if any retrieved page title contains any.
CASES = [
    ("how do i roll for stats",                     ["ability score"]),
    ("how does thac0 work",                         ["thac0"]),
    ("what are saving throws",                      ["saving throw"]),
    ("what does armor class do",                    ["armor class"]),
    ("how does initiative work",                    ["initiative"]),
    ("how do i grapple someone",                    ["wrestl", "grappl", "hold"]),
    ("how does surprise work",                      ["surprise"]),
    ("how do i multiclass",                         ["multi"]),
    ("how do proficiencies work",                   ["proficienc"]),
    ("how does experience work",                    ["experience", "award"]),
    ("how do i cast a spell",                       ["spell", "casting"]),
    ("how does movement work",                      ["movement", "move"]),
    ("how does turning undead work",                ["turn"]),
    ("how do i pick a lock",                        ["lock"]),
    ("how does falling damage work",                ["falling"]),
    ("what happens when i run out of hit points",   ["death", "dying", "dead"]),
    ("how does morale work",                        ["morale"]),
    ("how do i sneak attack",                       ["backstab"]),
    ("how do i hide in shadows",                    ["hide in shadows", "thieving", "camoflage"]),
    ("how do i resurrect someone",                  ["raise dead", "raising the dead", "resurrection"]),
    ("how do i disarm an opponent",                 ["disarm"]),
    ("how do i climb a wall",                       ["climb"]),
    ("how do i swim",                               ["swim"]),
    ("how does poison work",                        ["poison"]),
    ("how do i two weapon fight",                   ["two-weapon", "off-hand", "two weapon"]),
    ("how much can my character carry",             ["encumbr", "weight"]),
    ("how do i parry",                              ["parry"]),
    ("what does charisma do",                       ["charisma"]),
    ("how do henchmen work",                        ["henchmen"]),
    ("how do i gain a level",                       ["experience", "award", "advancement"]),
    ("how do i disbelieve an illusion",             ["illusion", "saving throw"]),
    ("how does infravision work",                   ["infravision"]),
]


@pytest.mark.skipif(not os.path.exists(DB), reason="rulebook database not present")
@pytest.mark.parametrize("question,keywords", CASES, ids=[c[0] for c in CASES])
def test_retrieval_surfaces_expected_page(question, keywords):
    worker = AskWorker(DB, "x", question)
    titles = [t.lower() for _u, t, _b, _x in worker._retrieve(question, phrases=[], full=0)]
    assert any(any(k in title for title in titles) for k in keywords), (
        f"{question!r}: no retrieved title matched {keywords}; got {titles[:5]}"
    )

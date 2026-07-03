"""Golden retrieval set + metrics for Jarvis.

RAG answer quality is bottlenecked by retrieval: if the page that actually holds
the answer never reaches the model, no amount of prompting saves the answer. So
we pin, for each common question, the specific rulebook page(s) that truly
contain the answer (verified by reading them), and measure how well the retriever
surfaces them — recall@k and mean reciprocal rank (MRR).

This is stronger than the old "a retrieved *title* contains a keyword" proxy,
which silently passed questions whose real answer page was never retrieved (e.g.
the thief-skill prose page vs. the thief-skill *tables* that share its keywords).

Each entry is (question, gold_urls): retrieval "hits" if ANY gold url appears.
Multiple urls are listed when several pages legitimately answer (e.g. the PHB and
DMG versions of the same rule, or a definition page plus its procedure page).
"""

# (question, (acceptable gold page_url, …))  — page_urls match the `pages` table.
GOLDEN = [
    ("how do i roll for stats",                   ("PHB/DD01422.htm", "PHB/DD01423.htm")),
    ("how does thac0 work",                       ("PHB/DD01671.htm", "PHB/DD01673.htm", "DMG/DD00395.htm")),
    ("what are saving throws",                    ("PHB/DD01669.htm", "PHB/DD01723.htm")),
    ("what does armor class do",                  ("PHB/DD01664.htm",)),
    ("how does initiative work",                  ("PHB/DD01686.htm", "PHB/DD01687.htm", "DMG/DD00403.htm")),
    ("how do i grapple someone",                  ("PHB/DD01704.htm", "CT/DD02679.htm")),
    ("how does surprise work",                    ("PHB/DD01757.htm", "PHB/DD01758.htm", "PHB/DD01670.htm", "DMG/DD00560.htm")),
    ("how do i multiclass",                       ("PHB/DD01511.htm", "PHB/DD01513.htm")),
    ("how do proficiencies work",                 ("PHB/DD01522.htm", "PHB/DD01523.htm")),
    ("how does experience work",                  ("PHB/DD01656.htm", "PHB/DD01658.htm", "DMG/DD00363.htm", "DMG/DD00372.htm")),
    ("how do i cast a spell",                     ("PHB/DD01652.htm", "CT/DD02426.htm")),
    ("how does movement work",                    ("PHB/DD01774.htm", "PHB/DD01773.htm", "PHB/DD01698.htm", "DMG/DD00422.htm")),
    ("how does turning undead work",              ("PHB/DD01733.htm", "PHB/DD01734.htm", "DMG/DD00467.htm")),
    ("how do i pick a lock",                      ("PHB/DD01505.htm",)),
    ("how does falling damage work",              ("PHB/DD01739.htm", "DMG/DD00486.htm")),
    ("what happens when i run out of hit points", ("PHB/DD01736.htm", "PHB/DD01747.htm", "DMG/DD00502.htm")),
    ("how does morale work",                      ("DMG/DD00476.htm", "DMG/DD00479.htm", "CT/DD02445.htm")),
    ("how do i sneak attack",                     ("PHB/DD01505.htm", "PHB/DD01506.htm")),
    ("how do i hide in shadows",                  ("PHB/DD01505.htm",)),
    ("how do i resurrect someone",                ("PHB/DD01751.htm", "DMG/DD00501.htm")),
    ("how do i disarm an opponent",               ("CT/DD02483.htm",)),
    ("how do i climb a wall",                     ("PHB/DD01780.htm", "PHB/DD01781.htm", "PHB/DD01784.htm", "PHB/DD01785.htm", "CT/DD02785.htm")),
    ("how do i swim",                             ("PHB/DD01778.htm",)),
    ("how does poison work",                      ("PHB/DD01742.htm", "DMG/DD00489.htm")),
    ("how do i two weapon fight",                 ("PHB/DD01697.htm", "CT/DD02649.htm")),
    ("how much can my character carry",           ("PHB/DD01636.htm", "PHB/DD01637.htm", "PHB/DD01638.htm", "PHB/DD01645.htm", "SP/DD03162.htm")),
    ("how do i parry",                            ("PHB/DD01721.htm", "DMG/DD00437.htm", "CT/DD02432.htm")),
    ("what does charisma do",                     ("PHB/DD01435.htm",)),
    ("how do henchmen work",                      ("DMG/DD00589.htm", "PHB/DD01764.htm")),
    ("how do i gain a level",                     ("DMG/DD00339.htm", "PHB/DD01659.htm", "DMG/DD00380.htm")),
    ("how do i disbelieve an illusion",           ("PHB/DD01650.htm",)),
    ("how does infravision work",                 ("PHB/DD01771.htm", "DMG/DD00617.htm", "DMG/DD00618.htm", "DMG/DD00619.htm")),
]


# ── metrics ───────────────────────────────────────────────────────────────────

def retrieved_urls(worker, question, k=12):
    """The retriever's ranked page_urls for a question (real pipeline, no model)."""
    rows = worker._retrieve(question, phrases=[], k=k, full=0)
    return [url for url, _title, _book, _text in rows]


def first_hit_rank(urls, gold):
    """1-based rank of the first gold url in `urls`, or None if absent."""
    gold = set(gold)
    for i, u in enumerate(urls, 1):
        if u in gold:
            return i
    return None


def recall_at_k(urls, gold, k):
    return 1.0 if first_hit_rank(urls[:k], gold) is not None else 0.0


def reciprocal_rank(urls, gold):
    r = first_hit_rank(urls, gold)
    return 1.0 / r if r else 0.0

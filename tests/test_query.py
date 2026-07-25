"""Unit tests for Jarvis query building (stopwords + synonym/phrase expansion)."""
from ask_retrieval import (
    terms, fts_query, fts_from_terms, title_is_query, query_stems,
)


def test_stopwords_removed():
    t = terms("how do i roll for stats")
    assert "how" not in t and "do" not in t and "for" not in t and "i" not in t
    assert "roll" in t


def test_synonym_expansion_stats():
    t = terms("stats")
    assert "ability" in t and "scores" in t


def test_synonym_phrase_hp():
    assert "hit points" in terms("hp")
    assert "hit dice" in terms("hp")


def test_shorthand_maps_to_rulebook_terms():
    assert "strength" in terms("str bonus")
    assert "armor class" in terms("what is my ac")
    assert "saving throw" in terms("what is my save")
    assert "backstab" in terms("sneak attack")
    assert "raise dead" in terms("how do i resurrect someone")


def test_fts_from_terms_quotes_and_ors():
    assert fts_from_terms(["ability", "scores"]) == '"ability" OR "scores"'


def test_fts_from_terms_dedups():
    assert fts_from_terms(["a", "a", "b"]).count('"a"') == 1


def test_fts_from_terms_empty_uses_fallback():
    assert fts_from_terms([], fallback="thac0") == '"thac0"'


def test_fts_query_never_empty():
    # even an all-stopword question yields a usable query
    assert fts_query("how do i").strip()


def test_prefix_matching_opt_in():
    # prefix=True lets the un-stemmed index match singular/plural & inflections
    q = fts_from_terms(["lock", "climbing"], prefix=True)
    assert "lock*" in q and "climbing*" in q
    # short tokens and phrases stay exact even with prefix on
    q2 = fts_from_terms(["hp", "hide in shadows"], prefix=True)
    assert '"hp"' in q2 and '"hide in shadows"' in q2
    # default (query-unit path) is unchanged: exact quoted terms
    assert fts_from_terms(["lock"]) == '"lock"'


def test_title_is_query_matches_canonical_page():
    stems = query_stems(["movement", "move"])
    assert title_is_query("Movement", stems)              # whole title is a query word
    assert not title_is_query("Movement in Melee", stems)  # "melee" isn't in the query
    # prefix/inflection: query stem "climb" covers the title word "Climbing"
    assert title_is_query("Climbing", query_stems(["climb", "wall"]))
    # unrelated title is not a match
    assert not title_is_query("Thieving Skill Explanations", query_stems(["hide", "shadows"]))

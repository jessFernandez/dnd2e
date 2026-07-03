"""Unit tests for Jarvis query building (stopwords + synonym/phrase expansion)."""
from rules_agent import _terms, _fts_query, _fts_from_terms, _title_is_query, _query_stems


def test_stopwords_removed():
    t = _terms("how do i roll for stats")
    assert "how" not in t and "do" not in t and "for" not in t and "i" not in t
    assert "roll" in t


def test_synonym_expansion_stats():
    t = _terms("stats")
    assert "ability" in t and "scores" in t


def test_synonym_phrase_hp():
    assert "hit points" in _terms("hp")
    assert "hit dice" in _terms("hp")


def test_shorthand_maps_to_rulebook_terms():
    assert "strength" in _terms("str bonus")
    assert "armor class" in _terms("what is my ac")
    assert "saving throw" in _terms("what is my save")
    assert "backstab" in _terms("sneak attack")
    assert "raise dead" in _terms("how do i resurrect someone")


def test_fts_from_terms_quotes_and_ors():
    assert _fts_from_terms(["ability", "scores"]) == '"ability" OR "scores"'


def test_fts_from_terms_dedups():
    assert _fts_from_terms(["a", "a", "b"]).count('"a"') == 1


def test_fts_from_terms_empty_uses_fallback():
    assert _fts_from_terms([], fallback="thac0") == '"thac0"'


def test_fts_query_never_empty():
    # even an all-stopword question yields a usable query
    assert _fts_query("how do i").strip()


def test_prefix_matching_opt_in():
    # prefix=True lets the un-stemmed index match singular/plural & inflections
    q = _fts_from_terms(["lock", "climbing"], prefix=True)
    assert "lock*" in q and "climbing*" in q
    # short tokens and phrases stay exact even with prefix on
    q2 = _fts_from_terms(["hp", "hide in shadows"], prefix=True)
    assert '"hp"' in q2 and '"hide in shadows"' in q2
    # default (query-unit path) is unchanged: exact quoted terms
    assert _fts_from_terms(["lock"]) == '"lock"'


def test_title_is_query_matches_canonical_page():
    stems = _query_stems(["movement", "move"])
    assert _title_is_query("Movement", stems)              # whole title is a query word
    assert not _title_is_query("Movement in Melee", stems)  # "melee" isn't in the query
    # prefix/inflection: query stem "climb" covers the title word "Climbing"
    assert _title_is_query("Climbing", _query_stems(["climb", "wall"]))
    # unrelated title is not a match
    assert not _title_is_query("Thieving Skill Explanations", _query_stems(["hide", "shadows"]))

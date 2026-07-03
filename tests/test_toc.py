"""Tests for toc.py — the TOC-to-chapter grouping (previously untested in-app)."""
import toc


def test_extract_chapter_name():
    assert toc.extract_chapter_name("Combat-- Chapter 9 (Player's Handbook)") == "Chapter 9: Combat"
    assert toc.extract_chapter_name("Backstab-- Part 2 (X)") == "Part 2: Backstab"
    assert toc.extract_chapter_name("Wizard Spell List-- Appendix 1 (X)") == "Appendix 1: Wizard Spell List"
    assert toc.extract_chapter_name("Fireball (PHB)") == "Fireball"     # no marker → strip "(…)"
    assert toc.extract_chapter_name("Plain") == "Plain"


def test_chapters_from_markers_with_intro():
    entries = [
        ("b/1", "Foreword (X)"),                 # pre-chapter → Introduction
        ("b/2", "Combat-- Chapter 9 (X)"),        # marker
        ("b/3", "THAC0 (X)"),
        ("b/4", "Magic-- Chapter 7 (X)"),         # marker
        ("b/5", "Fireball (X)"),
    ]
    markers = [("Combat-- Chapter 9 (X)", "b/2"), ("Magic-- Chapter 7 (X)", "b/4")]
    chapters = toc.chapters_from_markers(entries, markers)

    assert [c["name"] for c in chapters] == ["Introduction", "Chapter 9: Combat", "Chapter 7: Magic"]
    assert chapters[0]["entries"] == [("b/1", "Foreword (X)")]
    assert [u for u, _ in chapters[1]["entries"]] == ["b/2", "b/3"]
    assert [u for u, _ in chapters[2]["entries"]] == ["b/4", "b/5"]


def test_chapters_from_markers_no_intro():
    entries = [("b/1", "Combat-- Chapter 1 (X)"), ("b/2", "THAC0 (X)")]
    markers = [("Combat-- Chapter 1 (X)", "b/1")]
    chapters = toc.chapters_from_markers(entries, markers)
    assert [c["name"] for c in chapters] == ["Chapter 1: Combat"]
    assert chapters[0]["page_url"] == "b/1"


def test_chapters_by_letter():
    entries = [("a/1", "Armor"), ("a/2", "Bless"), ("a/3", "axe")]
    chapters = toc.chapters_by_letter(entries)
    assert [c["name"] for c in chapters] == ["A", "B"]
    assert [u for u, _ in chapters[0]["entries"]] == ["a/1", "a/3"]   # Armor + axe
    assert chapters[1]["entries"] == [("a/2", "Bless")]


def test_build_chapters_dispatch():
    entries = [("b/1", "Combat-- Chapter 1 (X)"), ("b/2", "THAC0 (X)")]
    # markers present → marker grouping
    assert toc.build_chapters(entries, [("Combat-- Chapter 1 (X)", "b/1")])[0]["name"] == "Chapter 1: Combat"
    # no markers → alphabetical grouping
    assert [c["name"] for c in toc.build_chapters(entries, [])] == ["C", "T"]
    # empty → empty
    assert toc.build_chapters([], []) == []


def test_build_chapters_accepts_row_like_tuples():
    # db returns sqlite3.Row (2-tuples); build_chapters must handle any 2-seq.
    entries = [("b/1", "Foo-- Chapter 1 (X)"), ("b/2", "Bar (X)")]
    out = toc.build_chapters(iter(entries), iter([("Foo-- Chapter 1 (X)", "b/1")]))
    assert out[0]["entries"] == [("b/1", "Foo-- Chapter 1 (X)"), ("b/2", "Bar (X)")]

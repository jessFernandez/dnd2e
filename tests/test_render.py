"""Unit tests for the Jarvis Markdown -> HTML renderer."""
from askscreen_html import render_markdown


def test_heading():
    assert "<h2>" in render_markdown("## Combat")


def test_bulleted_list():
    assert "<ul>" in render_markdown("- a\n- b")


def test_numbered_list():
    assert "<ol>" in render_markdown("1. first\n2. second")


def test_link():
    assert '<a href="dnd:///PHB/DD01.htm">x</a>' in render_markdown("[x](dnd:///PHB/DD01.htm)")


def test_bold_italic_code():
    h = render_markdown("**b** *i* `c`")
    assert "<strong>b</strong>" in h and "<em>i</em>" in h and "<code>c</code>" in h


def test_html_is_escaped():
    h = render_markdown("a < b & c")
    assert "&lt;" in h and "&amp;" in h


def test_plain_text_is_paragraph():
    assert "<p>" in render_markdown("just some prose")

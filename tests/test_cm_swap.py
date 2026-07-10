"""Executes the builder's in-place DOM swap in a real JavaScript engine.

`swap_wrap_js` exists to avoid reloading the document on every builder action —
`setHtml` tears the page down and rebuilds it, which blanks the view and flickers.
The script's contract is behavioural (does it scroll? does it signal failure?), so
QJSEngine (shipped with PyQt5) runs the actual source against a fake DOM rather
than us asserting on substrings.
"""
import sys

import pytest

import charactermancer_html as cmh
from charactermancer import Charactermancer

QJSEngine = pytest.importorskip("PyQt5.QtQml").QJSEngine
from PyQt5.QtCore import QCoreApplication      # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


_HARNESS = """
var _scrolled = null, _newHTML = null, _hasWrap = true;
var window = { scrollTo: function(x, y){ _scrolled = [x, y]; } };
var document = {
  querySelector: function(sel){
    if (sel !== '.wrap' || !_hasWrap) return null;
    return { set outerHTML(v){ _newHTML = v; }, get outerHTML(){ return _newHTML; } };
  }
};
"""


def _run(js, has_wrap=True):
    eng = QJSEngine()
    eng.evaluate(_HARNESS)
    eng.evaluate("_hasWrap = %s;" % ("true" if has_wrap else "false"))
    result = eng.evaluate(js)
    assert not result.isError(), result.toString()      # the script must parse and run
    scrolled = eng.evaluate("_scrolled === null ? '' : _scrolled.join(',')").toString()
    html = eng.evaluate("_newHTML === null ? '' : _newHTML").toString()
    return result.toBool(), html, scrolled


def _wrap():
    return cmh.generate_wrap(Charactermancer())


def test_in_place_swap_never_touches_the_scroll():
    swapped, html, scrolled = _run(cmh.swap_wrap_js(_wrap(), scroll_to_top=False))
    assert swapped
    assert html == _wrap()          # the node is replaced with exactly our markup
    assert scrolled == ""           # ...and the reader stays where they were


def test_step_change_resets_to_the_top():
    swapped, _, scrolled = _run(cmh.swap_wrap_js(_wrap(), scroll_to_top=True))
    assert swapped and scrolled == "0,0"


def test_returns_false_when_the_document_is_not_the_builder():
    # The caller falls back to a full render on false, so this must not throw.
    swapped, html, _ = _run(cmh.swap_wrap_js(_wrap(), False), has_wrap=False)
    assert swapped is False and html == ""


def test_hostile_markup_cannot_break_out_of_the_script():
    # The wrap is interpolated into JS source, so a stray quote or a literal
    # </script> in the rules text must not terminate anything. json.dumps handles it.
    nasty = '<div class="wrap">' + '</script></div>";alert(1);//' + '\n— em dash</div>'
    swapped, html, _ = _run(cmh.swap_wrap_js(nasty, False))
    assert swapped and html == nasty

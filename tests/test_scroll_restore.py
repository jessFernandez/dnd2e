"""Executes the builder's scroll-restore script in a real JavaScript engine.

The script's whole job is to position the page *before the first paint*, so the
interesting failures are timing ones that a string assertion can't see. QJSEngine
(shipped with PyQt5) runs the actual injected source against a fake DOM whose
layout height grows over successive animation frames — which is what QtWebEngine
does after `setHtml`, and what made an earlier version reveal the page at the wrong
offset and then visibly jump.
"""
import re
import sys

import pytest

import charactermancer_html as cmh
from charactermancer import Charactermancer

QJSEngine = pytest.importorskip("PyQt5.QtQml").QJSEngine
from PyQt5.QtCore import QCoreApplication      # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


def _restore_js(scroll_y=350) -> str:
    html = cmh.with_scroll_restore(cmh.generate(Charactermancer()), scroll_y)
    return re.search(r"<script>(\(function\(\).*?)</script>", html, re.S).group(1)


# A fake DOM. `_growth` is how much the document's height gains per frame — the
# layout settling. `_scrollTo` clamps against the current height, exactly as a
# browser does, which is the trap the script has to survive.
_HARNESS = """
var _rafQueue = [], _scrollHeight = 200, _revealedAt = -1, _frame = 0, _growth = 150;
var document = {
  documentElement: { get scrollHeight(){ return _scrollHeight; }, scrollTop: 0 },
  body: { get scrollHeight(){ return _scrollHeight; } },
  getElementById: function(id){
    if (id === 'cm-scroll-hide' && _revealedAt < 0) {
      return { parentNode: { removeChild: function(){ _revealedAt = _frame; } } };
    }
    return null;
  }
};
var history = {};
var window = {
  innerHeight: 100, pageYOffset: 0,
  scrollTo: function(x, y){
    this.pageYOffset = Math.min(y, Math.max(0, _scrollHeight - this.innerHeight));
  },
  requestAnimationFrame: function(fn){ _rafQueue.push(fn); },
  addEventListener: function(ev, fn){ if (ev === 'load') window._onload = fn; },
  setTimeout: function(fn, ms){ window._timeout = fn; }
};
function runFrames(n){
  for (var i = 0; i < n; i++){
    if (_revealedAt >= 0) break;
    _frame++; _scrollHeight += _growth;
    var q = _rafQueue; _rafQueue = [];
    for (var j = 0; j < q.length; j++) q[j]();
  }
}
"""


def _run(scroll_y=350, growth=150, frames=40):
    eng = QJSEngine()
    assert not eng.evaluate(_HARNESS).isError()
    eng.evaluate(f"_growth = {growth};")
    result = eng.evaluate(_restore_js(scroll_y))
    assert not result.isError(), result.toString()      # the script must parse and run
    eng.evaluate(f"runFrames({frames})")
    return (eng.evaluate("_revealedAt").toInt(),
            eng.evaluate("window.pageYOffset").toInt(),
            eng.evaluate("_revealedAt >= 0").toBool())


def test_script_parses_and_executes():
    revealed_at, _, revealed = _run()
    assert revealed and revealed_at > 0


def test_reveals_only_once_the_scroll_lands_on_target():
    # Frame 1 the document is still short, so scrollTo clamps below the target. The
    # script must NOT reveal there — that half-laid-out paint was the flash.
    _, offset, _ = _run(scroll_y=350)
    assert offset == 350


def test_a_settled_short_page_still_reveals():
    # A page genuinely too short to reach the target must not stay hidden forever.
    revealed_at, offset, revealed = _run(scroll_y=5000, growth=0)
    assert revealed and revealed_at > 0
    assert offset == 100                                # its own maximum scroll


def test_a_document_that_never_settles_still_reveals():
    # Pathological: the height grows every frame and the target is unreachable. The
    # frame budget has to give up and show the page.
    revealed_at, _, revealed = _run(scroll_y=10 ** 9, growth=150, frames=60)
    assert revealed and revealed_at > 0

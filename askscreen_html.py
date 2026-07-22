"""askscreen_html.py — "Ask the Rules" page (local Ollama-powered rules Q&A)."""
import re
from view_common import esc


# ── Minimal Markdown → HTML ──────────────────────────────────────────────────

def _inline(t: str) -> str:
    t = esc(t)
    t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)',
               lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', t)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    return t


def render_markdown(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r'(#{1,6})\s+(.*)', line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue
        if re.match(r'\s*[-*]\s+', line):
            items = []
            while i < n and re.match(r'\s*[-*]\s+', lines[i]):
                items.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r'\s*\d+\.\s+', line):
            items = []
            while i < n and re.match(r'\s*\d+\.\s+', lines[i]):
                items.append(f"<li>{_inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if line.lstrip().startswith(">"):
            quote = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote.append(_inline(re.sub(r'^\s*>\s?', '', lines[i])))
                i += 1
            out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
            continue
        para = []
        while i < n and lines[i].strip() and not re.match(r'(#{1,6}\s|\s*[-*]\s|\s*\d+\.\s|\s*>)', lines[i]):
            para.append(_inline(lines[i].strip()))
            i += 1
        out.append("<p>" + "<br>".join(para) + "</p>")
    return "\n".join(out)


# ── CSS ──────────────────────────────────────────────────────────────────────

_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a1c26; color: #c8cad8;
         font-family: "Segoe UI", system-ui, sans-serif; font-size: 14px; min-height: 100vh; }
  .wrap { max-width: 820px; margin: 0 auto; padding: 34px 28px 70px; }
  .hero { text-align: center; margin-bottom: 22px; }
  .hero h1 { font-size: 26px; color: #c9a84c; letter-spacing: .02em; font-family: Georgia, serif; }
  .hero p { color: #5a6080; font-size: 12.5px; margin-top: 6px; letter-spacing: .02em; }

  .askbar > * + * { margin-left: 8px; }  /* QtWebEngine drops flex gap */
  .askbar { display: flex; margin-bottom: 10px; }
  #q { flex: 1; background: #23263a; border: 1px solid #383c52; border-radius: 9px;
       color: #e6e9f6; padding: 12px 15px; font-size: 15px; outline: none; }
  #q:focus { border-color: #c9a84c; }
  .btn { background: #c9a84c; color: #1a1c26; border: none; border-radius: 9px;
         padding: 0 20px; font-size: 14px; font-weight: 700; cursor: pointer; letter-spacing: .02em; }
  .btn:hover { background: #d8b968; }

  .meta > * { margin: 0 10px 0 0; }  /* QtWebEngine drops flex gap */
  .meta { display: flex; align-items: center; flex-wrap: wrap;
          color: #5a6080; font-size: 11.5px; margin-bottom: 24px; }
  .meta select { background: #23263a; color: #c8cad8; border: 1px solid #383c52;
                 border-radius: 6px; padding: 4px 8px; font-size: 11.5px; outline: none; }
  .meta a { color: #6b7290; } .meta a:hover { color: #c9a84c; }
  .pill { background: #17301f; color: #6cc48a; border: 1px solid #244a33;
          border-radius: 20px; padding: 1px 9px; font-weight: 600; }

  .card { background: #21243a; border: 1px solid #2a2e45; border-radius: 12px;
          padding: 20px 22px; margin-top: 18px; }
  .q-label { font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: #6b7290; margin-bottom: 6px; }
  .q-text { font-size: 16px; color: #e6e9f6; font-weight: 600; line-height: 1.45; }

  .stream { white-space: pre-wrap; color: #aeb4c8; font-size: 14px; line-height: 1.7; margin-top: 14px; }
  .status-row { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; }
  #ask-status > * + * { margin-left: 10px; }  /* QtWebEngine drops flex gap */
  #ask-status { display: flex; align-items: center; color: #9098b8; font-size: 13px; }
  .stopbtn { color: #e6a0a8; border: 1px solid #5c2a30; border-radius: 6px; padding: 3px 12px;
             font-size: 11.5px; font-weight: 600; text-decoration: none; }
  .stopbtn:hover { background: #2a1518; border-color: #e6a0a8; }
  .spinner { width: 15px; height: 15px; border: 2px solid #3a3f58; border-top-color: #c9a84c;
             border-radius: 50%; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .answer { line-height: 1.72; color: #cfd3e4; font-size: 14.5px; margin-top: 16px; }
  .answer h1, .answer h2, .answer h3 { color: #e8eaf6; margin: 18px 0 8px; font-weight: 700; }
  .answer h1 { font-size: 19px; } .answer h2 { font-size: 16.5px; } .answer h3 { font-size: 15px; }
  .answer p { margin: 0 0 12px; }
  .answer ul, .answer ol { margin: 0 0 12px 22px; } .answer li { margin-bottom: 5px; }
  .answer a { color: #e0b85a; text-decoration: none; border-bottom: 1px solid #5a4a1c; }
  .answer a:hover { color: #f0d488; border-bottom-color: #c9a84c; }
  .answer code { background: #171926; border: 1px solid #2a2e45; border-radius: 4px;
                 padding: 1px 5px; font-family: Consolas, monospace; font-size: 12.5px; color: #d4b46a; }
  .answer blockquote { border-left: 3px solid #c9a84c; padding: 4px 14px; margin: 0 0 12px;
                       color: #aab0c8; background: #1c1f30; border-radius: 4px; }
  .disclaimer { color: #4a5070; font-size: 11px; margin-top: 22px; font-style: italic; text-align: center; }

  .setup { max-width: 580px; margin: 34px auto 0; background: #21243a;
           border: 1px solid #2a2e45; border-radius: 12px; padding: 26px 26px 24px; }
  .setup h2 { color: #e6e9f6; font-size: 16px; margin-bottom: 10px; }
  .setup p { color: #8890b0; font-size: 12.5px; line-height: 1.6; margin-bottom: 14px; }
  .setup ol { margin: 0 0 14px 20px; color: #b8bccf; font-size: 12.5px; line-height: 1.8; }
  .setup code, .cmd { background: #171926; border: 1px solid #2a2e45; border-radius: 5px;
                      padding: 2px 7px; font-family: Consolas, monospace; font-size: 12.5px; color: #d4b46a; }
  .setup a { color: #c9a84c; }
  .setup a.btn { color: #1a1c26; }
  .setup .row > * + * { margin-left: 8px; }  /* QtWebEngine drops flex gap */
  .setup .row { display: flex; align-items: center; margin-top: 6px; }
  .err { background: #2a1518; border: 1px solid #5c2a30; color: #e6a0a8; border-radius: 9px;
         padding: 12px 15px; font-size: 13px; margin-top: 16px; white-space: pre-wrap; }
"""

_SCRIPT = """
  function submitAsk() {
    var el = document.getElementById('q'); var v = el.value.trim();
    if (v) window.location.href = 'dnd:///ask/' + encodeURIComponent(v);
    return false;
  }
  function setModel(v) { window.location.href = 'dnd:///ask-setmodel/' + encodeURIComponent(v); }
  window.addEventListener('load', function () {
    var q = document.getElementById('q'); if (q) q.focus();
  });
"""


def _model_select(model: str, models) -> str:
    models = models or [model]
    if model not in models:
        models = [model] + models
    opts = "".join(
        f'<option value="{esc(m)}"{" selected" if m == model else ""}>{esc(m)}</option>'
        for m in models
    )
    return f'<select onchange="setModel(this.value)">{opts}</select>'


def _askbar(question: str = "") -> str:
    return (
        '<form class="askbar" onsubmit="return submitAsk();">'
        f'<input id="q" type="text" autocomplete="off" placeholder="Ask Jarvis a 2e rules question…" value="{esc(question)}">'
        '<button class="btn" type="submit">Ask</button></form>'
    )


def _meta(model: str, models, show_new: bool = False) -> str:
    new_chat = '<span>·</span><a href="dnd:///ask-new">✦ new chat</a>' if show_new else ''
    return (
        '<div class="meta">'
        '<span>Model:</span>' + _model_select(model, models) +
        '<span>·</span><span class="pill">local · Ollama</span>'
        '<span>·</span><a href="dnd:///ask-refresh">refresh</a>' + new_chat +
        '<span style="margin-left:auto">Runs on your machine — free & offline. Verify against the book.</span>'
        '</div>'
    )


def _turn_card(q: str, answer_md: str) -> str:
    return ('<div class="card"><div class="q-label">Question</div>'
            f'<div class="q-text">{esc(q)}</div>'
            f'<div class="answer">{render_markdown(answer_md)}</div></div>')


def _thread_html(thread) -> str:
    return "".join(_turn_card(q, a) for q, a in reversed(thread or []))


def _loading_card(q: str) -> str:
    return ('<div class="card"><div class="q-label">Question</div>'
            f'<div class="q-text">{esc(q)}</div>'
            '<div class="status-row">'
            '<div id="ask-status"><span class="spinner"></span><span>Thinking…</span></div>'
            '<a class="stopbtn" href="dnd:///ask-stop">Stop</a></div>'
            '<div id="ask-stream" class="stream"></div></div>')


def _error_card(q: str, error: str) -> str:
    return ('<div class="card"><div class="q-label">Question</div>'
            f'<div class="q-text">{esc(q)}</div>'
            f'<div class="err">{esc(error)}</div></div>')


def _page(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Jarvis — AD&D 2e</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <div class="hero"><h1>✦ Jarvis</h1>
    <p>At your service. I've read every 2e rulebook — and your house rules — so you don't have to flip a single page.</p>
  </div>
  {body}
</div><script>{_SCRIPT}</script></body></html>"""


def generate(state: str, *, model: str = "llama3.1", models=None,
             ollama_ok: bool = True, question: str = "", answer_md: str = "",
             error: str = "", thread=None) -> str:
    """state: 'setup' | 'ready' | 'loading' | 'answer' | 'error'.
    thread: list of (question, answer_md) turns, oldest first."""
    thread = thread or []

    if state == "setup":
        if not ollama_ok:
            body = """
            <div class="setup">
              <h2>Set up Ollama (one-time, free)</h2>
              <p>Jarvis runs a language model <b>locally</b> on this computer using
                 <a href="https://ollama.com">Ollama</a> — no account, no API key, no cost.</p>
              <ol>
                <li>Install Ollama from <a href="https://ollama.com">ollama.com</a> and launch it.</li>
                <li>Open a terminal and download a model:<br><span class="cmd">ollama pull llama3.1</span></li>
                <li>Come back and click <b>Refresh</b>.</li>
              </ol>
              <div class="row"><a class="btn" href="dnd:///ask-refresh" style="text-decoration:none;padding:9px 18px;">Refresh</a>
                <span style="color:#5a6080;font-size:12px;">Ollama not detected yet.</span></div>
            </div>"""
        else:
            body = """
            <div class="setup">
              <h2>Almost ready — install a model</h2>
              <p>Ollama is running, but no models are installed. Pull one from a terminal, then refresh:</p>
              <ol>
                <li><span class="cmd">ollama pull llama3.1</span> &nbsp;(good general model, ~5&nbsp;GB)</li>
                <li>or a smaller/faster one: <span class="cmd">ollama pull qwen2.5:3b</span></li>
              </ol>
              <div class="row"><a class="btn" href="dnd:///ask-refresh" style="text-decoration:none;padding:9px 18px;">Refresh</a></div>
            </div>"""
        return _page(body)

    if state == "ready":
        return _page(_askbar() + _meta(model, models))

    if state == "loading":
        body = (_askbar() + _meta(model, models, show_new=True) +
                _loading_card(question) + _thread_html(thread))
        return _page(body)

    if state == "answer":
        body = (_askbar() + _meta(model, models, show_new=True) + _thread_html(thread) +
                '<div class="disclaimer">Answered by a local model from your 2e rulebooks — '
                'double-check anything important against the source page.</div>')
        return _page(body)

    body = (_askbar() + _meta(model, models, show_new=True) +
            _error_card(question, error) + _thread_html(thread))
    return _page(body)

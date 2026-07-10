"""rules_agent.py — "Ask the Rules" powered by a LOCAL model via Ollama.

No API key, no cost: the app talks to an Ollama server running on the user's
machine (http://localhost:11434).  To keep answers grounded (and to work even
with small local models that are weak at tool-calling), we do retrieval first:
full-text search the local rulebook DB, hand the top pages to the model as
context, and ask it to answer citing them with dnd:// links.
"""

import re
import json
import sqlite3
import urllib.request
import urllib.error
from html import unescape

from PyQt5.QtCore import QThread, pyqtSignal

import db

OLLAMA_URL    = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1"

# Retrieval re-ranking knobs (tuned against tests/golden_retrieval.py).
_TITLE_WEIGHT     = 3.0    # BM25 weight on the title column vs. body (1.0)
_TABLE_PENALTY    = 5.0    # push "…-- Table NN" pages below the prose that explains them
_APPENDIX_PENALTY = 2.0    # likewise for appendix/reference pages
_CORE_BOOK_BONUS  = 3.0    # prefer the canonical PHB/DMG rule over supplement restatements
_TITLE_SUBSET_BONUS = 6.0  # a page titled entirely in the query's words is the canonical one

SYSTEM_PROMPT = """\
You are a rules assistant for Advanced Dungeons & Dragons 2nd Edition. You are \
given excerpts from the official 2e rulebooks, and possibly a set of CAMPAIGN \
HOUSE RULES. Answer the user's question using ONLY that provided information.

Rules for your answer:
- CAMPAIGN HOUSE RULES take precedence over the standard rulebook wherever they \
conflict. If a house rule affects the answer, apply it and label it with the \
crossed-swords marker exactly like this: "⚔️ House Rule: …" so the reader knows \
it differs from the printed rule.
- Give the concrete procedure a player or DM needs at the table (rolls, \
modifiers, order of operations), quoting the rule where it helps. ALWAYS state \
exactly what dice are rolled (e.g. "roll 1d20", "roll 3d6", "roll d100") and \
spell out any saving throw, attack roll, or check the rule requires — never \
describe a mechanic without naming the roll behind it.
- Cite every rulebook page you use as a Markdown link in EXACTLY this form, \
using the "cite as" URL shown with each excerpt: \
[Figuring the To-Hit Number](dnd:///PHB/DD01673.htm). Lead with the page that \
most directly answers the question (prefer the core rule that defines the \
mechanic over a page that only mentions it in passing). Every entry in the \
"Sources" list must be a full [Title](dnd:///…) link — never a bare or bracketed \
URL. Cite a house rule as "(⚔️ house rule)".
- If the provided text does not contain the answer, say so plainly — do NOT \
invent rules.
- Be concise. Answer in GitHub-flavoured Markdown and end with a short \
"Sources" list of the pages you cited."""


def ollama_status(base_url: str = OLLAMA_URL, timeout: float = 0.7):
    """Return (running: bool, model_names: list[str]) for a local Ollama server."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return True, [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return False, []


def pick_default_model(models: list[str]) -> str:
    """Choose a sensible default from installed models (prefer capable ones)."""
    prefs = ("llama3.1", "qwen2.5", "llama3", "mistral", "qwen", "gemma", "phi")
    for p in prefs:
        for m in models:
            if m.lower().startswith(p):
                return m
    return models[0] if models else DEFAULT_MODEL


# Common words that only add noise to a keyword search.
_STOP = set(
    "a an the to of for in on at by is are am be been being do does did done how "
    "what when where which who whom whose why will would can could should i me my "
    "we us our you your he she it its they them their that this these those with "
    "without as if then than so just about into over under out up down get gets "
    "getting got use used using need needs want wants make makes made also many "
    "much more most some any all each per vs versus and or but not no yes there "
    "here work works working does".split()
)

# Colloquial / shorthand → the vocabulary the 2e rulebooks actually use.
_SYN = {
    "stat": ["ability", "scores"], "stats": ["ability", "scores"],
    "statistic": ["ability", "scores"], "statistics": ["ability", "scores"],
    "hp": ["hit points", "hit dice"], "hitpoints": ["hit points", "hit dice"],
    "health": ["hit points"], "fighter": ["warrior"], "paladin": ["warrior"],
    "ranger": ["warrior"], "mage": ["wizard"], "priest": ["cleric"],
    "ac": ["armor class"], "armour": ["armor"],
    "xp": ["experience"], "exp": ["experience"],
    "init": ["initiative"], "crit": ["critical hit"], "crits": ["critical hit"],
    "dmg": ["damage"], "tohit": ["attack roll"], "thaco": ["thac0"],
    "str": ["strength"], "dex": ["dexterity"], "con": ["constitution"],
    "int": ["intelligence"], "wis": ["wisdom"], "cha": ["charisma"],
    "lvl": ["level"], "lvls": ["level"], "leveling": ["experience", "level"],
    "save": ["saving throw"], "saves": ["saving throws"],
    "gp": ["coins"], "gold": ["coins", "treasure"], "money": ["coins", "treasure"],
    "grapple": ["wrestling"], "wrestle": ["wrestling"], "grappling": ["wrestling"],
    "multiclass": ["multi-class"], "multiclassing": ["multi-class"],
    "spellcasting": ["spells"], "caster": ["wizard", "priest"],
    "rolls": ["rolling"], "movement": ["move"], "encumbrance": ["weight"],
    # colloquial / edition-shorthand -> 2e rulebook terminology
    "sneak": ["backstab", "move silently"], "stealth": ["move silently", "hide in shadows"],
    "hide": ["hide in shadows"], "hiding": ["hide in shadows"],
    "resurrect": ["raise dead", "resurrection"], "resurrecting": ["raise dead"],
    "revive": ["raise dead"], "rez": ["raise dead"],
    "bribe": ["reaction"], "bribing": ["reaction"], "persuade": ["reaction"],
    "tie": ["binding"], "restrain": ["binding", "wrestling"],
    "disarm": ["disarm"], "enemy": ["opponent"], "opponent": ["opponent"],
}


def _terms(text: str) -> list:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out: list = []
    for t in toks:
        if len(t) < 2 or t in _STOP:
            continue
        if t not in out:
            out.append(t)
        for s in _SYN.get(t, []):
            if s not in out:
                out.append(s)
    if not out:                                  # query was all stopwords
        out = [t for t in toks if len(t) >= 3]
    return out[:16]


def _fts_from_terms(terms: list, fallback: str = "", prefix: bool = False) -> str:
    seen: list = []
    for t in terms:
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    if not seen:
        return f'"{fallback.strip()}"' if fallback.strip() else '""'
    atoms = []
    for t in seen[:20]:
        # Prefix-match plain words (≥4 chars) so the un-stemmed FTS index still
        # matches singular/plural and inflections: lock*→lock/locks, climb*→
        # climbing, spell*→spells. Phrases and short/odd tokens stay exact.
        if prefix and t.isascii() and t.isalnum() and len(t) >= 4:
            atoms.append(f"{t}*")
        else:
            atoms.append(f'"{t}"')
    return " OR ".join(atoms)


def _fts_query(text: str) -> str:
    return _fts_from_terms(_terms(text), fallback=text)


# Minor words ignored when testing whether a page title is "made of" query words.
_TITLE_MINOR = {"a", "an", "the", "of", "in", "on", "to", "for", "and", "or",
                "vs", "with", "your", "you", "how", "into", "at", "by"}


def _query_stems(terms: list) -> set:
    """Flatten query atoms (tokens + multi-word phrases) into a set of word stems."""
    stems: set = set()
    for atom in terms:
        for w in re.findall(r"[a-z0-9]+", atom.lower()):
            stems.add(w)
    return stems


def _title_is_query(clean_title: str, stems: set) -> bool:
    """True if every meaningful word of the title is covered by a query stem.

    Captures the strong signal that a page titled entirely in the question's own
    words (e.g. "Movement", "Poison", "Charisma") is the canonical page for it,
    even when a longer prose page loses on raw term-frequency.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", clean_title.lower())
             if w not in _TITLE_MINOR]
    if not words:
        return False
    for w in words:
        if not any(w == s or (len(s) >= 4 and w.startswith(s))
                   or (len(w) >= 4 and s.startswith(w)) for s in stems):
            return False
    return True


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


def _linkify(text: str, titles: dict) -> str:
    """Turn bare / bracketed dnd:/// URLs into proper [Title](url) Markdown links,
    so they render as clickable links even if the model didn't format them."""
    def _title(url: str) -> str:
        key = url[len("dnd:///"):]
        return titles.get(key, key.rsplit("/", 1)[-1].replace(".htm", ""))

    # [dnd:///PHB/DD01673.htm]  ->  [Figuring the To-Hit Number](dnd:///PHB/DD01673.htm)
    text = re.sub(r'\[(dnd:///[A-Za-z0-9/._#\-]+)\]',
                  lambda m: f'[{_title(m.group(1))}]({m.group(1)})', text)
    # bare dnd:///... that isn't already the target of a [text](...) link
    text = re.sub(r'(?<![(\[])dnd:///[A-Za-z0-9/._#\-]+',
                  lambda m: f'[{_title(m.group(0))}]({m.group(0)})', text)
    return text


def _mark_house_rules(text: str) -> str:
    """Prefix house-rule mentions with the crossed-swords marker used in the books."""
    text = re.sub(r'(?im)(?:⚔️?\s*)?\*{0,2}house rules?\*{0,2}\s*:\*{0,2}',
                  '⚔️ **House Rule:**', text)
    text = re.sub(r'(?i)\((?:⚔️?\s*)?house rules?\)', '(⚔️ house rule)', text)
    return text


class AskWorker(QThread):
    status   = pyqtSignal(str)
    delta    = pyqtSignal(str)   # a streamed chunk of the answer
    finished = pyqtSignal(str)   # the full, post-processed answer
    failed   = pyqtSignal(str)

    def __init__(self, db_path: str, model: str, question: str,
                 base_url: str = OLLAMA_URL, history=None):
        super().__init__()
        self.db_path  = db_path
        self.model    = model or DEFAULT_MODEL
        self.question = question
        self.base_url = base_url.rstrip("/")
        self.history  = list(history or [])   # [(question, answer_md), ...] prior turns
        self._cancel  = False

    def cancel(self):
        """Ask the worker to stop streaming as soon as possible."""
        self._cancel = True

    # ── query rewriting (model turns the question into rulebook terms) ──────
    def _rewrite_query(self, question: str, prev: str = "") -> list:
        ctx = f"For context, the previous question was: {prev}\n" if prev else ""
        prompt = (
            "You turn a Dungeons & Dragons 2nd Edition rules question into search "
            "keywords. Reply with ONLY a comma-separated list of 3 to 6 short search "
            "phrases in official 2e rulebook terminology (for example: ability scores, "
            "THAC0, saving throw, hit dice). No explanations, no numbering.\n\n"
            f"{ctx}Question: {question}"
        )
        try:
            raw = self._chat([{"role": "user", "content": prompt}])
        except Exception:
            return []
        if not raw:
            return []
        line = next((ln for ln in raw.splitlines() if "," in ln), "")
        if not line:
            line = next((ln for ln in raw.splitlines() if ln.strip()), "")
        out: list = []
        for part in re.split(r"[,;]", line):
            p = re.sub(r"^[\s\-*\d.)\"']+", "", part).strip().strip("\"'").lower()
            p = re.sub(r"[^a-z0-9 \-]", "", p).strip()
            if 2 <= len(p) <= 40 and p not in out:
                out.append(p)
        return out[:6]

    # ── retrieval ──────────────────────────────────────────────────────────
    def _retrieve(self, question: str, phrases=None, k: int = 8, full: int = 5):
        conn = sqlite3.connect(self.db_path)
        c    = conn.cursor()
        atoms = _terms(question) + list(phrases or [])
        query = _fts_from_terms(atoms, fallback=question, prefix=True)
        stems = _query_stems(atoms)
        # Rank candidates ourselves rather than trusting raw BM25:
        #  • weight the TITLE column heavily — a page literally titled "Wrestling"
        #    should beat one that only mentions the word in passing;
        #  • demote lookup-table / appendix pages beneath the PROSE that explains
        #    the rule (someone asking "how does X work" wants the text, not a grid);
        #  • prefer the canonical PHB/DMG rule over supplement restatements.
        # bm25() is negative (better = more negative), so penalties are added.
        extra = (
            f"(CASE WHEN p.title LIKE '%Table%'    THEN {_TABLE_PENALTY}    ELSE 0 END)"
            f"+ (CASE WHEN p.title LIKE '%Appendix%' THEN {_APPENDIX_PENALTY} ELSE 0 END)"
            f"+ (CASE WHEN p.page_url LIKE 'PHB/%' OR p.page_url LIKE 'DMG/%'"
            f"        THEN {-_CORE_BOOK_BONUS} ELSE 0 END)"
        )
        has_chunks = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone() is not None

        if has_chunks:
            # Search PASSAGES, keep each page's best-matching passage, and hand that
            # tight passage to the model as the excerpt (sharper than page-start text).
            c.execute(
                f"""SELECT c.page_url, p.title, p.book_name, c.body,
                           bm25(chunks_fts, 0.0, 0.0, {_TITLE_WEIGHT}, 1.0) + {extra} AS score
                    FROM   chunks_fts c JOIN pages p ON c.page_url = p.page_url
                    WHERE  chunks_fts MATCH ?
                    ORDER  BY score LIMIT ?""",
                (query, max(k * 8, 80)),
            )
            cand, best = [], set()
            for url, title, book, body, score in c.fetchall():
                if url in best:                  # keep only the page's top passage
                    continue
                best.add(url)
                cand.append((url, title, book, body, score))
        else:
            # Fallback for an un-chunked DB: page-level search with a page-start body.
            c.execute(
                f"""SELECT p.page_url, p.title, p.book_name,
                           snippet(pages_fts, 2, '', '', ' … ', 30) AS body,
                           bm25(pages_fts, 0.0, {_TITLE_WEIGHT}, 1.0) + {extra} AS score
                    FROM   pages_fts JOIN pages p ON pages_fts.page_url = p.page_url
                    WHERE  pages_fts MATCH ?
                    ORDER  BY score LIMIT ?""",
                (query, max(k * 4, 40)),
            )
            cand = list(c.fetchall())

        # Second-pass Python re-rank: a page whose whole title is query words is
        # almost certainly the canonical page — lift it above term-frequency noise.
        ranked = []
        for url, title, book, body, score in cand:
            clean = re.sub(r"\s*\([^)]+\)\s*$", "", title or url).strip()
            bonus = _TITLE_SUBSET_BONUS if _title_is_query(clean, stems) else 0.0
            ranked.append((score - bonus, url, clean, book, body))
        ranked.sort(key=lambda r: r[0])

        excerpts, seen = [], set()
        for _score, url, clean, book, body in ranked:
            norm = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
            if norm in seen:                     # drop near-duplicate titles across books
                continue
            seen.add(norm)
            text = re.sub(r"\s+", " ", (body or "")).strip()[:1600]
            if not has_chunks and len(excerpts) < full:
                c.execute("SELECT content_html FROM pages WHERE page_url = ?", (url,))
                row = c.fetchone()
                if row and row[0]:
                    b = _strip_html(row[0])
                    if len(b) > 60:
                        text = b[:1600]
            excerpts.append((url, clean, book or "", text))
            if len(excerpts) >= k:
                break
        conn.close()
        return excerpts

    def _house_rules(self) -> str:
        """All campaign house rules, grouped by category (empty if none)."""
        conn = db.connect(self.db_path)
        rows = db.all_house_rules(conn)
        conn.close()
        by_cat: dict = {}
        for cat, text in rows:
            text = (text or "").replace("�", "-").strip()
            if text:
                by_cat.setdefault(cat or "General", []).append(text)
        blocks = []
        for cat, items in by_cat.items():
            blocks.append(f"[{cat}]\n" + "\n".join(f"- {t}" for t in items))
        return "\n\n".join(blocks)

    def _chat(self, messages: list) -> str:
        body = json.dumps({
            "model":    self.model,
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": 0.2},
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=240) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return (data.get("message") or {}).get("content", "").strip()

    def _chat_stream(self, messages: list) -> str:
        """Stream the answer, emitting `delta` per chunk; return the full text."""
        body = json.dumps({
            "model":    self.model,
            "messages": messages,
            "stream":   True,
            "options":  {"temperature": 0.2},
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=body,
            headers={"Content-Type": "application/json"},
        )
        parts = []
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in r:
                if self._cancel:
                    break
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw.decode("utf-8", "replace"))
                except Exception:
                    continue
                chunk = (obj.get("message") or {}).get("content", "")
                if chunk:
                    parts.append(chunk)
                    self.delta.emit(chunk)
                if obj.get("done"):
                    break
        return "".join(parts).strip()

    # ── prompt assembly (shared by the streaming app path and the eval) ─────
    def _compose(self, status=None):
        """Retrieve context and build the chat messages. Returns (messages, titles)."""
        prev = self.history[-1][0] if self.history else ""
        if status:
            status("Understanding your question…")
        phrases = self._rewrite_query(self.question, prev)
        if status:
            status("Searching the rulebooks…")
        excerpts = self._retrieve(self.question, phrases)
        house    = self._house_rules()

        if excerpts:
            context = "\n\n".join(
                f"### {title} ({book})   [cite as dnd:///{url}]\n{text}"
                for url, title, book, text in excerpts
            )
        else:
            context = "(No matching pages were found in the local rulebook database.)"

        house_block = ""
        if house:
            house_block = (
                "CAMPAIGN HOUSE RULES — these OVERRIDE the standard rulebook "
                "wherever they conflict:\n\n" + house + "\n\n"
                "=====================================================\n\n"
            )

        user = (
            f"{house_block}"
            f"Rulebook excerpts:\n\n{context}\n\n"
            f"Question: {self.question}\n\n"
            "Answer using only the information above. Apply any relevant house "
            "rule (and label it), and cite the rulebook pages you use."
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for q, a in self.history[-4:]:          # carry recent turns for follow-ups
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": user})

        titles = {url: title for url, title, _b, _t in excerpts}
        return messages, titles

    @staticmethod
    def _postprocess(answer: str, titles: dict) -> str:
        return _mark_house_rules(_linkify(answer, titles))

    def answer_sync(self):
        """Run the full pipeline non-streaming and return the finished answer.

        Same retrieval + prompt + post-processing as the app; used by the answer
        evaluation harness (tests/answer_eval.py) so the eval can't drift from
        what users actually see."""
        messages, titles = self._compose()
        raw = self._chat(messages)
        return self._postprocess(raw, titles) if raw else ""

    def run(self):
        try:
            messages, titles = self._compose(status=self.status.emit)
            self.status.emit(f"Asking {self.model}…")
            answer = self._chat_stream(messages)
            if answer:
                answer = self._postprocess(answer, titles)
                if self._cancel:
                    answer += "\n\n_(stopped)_"
            elif self._cancel:
                answer = "_(stopped)_"
            self.finished.emit(answer or "The model returned an empty answer. Try rephrasing the question.")

        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8", "replace")).get("error", "")
            except Exception:
                pass    # best-effort: a non-JSON error body just leaves detail empty
            if e.code == 404 or "not found" in detail.lower():
                self.failed.emit(
                    f"The model \"{self.model}\" isn't installed in Ollama.\n"
                    f"Install it from a terminal:  ollama pull {self.model}"
                )
            else:
                self.failed.emit(f"Ollama error ({e.code}): {detail or e.reason}")
        except urllib.error.URLError:
            self.failed.emit(
                "Couldn't reach Ollama at " + self.base_url + ".\n"
                "Make sure Ollama is installed and running (download it from ollama.com), "
                "then pull a model, e.g.  ollama pull llama3.1"
            )
        except Exception as e:
            self.failed.emit(f"Something went wrong: {e}")

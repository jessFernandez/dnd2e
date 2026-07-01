"""
D&D 2nd Edition Rules – Desktop App
Run after scraper.py has built dnd2e.db.

    python app.py
"""

import os
import re
import sys
import json
import sqlite3
from pathlib import Path
from urllib.parse import unquote
from collections import defaultdict

from dmscreen_html import generate as generate_dmscreen_html
from actionsscreen_html import generate as generate_actions_html
from chargen_html import generate as generate_chargen_html
from splash_html import generate as generate_splash_html
import askscreen_html
from rules_agent import AskWorker, DEFAULT_MODEL, ollama_status, pick_default_model

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QStatusBar, QMessageBox,
    QLabel, QSizePolicy, QShortcut,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QSettings, QEvent
from PyQt5.QtGui import QFont, QColor, QPalette, QFontDatabase, QKeySequence

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    HAS_WEBENGINE = True
except ImportError:
    from PyQt5.QtWidgets import QTextBrowser
    HAS_WEBENGINE = False

def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def _user_data_dir() -> Path:
    """A writable per-user directory for bookmarks/settings (survives app updates)."""
    root = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME") or str(Path.home())
    base = Path(root) / "DnD2eRules"
    base.mkdir(parents=True, exist_ok=True)
    return base


DB_PATH      = _bundle_dir() / "dnd2e.db"
USER_DB_PATH = _user_data_dir() / "userdata.db"
BASE_URL     = "https://regalgoblins.com/2erules/"

BOOK_ORDER = ["PHB", "DMG", "MM", "SP", "HLC", "TM", "SM", "CT", "AEG", "ECO"]
BOOK_NAMES = {
    "PHB": "Player's Handbook",
    "DMG": "Dungeon Master Guide",
    "MM":  "Monstrous Manual",
    "SP":  "Skills and Powers",
    "HLC": "High-Level Campaigns",
    "TM":  "Tome of Magic",
    "SM":  "Spells and Magic",
    "CT":  "Combat and Tactics",
    "AEG": "Arms and Equipment Guide",
    "ECO": "Economics of the Realm",
}

# Vivid foreground colours for book nodes on the dark sidebar
BOOK_TREE_COLORS = {
    "PHB": "#5b9bd5",
    "DMG": "#e07b2a",
    "MM":  "#4db870",
    "SP":  "#c8a828",
    "HLC": "#a76bcc",
    "TM":  "#e05555",
    "SM":  "#3dbfa8",
    "CT":  "#e0924a",
    "AEG": "#8a9bb0",
    "ECO": "#c9a84c",
}

# Accent colours used in the generated TOC HTML pages
BOOK_ACCENT_COLORS = {
    "PHB": "#2563eb",
    "DMG": "#ea580c",
    "MM":  "#16a34a",
    "SP":  "#ca8a04",
    "HLC": "#7c3aed",
    "TM":  "#dc2626",
    "SM":  "#0d9488",
    "CT":  "#b45309",
    "AEG": "#4b5563",
    "ECO": "#b7930a",
}

# Subtle dark tints used for list items in results / bookmarks panels
BOOK_ITEM_COLORS = {
    "PHB": "#192233",
    "DMG": "#2a1e12",
    "MM":  "#132213",
    "SP":  "#232012",
    "HLC": "#1f1430",
    "TM":  "#261212",
    "SM":  "#122424",
    "CT":  "#251b12",
    "AEG": "#1c1f24",
    "ECO": "#22200a",
}

# ── Global stylesheet ─────────────────────────────────────────────────────────

APP_STYLESHEET = """
/* ── Base ─────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background: #13151b;
    color: #c9ccd6;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

/* ── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle:horizontal {
    background: #2a2d38;
    width: 1px;
}

/* ── Scrollbars ────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #13151b;
    width: 7px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3a3f4e;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #c9a84c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: #13151b;
    height: 7px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #3a3f4e;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #c9a84c; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Search box ────────────────────────────────────────────────── */
QLineEdit {
    background: #1e2130;
    color: #e0e4f0;
    border: 1px solid #2e3348;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: #5c4a1c;
}
QLineEdit:focus { border-color: #c9a84c; }
QLineEdit:hover { border-color: #3e4560; }

/* ── Buttons ───────────────────────────────────────────────────── */
QPushButton {
    background: #1e2130;
    color: #c0c4d4;
    border: 1px solid #2e3348;
    border-radius: 7px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover   { background: #272b40; border-color: #c9a84c; color: #ffffff; }
QPushButton:pressed { background: #c9a84c; border-color: #c9a84c; color: #1a1c26; }
QPushButton:disabled { color: #404555; border-color: #1e2030; background: #181a24; }

/* ── Tab bar ───────────────────────────────────────────────────── */
QTabWidget::pane  { border: none; background: #13151b; }
QTabWidget::tab-bar { alignment: left; }
QTabBar {
    background: #13151b;
}
QTabBar::tab {
    background: transparent;
    color: #565e78;
    padding: 9px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
}
QTabBar::tab:selected {
    color: #e0e4f0;
    border-bottom: 2px solid #c9a84c;
}
QTabBar::tab:hover:!selected { color: #9aa0b8; }

/* ── Content tab bar (browser-style, separate from sidebar tabs) ── */
QTabWidget#contentTabs { background: #1a1c26; }
QTabWidget#contentTabs::pane { border: none; background: #1a1c26; }
QTabWidget#contentTabs QTabBar {
    background: #13151f;
    border-bottom: 1px solid #1e2130;
}
QTabWidget#contentTabs QTabBar::tab {
    background: #13151f;
    color: #5a627e;
    padding: 8px 8px 8px 16px;
    border: none;
    border-top: 2px solid transparent;
    border-right: 1px solid #1a1d28;
    font-size: 12px;
    font-weight: 500;
    min-width: 96px;
    max-width: 200px;
}
QTabWidget#contentTabs QTabBar::tab:selected {
    background: #1e2138;
    color: #e6e9f6;
    border-top: 2px solid #c9a84c;
}
QTabWidget#contentTabs QTabBar::tab:hover:!selected {
    background: #181b2a;
    color: #828ab0;
}
QTabWidget#contentTabs QTabBar::close-button {
    subcontrol-position: right;
    margin-right: 4px;
    border-radius: 4px;
}
QTabWidget#contentTabs QTabBar::close-button:hover {
    background: #4a2530;
}

/* ── Tree widget ───────────────────────────────────────────────── */
QTreeWidget {
    background: #13151b;
    border: none;
    outline: none;
    show-decoration-selected: 1;
}
QTreeWidget::item {
    padding: 5px 4px;
    border-radius: 5px;
    margin: 1px 4px;
}
QTreeWidget::item:hover    { background: #1e2130; }
QTreeWidget::item:selected { background: #4d3f18; color: #f2e8cc; }
QTreeWidget::branch { background: #13151b; }
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: none;
}

/* ── List widgets (results / bookmarks) ────────────────────────── */
QListWidget {
    background: #13151b;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 10px 13px;
    border-bottom: 1px solid #1d1f28;
}
QListWidget::item:hover    { background: #1e2130; }
QListWidget::item:selected { background: #4d3f18; color: #f2e8cc; }

/* ── Status bar ────────────────────────────────────────────────── */
QStatusBar {
    background: #0e0f14;
    color: #44485c;
    font-size: 11px;
    border-top: 1px solid #1d1f28;
}

/* ── Context menu ──────────────────────────────────────────────── */
QMenu {
    background: #1e2130;
    color: #c9ccd6;
    border: 1px solid #2e3348;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item { padding: 7px 22px; border-radius: 4px; }
QMenu::item:selected { background: #c9a84c; color: #1a1c26; }
"""

# ── Right-panel nav bar stylesheet (light strip above content) ────────────────

NAV_BAR_STYLE = """
QWidget#navBar {
    background: #1e2130;
    border-bottom: 1px solid #2a2d3a;
}
QPushButton {
    background: transparent;
    color: #8087a8;
    border: 1px solid #2e3348;
    border-radius: 7px;
    padding: 6px 15px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover   { background: #272b40; color: #d4d8e8; border-color: #c9a84c; }
QPushButton:pressed { background: #c9a84c; color: #1a1c26; border-color: #c9a84c; }
QPushButton:disabled { color: #303444; border-color: #1e2030; background: transparent; }
"""

# ── In-page find bar stylesheet ───────────────────────────────────────────────

FIND_BAR_STYLE = """
QWidget#findBar {
    background: #1a1c26;
    border-bottom: 1px solid #2a2d3a;
}
QWidget#findBar QLineEdit {
    background: #23263a;
    border: 1px solid #383c52;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    color: #e0e2f0;
}
QWidget#findBar QLineEdit:focus { border-color: #c9a84c; }
QWidget#findBar QPushButton {
    background: #23263a;
    color: #b8bccf;
    border: 1px solid #383c52;
    border-radius: 6px;
    padding: 4px 0;
    font-size: 12px;
}
QWidget#findBar QPushButton:hover   { background: #2d3048; color: #c9a84c; border-color: #c9a84c; }
QWidget#findBar QPushButton:pressed { background: #c9a84c; color: #1a1c26; }
"""


# ── FTS search worker ─────────────────────────────────────────────────────────

class SearchWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, db_path: str, query: str):
        super().__init__()
        self.db_path = db_path
        self.query   = query

    def run(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c    = conn.cursor()
            fts_query = f'"{self.query.replace(chr(34), "")}"'
            try:
                c.execute(
                    """SELECT p.page_url, p.title, p.book_name, p.book_code,
                              snippet(pages_fts, 2, '**', '**', '…', 25) AS snip
                       FROM   pages_fts
                       JOIN   pages p ON pages_fts.page_url = p.page_url
                       WHERE  pages_fts MATCH ?
                       ORDER  BY rank
                       LIMIT  300""",
                    (fts_query,),
                )
            except Exception:
                plain = " ".join(self.query.split())
                c.execute(
                    """SELECT p.page_url, p.title, p.book_name, p.book_code,
                              snippet(pages_fts, 2, '**', '**', '…', 25) AS snip
                       FROM   pages_fts
                       JOIN   pages p ON pages_fts.page_url = p.page_url
                       WHERE  pages_fts MATCH ?
                       ORDER  BY rank
                       LIMIT  300""",
                    (plain,),
                )
            rows = c.fetchall()
            conn.close()
            self.results_ready.emit(rows)
        except Exception:
            self.results_ready.emit([])


# ── dnd:// link interception ──────────────────────────────────────────────────

if HAS_WEBENGINE:
    class DnDPage(QWebEnginePage):
        dnd_navigate        = pyqtSignal(str)
        dnd_navigate_newtab = pyqtSignal(str)

        def _route(self, page_url: str):
            """Emit the right signal for a page_url based on Ctrl/middle-click."""
            mods = QApplication.keyboardModifiers()
            btns = QApplication.mouseButtons()
            if (mods & Qt.ControlModifier) or (btns & Qt.MiddleButton):
                self.dnd_navigate_newtab.emit(page_url)
            else:
                self.dnd_navigate.emit(page_url)

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            # Internal dnd:// links (TOC, screens, our own rewrites)
            if url.scheme() == "dnd":
                page_url = url.path().lstrip("/")
                if page_url:
                    self._route(page_url)
                return False
            # Cross-reference links in scraped pages are relative http links back
            # to the source site — route the page ones through the app so they
            # load from the DB with our styling instead of the live website.
            # (Same-page anchors and other links fall through to default.)
            if nav_type == QWebEnginePage.NavigationTypeLinkClicked and \
                    url.toString().startswith(BASE_URL):
                page_url = url.toString()[len(BASE_URL):].split("#")[0].split("?")[0]
                if page_url.lower().endswith((".htm", ".html")):
                    self._route(page_url)
                    return False
            return True


# ── Content viewer ────────────────────────────────────────────────────────────

class ContentView(QWidget):
    page_requested        = pyqtSignal(str)
    page_requested_newtab = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #2a2d36;")
        self._zoom = 1.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE:
            self._dnd_page = DnDPage()
            self._dnd_page.dnd_navigate.connect(self.page_requested)
            self._dnd_page.dnd_navigate_newtab.connect(self.page_requested_newtab)
            self._view = QWebEngineView()
            self._view.setPage(self._dnd_page)
            # Zoom factor resets whenever new content loads, so re-apply it each time.
            self._view.loadFinished.connect(lambda ok: self._view.setZoomFactor(self._zoom))
        else:
            self._view = QTextBrowser()
            self._view.setStyleSheet("background: #2a2d36; color: #d4d6de;")
            self._view.setOpenExternalLinks(False)
            self._view.anchorClicked.connect(self._on_anchor)
            self._view.setFont(QFont("Segoe UI", 11))

        layout.addWidget(self._view)

    # ── Zoom ──────────────────────────────────────────────────────────────
    def apply_zoom(self, factor: float):
        self._zoom = factor
        if HAS_WEBENGINE:
            self._view.setZoomFactor(factor)
        else:
            f = self._view.font()
            f.setPointSizeF(11 * factor)
            self._view.setFont(f)

    # ── In-page find ──────────────────────────────────────────────────────
    def find(self, text: str, forward: bool = True):
        if not HAS_WEBENGINE:
            return
        flags = QWebEnginePage.FindFlags()
        if not forward:
            flags |= QWebEnginePage.FindBackward
        self._view.findText(text, flags)

    def clear_find(self):
        if HAS_WEBENGINE:
            self._view.findText("")

    def _on_anchor(self, url: QUrl):
        if url.scheme() == "dnd":
            page_url = url.path().lstrip("/")
            if page_url:
                self.page_requested.emit(page_url)

    # Base overrides applied to every loaded page (dark background, app font).
    _BASE_INJECT = (
        "html,body{background-color:#2a2d36!important;color:#d4d6de!important;"
        "font-family:'Segoe UI',system-ui,sans-serif!important;}"
        "body,p,td,th,li,a,span,div,font,h1,h2,h3,h4,h5,h6,b,i,em,strong,center,blockquote"
        "{font-family:'Segoe UI',system-ui,sans-serif!important;}"
        "a{color:#7aabdb!important;}"
        "img{max-width:100%!important;height:auto!important;}"
        "table{border-collapse:collapse;max-width:100%!important;}"
        "td,th{border-color:#3a3e50!important;}"
    )

    # Extra typography for scraped rules pages: a centred, comfortable reading
    # column instead of edge-to-edge text.  (Not applied to the generated TOC,
    # which has its own layout.)
    _READING_INJECT = (
        "body{max-width:820px!important;margin:0 auto!important;"
        "padding:32px 36px 72px!important;font-size:15px!important;"
        "line-height:1.66!important;}"
        "p,li,td{line-height:1.66!important;}"
        "p{margin:0 0 12px!important;}"
    )

    _TOC_LINK_RE = re.compile(
        r'<a\b[^>]*>\s*(?:(?:Back\s+to\s+)?Table\s+of\s+Contents)\s*</a>',
        re.IGNORECASE,
    )

    def load(self, html: str, page_url: str, reading: bool = True):
        folder     = page_url.rsplit("/", 1)[0] + "/" if "/" in page_url else page_url + "/"
        base       = QUrl(BASE_URL + folder)
        book_code  = page_url.split("/")[0] if "/" in page_url else ""

        # Replace the site's "Table of Contents" link with our internal TOC
        if book_code:
            html = self._TOC_LINK_RE.sub(
                f'<a href="dnd:///toc/{book_code}">Table of Contents</a>',
                html,
            )

        # Inject background / colour overrides (+ reading typography for pages)
        css = self._BASE_INJECT + (self._READING_INJECT if reading else "")
        style = f"<style>{css}</style>"
        if "</head>" in html:
            html = html.replace("</head>", style + "</head>", 1)
        else:
            html = style + html

        if HAS_WEBENGINE:
            self._view.setHtml(html, base)
        else:
            self._view.setHtml(html)

    def clear(self):
        if HAS_WEBENGINE:
            self._view.setUrl(QUrl("about:blank"))
        else:
            self._view.clear()


# ── Per-tab state ─────────────────────────────────────────────────────────────

class TabContext:
    """Holds all state that belongs to one content tab."""
    def __init__(self, view: ContentView):
        self.view                          = view
        self.history:       list[str]      = []
        self.history_pos:   int            = -1
        self.current_page_url: str | None  = None


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = sqlite3.connect(str(DB_PATH))
        self.user_db = sqlite3.connect(str(USER_DB_PATH))
        self._init_user_db()
        self._settings = QSettings(str(_user_data_dir() / "settings.ini"), QSettings.IniFormat)
        self._search_worker: SearchWorker | None = None
        self._url_to_tree_item: dict = {}
        self._book_chapters:    dict = {}
        self._book_page_order:  dict = {}   # book_code -> ordered list of page_urls
        self._tabs: list[TabContext] = []   # populated by _build_ui → _new_tab
        self._zoom: float = float(self._settings.value("zoom", 1.0))

        # Built-in screens: destination key -> (html generator, tab title, status text)
        self._screens = {
            "splash":   (generate_splash_html,  "Home",           "  D&D 2nd Edition  ·  Rules Reference"),
            "dmscreen": (generate_dmscreen_html, "DM Screen",      "  DM Screen  ·  Quick Reference"),
            "actions":  (generate_actions_html,  "Actions",        "  Actions Screen  ·  Quick Reference"),
            "chargen":  (generate_chargen_html,  "Char. Creation", "  Character Creation  ·  Step-by-Step Walkthrough"),
        }

        self._build_ui()
        self._setup_shortcuts()
        self._load_topics()
        self._load_bookmarks()
        self._restore_session()

    def _init_user_db(self):
        """Create the bookmarks table in the writable user DB, migrating any legacy rows."""
        c = self.user_db.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS bookmarks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "page_url TEXT UNIQUE, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        self.user_db.commit()
        # One-time migration: copy bookmarks that used to live in the bundled DB.
        c.execute("SELECT COUNT(*) FROM bookmarks")
        if c.fetchone()[0] == 0:
            try:
                old = self.db.cursor()
                old.execute("SELECT page_url FROM bookmarks ORDER BY created_at")
                for (url,) in old.fetchall():
                    c.execute("INSERT OR IGNORE INTO bookmarks (page_url) VALUES (?)", (url,))
                self.user_db.commit()
            except sqlite3.Error:
                pass  # no legacy bookmarks table — nothing to migrate

    # ── Per-tab properties (redirect to the active TabContext) ────────────────

    @property
    def content(self) -> ContentView:
        return self._tabs[self._content_tabs.currentIndex()].view

    @property
    def _history(self) -> list:
        return self._tabs[self._content_tabs.currentIndex()].history

    @_history.setter
    def _history(self, val: list):
        self._tabs[self._content_tabs.currentIndex()].history = val

    @property
    def _history_pos(self) -> int:
        return self._tabs[self._content_tabs.currentIndex()].history_pos

    @_history_pos.setter
    def _history_pos(self, val: int):
        self._tabs[self._content_tabs.currentIndex()].history_pos = val

    @property
    def current_page_url(self):
        return self._tabs[self._content_tabs.currentIndex()].current_page_url

    @current_page_url.setter
    def current_page_url(self, val):
        self._tabs[self._content_tabs.currentIndex()].current_page_url = val

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("D&D 2nd Edition Rules")
        self.setMinimumSize(1200, 720)

        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # ── Left sidebar ───────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setMaximumWidth(400)
        sidebar.setMinimumWidth(260)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 16, 14, 12)
        sl.setSpacing(12)

        # App title / branding strip
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_label = QLabel("⚔  D&D 2e Rules")
        title_label.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 700; "
            "letter-spacing: 0.04em;"
        )
        title_row.addWidget(title_label)
        title_row.addStretch()
        sl.addLayout(title_row)

        # Search box
        search_row = QHBoxLayout()
        search_row.setSpacing(7)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search rules…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.returnPressed.connect(self._do_search)
        search_btn = QPushButton("Go")
        search_btn.setFixedWidth(44)
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_box)
        search_row.addWidget(search_btn)
        sl.addLayout(search_row)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.browse_tree = QTreeWidget()
        self.browse_tree.setHeaderHidden(True)
        self.browse_tree.setAnimated(True)
        self.browse_tree.setIndentation(16)
        self.browse_tree.setFont(QFont("Segoe UI", 11))
        self.browse_tree.itemClicked.connect(self._on_tree_click)
        self.tabs.addTab(self.browse_tree, "Browse")

        self.results_list = QListWidget()
        self.results_list.setWordWrap(True)
        self.results_list.setSpacing(1)
        self.results_list.itemClicked.connect(self._on_result_click)
        self.tabs.addTab(self.results_list, "Results")

        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setWordWrap(True)
        self.bookmarks_list.setSpacing(1)
        self.bookmarks_list.itemClicked.connect(self._on_bookmark_click)
        self.bookmarks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks_list.customContextMenuRequested.connect(self._bookmark_ctx)
        self.tabs.addTab(self.bookmarks_list, "Bookmarks")

        sl.addWidget(self.tabs)

        # Bookmark button
        self.bookmark_btn = QPushButton("☆   Bookmark This Page")
        self.bookmark_btn.setEnabled(False)
        self.bookmark_btn.setMinimumHeight(36)
        self.bookmark_btn.setCursor(Qt.PointingHandCursor)
        self.bookmark_btn.clicked.connect(self._toggle_bookmark)
        sl.addWidget(self.bookmark_btn)

        splitter.addWidget(sidebar)

        # ── Right panel ────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background: #2a2d36;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Navigation bar
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        nav_bar.setFixedHeight(48)
        nav_bar.setStyleSheet(NAV_BAR_STYLE)
        nl = QHBoxLayout(nav_bar)
        nl.setContentsMargins(12, 7, 12, 7)
        nl.setSpacing(7)

        self.back_btn = QPushButton("◀  Back")
        self.back_btn.setEnabled(False)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self._go_back)

        self.fwd_btn = QPushButton("Forward  ▶")
        self.fwd_btn.setEnabled(False)
        self.fwd_btn.setCursor(Qt.PointingHandCursor)
        self.fwd_btn.clicked.connect(self._go_forward)

        self.prev_btn = QPushButton("‹  Prev")
        self.prev_btn.setEnabled(False)
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.setToolTip("Previous page in this book  ( [ )")
        self.prev_btn.clicked.connect(self._go_prev_page)

        self.next_btn = QPushButton("Next  ›")
        self.next_btn.setEnabled(False)
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setToolTip("Next page in this book  ( ] )")
        self.next_btn.clicked.connect(self._go_next_page)

        self.newtab_btn = QPushButton("＋  New Tab")
        self.newtab_btn.setCursor(Qt.PointingHandCursor)
        self.newtab_btn.setToolTip("Open a new tab")
        self.newtab_btn.clicked.connect(lambda: self._new_tab())

        self.dmscreen_btn = QPushButton("⚔  DM Screen")
        self.dmscreen_btn.setCursor(Qt.PointingHandCursor)
        self.dmscreen_btn.clicked.connect(lambda: self._show_dmscreen())

        self.actions_btn = QPushButton("⚡  Actions")
        self.actions_btn.setCursor(Qt.PointingHandCursor)
        self.actions_btn.clicked.connect(lambda: self._show_actions())

        self.chargen_btn = QPushButton("✦  Character Creation")
        self.chargen_btn.setCursor(Qt.PointingHandCursor)
        self.chargen_btn.clicked.connect(lambda: self._show_chargen())

        self.ask_btn = QPushButton("✦  Jarvis")
        self.ask_btn.setCursor(Qt.PointingHandCursor)
        self.ask_btn.setToolTip("Ask a 2e rules question in plain English (local AI assistant)")
        self.ask_btn.clicked.connect(lambda: self._show_ask())

        nl.addWidget(self.back_btn)
        nl.addWidget(self.fwd_btn)
        nl.addSpacing(10)
        nl.addWidget(self.prev_btn)
        nl.addWidget(self.next_btn)
        nl.addSpacing(10)
        nl.addWidget(self.newtab_btn)
        nl.addStretch()
        nl.addWidget(self.ask_btn)
        nl.addWidget(self.chargen_btn)
        nl.addWidget(self.actions_btn)
        nl.addWidget(self.dmscreen_btn)
        rl.addWidget(nav_bar)

        # Find-on-page bar (hidden until Ctrl+F)
        self._find_bar = QWidget()
        self._find_bar.setObjectName("findBar")
        self._find_bar.setStyleSheet(FIND_BAR_STYLE)
        fl = QHBoxLayout(self._find_bar)
        fl.setContentsMargins(12, 6, 12, 6)
        fl.setSpacing(6)
        find_label = QLabel("Find")
        find_label.setStyleSheet("color:#8087a8; font-size:11px; font-weight:600;")
        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find on page…")
        self._find_input.returnPressed.connect(lambda: self._find_next(True))
        self._find_input.textChanged.connect(lambda _t: self._find_next(True))
        find_prev = QPushButton("▲")
        find_prev.setFixedWidth(30)
        find_prev.setCursor(Qt.PointingHandCursor)
        find_prev.setToolTip("Previous match (Shift+Enter)")
        find_prev.clicked.connect(lambda: self._find_next(False))
        find_next = QPushButton("▼")
        find_next.setFixedWidth(30)
        find_next.setCursor(Qt.PointingHandCursor)
        find_next.setToolTip("Next match (Enter)")
        find_next.clicked.connect(lambda: self._find_next(True))
        find_close = QPushButton("✕")
        find_close.setFixedWidth(30)
        find_close.setCursor(Qt.PointingHandCursor)
        find_close.setToolTip("Close (Esc)")
        find_close.clicked.connect(self._hide_find_bar)
        fl.addWidget(find_label)
        fl.addWidget(self._find_input, 1)
        fl.addWidget(find_prev)
        fl.addWidget(find_next)
        fl.addWidget(find_close)
        self._find_bar.setVisible(False)
        rl.addWidget(self._find_bar)

        self._content_tabs = QTabWidget()
        self._content_tabs.setObjectName("contentTabs")
        self._content_tabs.setTabsClosable(True)
        self._content_tabs.setMovable(True)
        self._content_tabs.setDocumentMode(True)
        self._content_tabs.tabCloseRequested.connect(self._close_tab)
        self._content_tabs.currentChanged.connect(self._on_tab_changed)

        rl.addWidget(self._content_tabs)
        self._new_tab(show_splash=False)   # creates the initial blank tab

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 860])

        # Status bar
        self.status = QStatusBar()
        self.status.setSizeGripEnabled(False)
        if not HAS_WEBENGINE:
            self.status.showMessage(
                "PyQtWebEngine not found — install with:  pip install PyQtWebEngine"
            )
        self.setStatusBar(self.status)

    # ── Keyboard shortcuts ──────────────────────────────────────────────────

    def _setup_shortcuts(self):
        def sc(seq, slot):
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(slot)
            return s

        sc("Ctrl+T",       lambda: self._new_tab())
        sc("Ctrl+W",       lambda: self._close_tab(self._content_tabs.currentIndex()))
        sc("Ctrl+Tab",     lambda: self._cycle_tab(1))
        sc("Ctrl+Shift+Tab", lambda: self._cycle_tab(-1))
        sc("Ctrl+PgDown",  lambda: self._cycle_tab(1))
        sc("Ctrl+PgUp",    lambda: self._cycle_tab(-1))
        sc("Alt+Left",     self._go_back)
        sc("Alt+Right",    self._go_forward)
        sc("[",            self._go_prev_page)
        sc("]",            self._go_next_page)
        sc("Ctrl+K",       self._focus_search)
        sc("Ctrl+F",       self._show_find_bar)
        sc("Escape",       self._hide_find_bar)
        sc("Ctrl+=",       self._zoom_in)
        sc("Ctrl++",       self._zoom_in)
        sc("Ctrl+-",       self._zoom_out)
        sc("Ctrl+0",       self._zoom_reset)
        sc("F3",           lambda: self._find_next(True))
        sc("Shift+F3",     lambda: self._find_next(False))
        for i in range(1, 10):
            sc(f"Ctrl+{i}", lambda n=i: self._goto_tab(n - 1))

        # Ctrl+wheel zoom, caught application-wide
        QApplication.instance().installEventFilter(self)

    def _cycle_tab(self, delta: int):
        n = self._content_tabs.count()
        if n:
            self._content_tabs.setCurrentIndex((self._content_tabs.currentIndex() + delta) % n)

    def _goto_tab(self, idx: int):
        if 0 <= idx < self._content_tabs.count():
            self._content_tabs.setCurrentIndex(idx)

    def _focus_search(self):
        self.tabs.setCurrentIndex(0)
        self.search_box.setFocus()
        self.search_box.selectAll()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and (QApplication.keyboardModifiers() & Qt.ControlModifier):
            if event.angleDelta().y() > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            return True
        return super().eventFilter(obj, event)

    # ── Zoom ────────────────────────────────────────────────────────────────

    def _apply_zoom_all(self):
        for ctx in self._tabs:
            ctx.view.apply_zoom(self._zoom)

    def _set_zoom(self, z: float):
        self._zoom = max(0.5, min(2.5, round(z, 2)))
        self._apply_zoom_all()
        self.status.showMessage(f"  Zoom: {int(self._zoom * 100)}%")

    def _zoom_in(self):    self._set_zoom(self._zoom + 0.1)
    def _zoom_out(self):   self._set_zoom(self._zoom - 0.1)
    def _zoom_reset(self): self._set_zoom(1.0)

    # ── In-page find ────────────────────────────────────────────────────────

    def _show_find_bar(self):
        self._find_bar.setVisible(True)
        self._find_input.setFocus()
        self._find_input.selectAll()
        if self._find_input.text():
            self._find_next(True)

    def _hide_find_bar(self):
        if not self._find_bar.isVisible():
            return
        self._find_bar.setVisible(False)
        self.content.clear_find()
        self.content._view.setFocus()

    def _find_next(self, forward: bool = True):
        self.content.find(self._find_input.text(), forward)

    # ── Chapter detection ──────────────────────────────────────────────────

    @staticmethod
    def _extract_chapter_name(subtopic: str) -> str:
        m = re.match(
            r"^(.+?)--\s*(Chapter\s+\d+|Part\s+\d+|Book\s+\d+|Appendix\s+\w+)",
            subtopic, re.I,
        )
        if m:
            return f"{m.group(2).strip()}: {m.group(1).strip()}"
        return subtopic.split("(")[0].strip()

    def _get_chapters(self, book_code: str) -> list[dict]:
        c = self.db.cursor()
        c.execute(
            """SELECT DISTINCT te.page_url, te.subtopic
               FROM   toc_entries te
               WHERE  te.book_code = ?
               ORDER  BY te.page_url""",
            (book_code,),
        )
        all_entries = c.fetchall()
        if not all_entries:
            return []

        c.execute(
            """SELECT te.subtopic, te.page_url
               FROM   toc_entries te
               WHERE  te.book_code = ?
                 AND  (te.subtopic LIKE '%-- Chapter %'
                    OR te.subtopic LIKE '%-- Part %'
                    OR te.subtopic LIKE '%-- Book %'
                    OR te.subtopic LIKE '%-- Appendix %')
               ORDER  BY te.page_url""",
            (book_code,),
        )
        markers = c.fetchall()
        return (
            self._chapters_from_markers(all_entries, markers)
            if markers
            else self._chapters_by_letter(all_entries)
        )

    def _chapters_from_markers(self, all_entries, markers) -> list[dict]:
        marker_map = {url: sub for sub, url in markers}
        marker_set = set(marker_map)
        chapters, pre, current = [], [], None

        for page_url, subtopic in all_entries:
            if page_url in marker_set:
                if current is not None:
                    chapters.append(current)
                elif pre:
                    chapters.append({"name": "Introduction", "page_url": pre[0][0], "entries": pre})
                    pre = []
                current = {
                    "name":     self._extract_chapter_name(marker_map[page_url]),
                    "page_url": page_url,
                    "entries":  [(page_url, subtopic)],
                }
            elif current is not None:
                current["entries"].append((page_url, subtopic))
            else:
                pre.append((page_url, subtopic))

        if current is not None:
            chapters.append(current)
        if pre:
            chapters.insert(0, {"name": "Introduction", "page_url": pre[0][0], "entries": pre})
        return chapters

    def _chapters_by_letter(self, all_entries) -> list[dict]:
        by_letter = defaultdict(list)
        for page_url, subtopic in all_entries:
            letter = subtopic[0].upper() if subtopic else "#"
            by_letter[letter].append((page_url, subtopic))
        return [
            {"name": letter, "page_url": entries[0][0], "entries": entries}
            for letter, entries in sorted(by_letter.items())
        ]

    # ── TOC page generation ────────────────────────────────────────────────

    def _generate_toc_html(self, book_code: str, chapters: list[dict]) -> str:
        book_name  = BOOK_NAMES.get(book_code, book_code)
        accent     = BOOK_ACCENT_COLORS.get(book_code, "#8b0000")
        hr_by_chap = self._get_all_house_rules_for_book(book_code)

        rows = ""
        for i, ch in enumerate(chapters, 1):
            count = len(ch["entries"])
            num   = f"{i:02d}"
            if ch.get("page_url"):
                name_html = f'<a href="dnd:///{ch["page_url"]}">{ch["name"]}</a>'
            else:
                name_html = ch["name"]

            # Find house rules whose keyword appears in this chapter's name
            ch_rules: list = []
            for kw, rules in hr_by_chap.items():
                if (kw + ":") in ch["name"] or ch["name"] == kw:
                    ch_rules.extend(rules)

            badge = ""
            hr_block = ""
            if ch_rules:
                badge = (
                    f' <span style="background:{accent}22;color:{accent};font-size:9px;'
                    f'font-weight:700;padding:2px 7px;border-radius:3px;'
                    f'letter-spacing:.06em;vertical-align:middle;">⚔ HR</span>'
                )
                by_cat: dict = {}
                for cat, text in ch_rules:
                    by_cat.setdefault(cat, []).append(text)
                inner = ""
                for cat, texts in by_cat.items():
                    inner += f'<div class="hr-cat">{cat}</div><ul class="hr-list">'
                    for text in texts:
                        inner += f"<li>{text}</li>"
                    inner += "</ul>"
                hr_block = f'<div class="hr-block">{inner}</div>'

            rows += (
                f'    <div class="row">'
                f'<span class="num">{num}</span>'
                f'<span class="name">{name_html}{badge}</span>'
                f'<span class="count">{count}</span>'
                f'</div>\n'
                f'{hr_block}'
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: #2a2d36;
    min-height: 100vh;
    padding: 56px 72px;
  }}
  .book-tag {{
    display: inline-block;
    background: {accent}18;
    color: {accent};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 4px;
    margin-bottom: 14px;
  }}
  h1 {{
    font-size: 2.4em;
    font-weight: 800;
    color: #e4e6f0;
    line-height: 1.1;
    margin-bottom: 6px;
  }}
  .divider {{
    height: 3px;
    width: 48px;
    background: {accent};
    border-radius: 2px;
    margin: 18px 0 36px;
  }}
  .toc {{ max-width: 720px; }}
  .row {{
    display: flex;
    align-items: baseline;
    gap: 18px;
    padding: 13px 10px;
    border-radius: 8px;
    transition: background .12s;
    cursor: default;
  }}
  .row:hover {{ background: #323642; }}
  .num {{
    font-size: 11px;
    font-weight: 700;
    color: #bdc3d0;
    min-width: 22px;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }}
  .name {{
    flex: 1;
    font-size: 15px;
    color: #c8cad8;
    font-weight: 500;
  }}
  .name a {{ color: {accent}; text-decoration: none; }}
  .name a:hover {{ text-decoration: underline; }}
  .count {{
    font-size: 12px;
    color: #9ca3af;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }}
  .count::after {{ content: " entries"; }}
  .hr-block {{
    margin: 0 0 6px 50px;
    padding: 10px 14px 12px;
    background: {accent}0f;
    border-left: 2px solid {accent}55;
    border-radius: 0 4px 4px 0;
  }}
  .hr-cat {{
    color: {accent};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .09em;
    text-transform: uppercase;
    margin-bottom: 4px;
    margin-top: 10px;
  }}
  .hr-cat:first-child {{ margin-top: 0; }}
  .hr-list {{
    margin: 0 0 0 14px;
    padding: 0;
    color: #9ca3b8;
    font-size: 12px;
    line-height: 1.7;
  }}
  hr.sep {{ border: none; border-top: 1px solid #3a3e50; margin: 2px 0; }}
</style>
</head>
<body>
  <div class="book-tag">2nd Edition AD&amp;D</div>
  <h1>{book_name}</h1>
  <div class="divider"></div>
  <div class="toc">
{rows}
  </div>
</body>
</html>"""

    # ── Browse tree ────────────────────────────────────────────────────────

    def _load_topics(self):
        self.browse_tree.clear()
        self._url_to_tree_item.clear()
        self._book_chapters.clear()
        self._book_page_order.clear()

        total_entries = 0
        for book_code in BOOK_ORDER:
            book_name = BOOK_NAMES.get(book_code, book_code)
            chapters  = self._get_chapters(book_code)
            if not chapters:
                continue

            self._book_chapters[book_code] = chapters
            # Flat reading order for this book (Prev/Next), duplicates removed.
            order, seen = [], set()
            for ch in chapters:
                for page_url, _sub in ch["entries"]:
                    if page_url not in seen:
                        seen.add(page_url)
                        order.append(page_url)
            self._book_page_order[book_code] = order
            tree_color = BOOK_TREE_COLORS.get(book_code, "#c9ccd6")

            # Book node
            book_item = QTreeWidgetItem([f"  {book_name}"])
            book_item.setFont(0, QFont("Segoe UI", 12, QFont.Bold))
            book_item.setForeground(0, QColor(tree_color))
            book_item.setData(0, Qt.UserRole, ("book", book_code))

            for ch in chapters:
                # Chapter node
                chap_item = QTreeWidgetItem([f"  {ch['name']}"])
                chap_item.setFont(0, QFont("Segoe UI", 10, QFont.DemiBold))
                chap_item.setForeground(0, QColor("#8a90a8"))
                chap_item.setData(0, Qt.UserRole, ("chapter", ch.get("page_url")))

                for page_url, subtopic in ch["entries"]:
                    # Strip the "(Book Name)" suffix from display label
                    label = re.sub(r"\s*\([^)]+\)\s*$", "", subtopic).strip()
                    entry_item = QTreeWidgetItem([f"   {label}"])
                    entry_item.setFont(0, QFont("Segoe UI", 10))
                    entry_item.setForeground(0, QColor("#7a8098"))
                    entry_item.setData(0, Qt.UserRole, ("entry", page_url))
                    entry_item.setToolTip(0, subtopic)
                    chap_item.addChild(entry_item)
                    self._url_to_tree_item[page_url] = entry_item
                    total_entries += 1

                book_item.addChild(chap_item)

            self.browse_tree.addTopLevelItem(book_item)

        book_count = self.browse_tree.topLevelItemCount()
        self.status.showMessage(
            f"  {book_count} books  ·  {total_entries} entries"
        )

    def _on_tree_click(self, item: QTreeWidgetItem, _col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        kind, value = data

        if kind == "book":
            self._show_toc(value)
        elif kind == "chapter" and value:
            self._load_page(value)
        elif kind == "entry" and value:
            self._load_page(value)

    def _sync_tree_selection(self, page_url: str):
        item = self._url_to_tree_item.get(page_url)
        if not item:
            return
        chap_item = item.parent()
        if chap_item:
            book_item = chap_item.parent()
            if book_item and not book_item.isExpanded():
                book_item.setExpanded(True)
            if not chap_item.isExpanded():
                chap_item.setExpanded(True)
        self.browse_tree.blockSignals(True)
        self.browse_tree.setCurrentItem(item)
        self.browse_tree.scrollToItem(item, QTreeWidget.PositionAtCenter)
        self.browse_tree.blockSignals(False)

    # ── Navigation ─────────────────────────────────────────────────────────
    #
    # A "destination" is a single canonical string that doubles as a history
    # entry.  Every navigation path — link clicks, history, session restore —
    # funnels through _navigate(), which renders the destination once and
    # (optionally) pushes it onto the active tab's history.
    #
    #   "splash" | "dmscreen" | "actions" | "chargen"   built-in screens
    #   "toc:<BOOK>"                                     a book's contents page
    #   "<BOOK>/<page>.htm"                              a scraped rules page

    @staticmethod
    def _link_to_destination(url: str) -> str:
        """Map a dnd:// link path to a canonical destination."""
        if url.startswith("toc/"):
            return "toc:" + url[4:]
        if url.startswith("screen/"):
            return url[len("screen/"):]   # screen/chargen -> chargen
        return url                        # a page_url

    def _on_content_navigate(self, url: str):
        """Handle a normal dnd:// link click from the content viewer."""
        # Interactive "Ask the Rules" routes are handled in place (no history entry).
        if url.startswith("ask/"):
            self._ask_question(unquote(url[len("ask/"):]).strip())
            return
        if url.startswith("ask-setmodel/"):
            self._settings.setValue("askModel", unquote(url[len("ask-setmodel/"):]).strip())
            self._settings.sync()
            self._render_ask()
            return
        if url == "ask-refresh":
            self._render_ask()
            return
        # A cited link clicked on the Jarvis page opens in a new tab so the
        # question/answer stays put.
        if self._on_jarvis_page():
            self._new_tab(show_splash=False)     # opens and switches to the new tab
            self._navigate(self._link_to_destination(url))
            return
        self._navigate(self._link_to_destination(url))

    def _on_jarvis_page(self) -> bool:
        h, p = self._history, self._history_pos
        return bool(h) and 0 <= p < len(h) and h[p] == "ask"

    def _navigate(self, dest: str, add_to_history: bool = True):
        """Render a destination and optionally record it in the tab's history."""
        if not self._render_destination(dest):
            return   # render failed (e.g. page not found) — leave history intact
        if add_to_history:
            self._history = self._history[: self._history_pos + 1]
            self._history.append(dest)
            self._history_pos = len(self._history) - 1
        self._update_nav_buttons()

    def _render_destination(self, dest: str) -> bool:
        """Display a destination's content. Returns False if it could not be shown."""
        if dest.startswith("toc:"):
            return self._render_toc(dest[4:])
        if dest == "ask":
            return self._render_ask()
        if dest in self._screens:
            return self._render_screen(dest)
        return self._render_page(dest)

    def _render_screen(self, key: str) -> bool:
        generator, title, status = self._screens[key]
        self.content._view.setHtml(generator())
        self.current_page_url = None
        self.bookmark_btn.setEnabled(False)
        self._set_tab_title(title)
        self.status.showMessage(status)
        return True

    def _render_toc(self, book_code: str) -> bool:
        chapters = self._book_chapters.get(book_code, [])
        html     = self._generate_toc_html(book_code, chapters)
        self.content.load(html, book_code + "/", reading=False)
        self.current_page_url = None
        self.bookmark_btn.setEnabled(False)
        self._set_tab_title(f"{book_code} — Contents")
        self.status.showMessage(f"  {BOOK_NAMES.get(book_code, book_code)}  ·  Table of Contents")
        return True

    # Thin public entry points used by the nav-bar buttons and tree.
    def _show_splash(self):   self._navigate("splash")
    def _show_dmscreen(self): self._navigate("dmscreen")
    def _show_actions(self):  self._navigate("actions")
    def _show_chargen(self):  self._navigate("chargen")
    def _show_ask(self):      self._navigate("ask")
    def _show_toc(self, book_code: str): self._navigate("toc:" + book_code)

    # ── Ask the Rules (local Ollama model) ──────────────────────────────────

    def _ask_model(self, models=None) -> str:
        chosen = (self._settings.value("askModel", "") or "").strip()
        if models and chosen not in models:
            chosen = pick_default_model(models)
        return chosen or DEFAULT_MODEL

    def _render_ask(self, force_setup: bool = False) -> bool:
        """Render the Ask page (Ollama setup help, or the ask box)."""
        ok, models = ollama_status()
        model = self._ask_model(models)
        state = "ready" if (ok and models) else "setup"
        self.content._view.setHtml(
            askscreen_html.generate(state, model=model, models=models, ollama_ok=ok)
        )
        self.current_page_url = None
        self.bookmark_btn.setEnabled(False)
        self._set_tab_title("Jarvis")
        self.status.showMessage("  Jarvis  ·  your local rules assistant")
        return True

    def _ask_question(self, question: str):
        if not question:
            return
        ok, models = ollama_status()
        if not ok or not models:
            self._render_ask()          # fall back to the setup instructions
            return

        model = self._ask_model(models)
        view  = self.content._view      # answer renders onto the tab that asked
        self._ask_view = view
        self._ask_question_text = question
        self._ask_model_id = model
        self._ask_models = models
        view.setHtml(askscreen_html.generate("loading", model=model, models=models, question=question))
        self._set_tab_title("Jarvis")
        self.status.showMessage(f'  Asking {model}:  "{question[:50]}"')

        worker = AskWorker(str(DB_PATH), model, question)
        worker.status.connect(self._ask_status)
        worker.finished.connect(self._ask_finished)
        worker.failed.connect(self._ask_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        self._ask_worker = worker
        worker.start()

    def _ask_status(self, msg: str):
        view = getattr(self, "_ask_view", None)
        if view is None:
            return
        js = ("var s=document.getElementById('ask-status');"
              "if(s){s.innerHTML='<span class=\"spinner\"></span><span>'+"
              + json.dumps(msg) + "+'</span>';}")
        view.page().runJavaScript(js)

    def _ask_finished(self, answer_md: str):
        view = getattr(self, "_ask_view", None)
        if view is None:
            return
        view.setHtml(askscreen_html.generate(
            "answer", model=getattr(self, "_ask_model_id", DEFAULT_MODEL),
            models=getattr(self, "_ask_models", None),
            question=getattr(self, "_ask_question_text", ""), answer_md=answer_md,
        ))
        self.status.showMessage("  Jarvis  ·  answer ready")

    def _ask_failed(self, error: str):
        view = getattr(self, "_ask_view", None)
        if view is None:
            return
        view.setHtml(askscreen_html.generate(
            "error", model=getattr(self, "_ask_model_id", DEFAULT_MODEL),
            models=getattr(self, "_ask_models", None),
            question=getattr(self, "_ask_question_text", ""), error=error,
        ))
        self.status.showMessage("  Jarvis  ·  error")

    # ── House rules helpers ────────────────────────────────────────────────

    def _get_all_house_rules_for_book(self, book_code: str) -> dict:
        """Return {chapter_keyword: [(category, rule_text)]} for this book, or {} if table missing."""
        try:
            c = self.db.cursor()
            c.execute(
                "SELECT chapter_keyword, category, rule_text FROM house_rules "
                "WHERE book_codes LIKE ? ORDER BY id",
                (f"%{book_code}%",),
            )
            result: dict = {}
            for kw, cat, text in c.fetchall():
                result.setdefault(kw, []).append((cat, text))
            return result
        except Exception:
            return {}

    def _get_chapter_house_rules(self, page_url: str, book_code: str) -> list:
        """Return [(category, rule_text)] for the chapter this page belongs to, or []."""
        try:
            c = self.db.cursor()
            c.execute(
                """SELECT subtopic FROM toc_entries
                   WHERE book_code = ? AND page_url <= ?
                     AND (subtopic LIKE '%-- Chapter %' OR subtopic LIKE '%-- Part %'
                          OR subtopic LIKE '%-- Book %' OR subtopic LIKE '%-- Appendix %')
                   ORDER BY page_url DESC LIMIT 1""",
                (book_code, page_url),
            )
            row = c.fetchone()
            if not row:
                return []
            m = re.search(r"(Chapter\s+\d+|Part\s+\d+)", row[0], re.I)
            if not m:
                return []
            chapter_keyword = m.group(1)
            c.execute(
                "SELECT category, rule_text FROM house_rules "
                "WHERE chapter_keyword = ? AND book_codes LIKE ? ORDER BY id",
                (chapter_keyword, f"%{book_code}%"),
            )
            return c.fetchall()
        except Exception:
            return []

    def _build_house_rules_callout(self, rules: list, book_code: str) -> str:
        """Build a slim, collapsed house-rules chip for the top of a rules page."""
        accent = BOOK_ACCENT_COLORS.get(book_code, "#c9a84c")
        by_cat: dict = {}
        for cat, text in rules:
            by_cat.setdefault(cat, []).append(text)

        inner = ""
        for cat, texts in by_cat.items():
            items = "".join(f"<li>{text}</li>" for text in texts)
            inner += f'<div class="hrx-cat" style="color:{accent}">{cat}</div><ul class="hrx-list">{items}</ul>'

        return f"""<style>
      .hrx {{ margin: 2px 0 26px; font-family:'Segoe UI',system-ui,sans-serif; }}
      .hrx > summary {{ list-style:none; cursor:pointer; outline:none; user-select:none;
        display:inline-flex; align-items:center; padding:6px 14px;
        border-radius:7px; background:#23262f; border:1px solid #34384a;
        color:#aeb4c6; font-size:12px; font-weight:600;
        transition:background .12s, border-color .12s; }}
      .hrx > summary:hover {{ background:#2a2e3c; border-color:{accent}; }}
      .hrx > summary::-webkit-details-marker {{ display:none; }}
      .hrx-ico {{ font-size:13px; }}
      .hrx-txt {{ margin:0 10px; }}
      .hrx-body {{ margin-top:10px; padding:12px 16px 14px; background:#1d2028;
        border:1px solid #2a2e3b; border-left:3px solid {accent}; border-radius:8px; }}
      .hrx-cat {{ font-size:10px; font-weight:700; letter-spacing:.09em;
        text-transform:uppercase; margin:14px 0 5px; }}
      .hrx-cat:first-child {{ margin-top:0; }}
      .hrx-list {{ margin:0 0 0 18px; padding:0; color:#c2c6d6; font-size:13.5px; line-height:1.7; }}
      .hrx-list li {{ margin-bottom:3px; }}
    </style>
    <details class="hrx">
      <summary>
        <span class="hrx-ico">&#x2694;&#xFE0F;</span>
        <span class="hrx-txt">House rules affect this chapter</span>
        <span class="hrx-ico">&#x2694;&#xFE0F;</span>
      </summary>
      <div class="hrx-body">{inner}</div>
    </details>"""

    def _load_page(self, page_url: str, add_to_history: bool = True):
        """Public entry point for opening a scraped rules page (tree/results/bookmarks)."""
        self._navigate(page_url, add_to_history)

    def _render_page(self, page_url: str) -> bool:
        c = self.db.cursor()
        c.execute(
            "SELECT content_html, title, book_name, book_code FROM pages WHERE page_url = ?",
            (page_url,),
        )
        row = c.fetchone()
        if not row:
            self.status.showMessage(f"  Not found: {page_url}")
            return False

        html, title, book_name, book_code = row
        rules = self._get_chapter_house_rules(page_url, book_code)
        if rules:
            callout = self._build_house_rules_callout(rules, book_code)
            if "<body" in html:
                idx = html.find(">", html.find("<body")) + 1
                html = html[:idx] + callout + html[idx:]
            else:
                html = callout + html
        self.content.load(html, page_url)
        self.current_page_url = page_url
        self._set_tab_title(f"{book_code}: {title}")
        self.status.showMessage(f"  {book_name}  ·  {title}")
        self.bookmark_btn.setEnabled(True)
        self._update_bookmark_btn()
        self._sync_tree_selection(page_url)
        return True

    def _go_back(self):
        if self._history_pos > 0:
            self._history_pos -= 1
            self._navigate(self._history[self._history_pos], add_to_history=False)

    def _go_forward(self):
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self._navigate(self._history[self._history_pos], add_to_history=False)

    def _update_nav_buttons(self):
        self.back_btn.setEnabled(self._history_pos > 0)
        self.fwd_btn.setEnabled(self._history_pos < len(self._history) - 1)
        self.prev_btn.setEnabled(self._adjacent_page(-1) is not None)
        self.next_btn.setEnabled(self._adjacent_page(1) is not None)

    def _adjacent_page(self, delta: int):
        """The page_url `delta` steps from the current page within its book, or None."""
        url = self.current_page_url
        if not url or "/" not in url:
            return None
        order = self._book_page_order.get(url.split("/")[0])
        if not order or url not in order:
            return None
        i = order.index(url) + delta
        return order[i] if 0 <= i < len(order) else None

    def _go_prev_page(self):
        target = self._adjacent_page(-1)
        if target:
            self._load_page(target)

    def _go_next_page(self):
        target = self._adjacent_page(1)
        if target:
            self._load_page(target)

    # ── Tab management ──────────────────────────────────────────────────────

    def _new_tab(self, show_splash: bool = True):
        """Open a fresh content tab, optionally showing the splash screen."""
        view = ContentView()
        view.page_requested.connect(self._on_content_navigate)
        view.page_requested_newtab.connect(self._on_content_navigate_newtab)
        view.apply_zoom(self._zoom)
        ctx = TabContext(view)
        self._tabs.append(ctx)
        idx = self._content_tabs.addTab(view, "Home")
        self._content_tabs.setCurrentIndex(idx)
        if show_splash:
            self._show_splash()

    def _on_content_navigate_newtab(self, url: str):
        """Ctrl/middle-clicked link: open the target in a new background tab."""
        prev = self._content_tabs.currentIndex()
        self._new_tab(show_splash=False)
        self._navigate(self._link_to_destination(url))
        # Keep focus on the originating tab (background-open behaviour)
        self._content_tabs.setCurrentIndex(prev)

    def _close_tab(self, idx: int):
        """Close the tab at idx; always keeps at least one tab open."""
        if self._content_tabs.count() <= 1:
            return
        ctx = self._tabs.pop(idx)
        self._content_tabs.removeTab(idx)
        ctx.view.deleteLater()
        self._update_nav_buttons()
        self._update_bookmark_btn()

    def _on_tab_changed(self, idx: int):
        """Sync UI state when the user switches tabs."""
        if not (0 <= idx < len(self._tabs)):
            return
        self._update_nav_buttons()
        self._update_bookmark_btn()
        ctx = self._tabs[idx]
        if ctx.current_page_url:
            self._sync_tree_selection(ctx.current_page_url)

    def _set_tab_title(self, title: str):
        """Update the active tab's label, truncating if needed."""
        idx = self._content_tabs.currentIndex()
        label = title if len(title) <= 24 else title[:22] + "…"
        self._content_tabs.setTabText(idx, label)

    # ── Search ─────────────────────────────────────────────────────────────

    def _do_search(self):
        query = self.search_box.text().strip()
        if not query:
            return
        self.status.showMessage(f'  Searching for "{query}"...')
        self.tabs.setCurrentIndex(1)
        self.results_list.clear()

        loading = QListWidgetItem("  Searching...")
        loading.setForeground(QColor("#505870"))
        self.results_list.addItem(loading)

        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.quit()

        self._search_worker = SearchWorker(str(DB_PATH), query)
        self._search_worker.results_ready.connect(self._show_results)
        self._search_worker.start()

    def _show_results(self, rows):
        self.results_list.clear()
        if not rows:
            empty = QListWidgetItem("  No results found.")
            empty.setForeground(QColor("#505870"))
            self.results_list.addItem(empty)
            self.status.showMessage("  No results found.")
            return

        for page_url, title, book_name, book_code, _snip in rows:
            label = re.sub(r"\s*\([^)]+\)\s*$", "", title or page_url).strip()
            text  = f"  {label}\n  {book_name or ''}"
            snip  = re.sub(r"\s+", " ", (_snip or "").replace("**", "")).strip()
            if snip:
                if len(snip) > 120:
                    snip = snip[:118].rstrip() + "…"
                text += f"\n  {snip}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, page_url)
            item.setForeground(QColor("#c0c4d4"))
            item.setBackground(QColor(BOOK_ITEM_COLORS.get(book_code or "", "#1a1d24")))
            self.results_list.addItem(item)

        self.tabs.setTabText(1, f"Results ({len(rows)})")
        self.status.showMessage(f"  Found {len(rows)} results")

    def _on_result_click(self, item: QListWidgetItem):
        url = item.data(Qt.UserRole)
        if url:
            self._load_page(url)

    # ── Bookmarks ──────────────────────────────────────────────────────────

    def _toggle_bookmark(self):
        if not self.current_page_url:
            return
        c = self.user_db.cursor()
        c.execute("SELECT id FROM bookmarks WHERE page_url = ?", (self.current_page_url,))
        if c.fetchone():
            c.execute("DELETE FROM bookmarks WHERE page_url = ?", (self.current_page_url,))
        else:
            c.execute("INSERT OR IGNORE INTO bookmarks (page_url) VALUES (?)",
                      (self.current_page_url,))
        self.user_db.commit()
        self._update_bookmark_btn()
        self._load_bookmarks()

    def _update_bookmark_btn(self):
        if not self.current_page_url:
            return
        c = self.user_db.cursor()
        c.execute("SELECT id FROM bookmarks WHERE page_url = ?", (self.current_page_url,))
        self.bookmark_btn.setText(
            "★   Remove Bookmark" if c.fetchone() else "☆   Bookmark This Page"
        )

    def _load_bookmarks(self):
        self.bookmarks_list.clear()
        c = self.user_db.cursor()
        c.execute("SELECT page_url FROM bookmarks ORDER BY created_at DESC")
        bookmarked = [r[0] for r in c.fetchall()]
        pc = self.db.cursor()
        for page_url in bookmarked:
            pc.execute(
                "SELECT title, book_name, book_code FROM pages WHERE page_url = ?",
                (page_url,),
            )
            prow = pc.fetchone()
            title, book_name, book_code = prow if prow else (page_url, "", "")
            label = re.sub(r"\s*\([^)]+\)\s*$", "", title or page_url).strip()
            item  = QListWidgetItem(f"  {label}\n  {book_name or ''}")
            item.setData(Qt.UserRole, page_url)
            item.setForeground(QColor("#c0c4d4"))
            item.setBackground(QColor(BOOK_ITEM_COLORS.get(book_code or "", "#1a1d24")))
            self.bookmarks_list.addItem(item)

        count = self.bookmarks_list.count()
        self.tabs.setTabText(2, f"Bookmarks ({count})" if count else "Bookmarks")

    def _on_bookmark_click(self, item: QListWidgetItem):
        url = item.data(Qt.UserRole)
        if url:
            self._load_page(url)

    def _bookmark_ctx(self, pos):
        from PyQt5.QtWidgets import QMenu
        item = self.bookmarks_list.itemAt(pos)
        if not item:
            return
        menu   = QMenu(self)
        remove = menu.addAction("Remove Bookmark")
        if menu.exec_(self.bookmarks_list.mapToGlobal(pos)) == remove:
            url = item.data(Qt.UserRole)
            c   = self.user_db.cursor()
            c.execute("DELETE FROM bookmarks WHERE page_url = ?", (url,))
            self.user_db.commit()
            self._load_bookmarks()
            if url == self.current_page_url:
                self._update_bookmark_btn()

    # ── Session persistence ─────────────────────────────────────────────────

    def _current_entry(self, ctx: "TabContext"):
        """The navigation entry currently shown in a tab, or None."""
        if ctx.history and 0 <= ctx.history_pos < len(ctx.history):
            return ctx.history[ctx.history_pos]
        return None

    def _restore_session(self):
        geo = self._settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        entries = self._settings.value("openTabs")
        if isinstance(entries, str):
            entries = [entries]
        if not entries:
            self._show_splash()
        else:
            for i, entry in enumerate(entries):
                if i > 0:
                    self._new_tab(show_splash=False)
                else:
                    self._content_tabs.setCurrentIndex(0)
                self._navigate(entry)   # a saved history entry is a destination
            try:
                active = int(self._settings.value("activeTab", 0))
            except (TypeError, ValueError):
                active = 0
            if 0 <= active < self._content_tabs.count():
                self._content_tabs.setCurrentIndex(active)
        self._apply_zoom_all()

    def _save_session(self):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("zoom", self._zoom)
        entries = [e for ctx in self._tabs if (e := self._current_entry(ctx))]
        self._settings.setValue("openTabs", entries)
        self._settings.setValue("activeTab", self._content_tabs.currentIndex())
        self._settings.sync()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._save_session()
        self.db.close()
        self.user_db.close()
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not DB_PATH.exists():
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, "Database Not Found",
            f"No database found at:\n{DB_PATH}\n\nPlease run scraper.py first.",
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("D&D 2e Rules")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    # Dark base palette so OS chrome (title bar etc.) matches
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor("#13151b"))
    pal.setColor(QPalette.WindowText,      QColor("#c9ccd6"))
    pal.setColor(QPalette.Base,            QColor("#1a1d24"))
    pal.setColor(QPalette.AlternateBase,   QColor("#1e2130"))
    pal.setColor(QPalette.Text,            QColor("#c9ccd6"))
    pal.setColor(QPalette.Button,          QColor("#1e2130"))
    pal.setColor(QPalette.ButtonText,      QColor("#c9ccd6"))
    pal.setColor(QPalette.Highlight,       QColor("#5c4a1c"))
    pal.setColor(QPalette.HighlightedText, QColor("#f2e8cc"))
    pal.setColor(QPalette.ToolTipBase,     QColor("#1e2130"))
    pal.setColor(QPalette.ToolTipText,     QColor("#c9ccd6"))
    app.setPalette(pal)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

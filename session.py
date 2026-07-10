"""session.py — pure helpers for restoring a saved window session.

The Qt orchestration (QSettings, window geometry, the tab widget, the calculator)
stays in MainWindow; what lives here is the fiddly coercion of stored values back
into usable form. QSettings is loosely typed -- a saved list of one item comes back
as a bare string, a missing key as None, a corrupt index as who-knows -- and that
normalization is exactly the part worth testing without a running window.

Follows character_library.py and ask_controller.py in pulling logic out of the Qt
shell. Pure and Qt-free.
"""


def normalize_open_tabs(value) -> list:
    """The stored ``openTabs`` value as a clean list of history-entry strings.

    QSettings returns a list as saved, a *bare string* when only one tab was open,
    and None when the key was never written. An empty result means "no saved tabs",
    which the caller reads as "show the splash screen".
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def active_tab_index(value, tab_count: int, default: int = 0):
    """Which tab to re-select, or ``None`` to leave the current selection alone.

    A non-numeric stored value falls back to ``default``; the result is applied only
    if it indexes a real tab, so a stale or corrupt index can never select a tab that
    no longer exists.
    """
    try:
        idx = int(value)
    except (TypeError, ValueError):
        idx = default
    return idx if 0 <= idx < tab_count else None

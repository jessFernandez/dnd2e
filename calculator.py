"""calculator.py — Floating "House-Rule Combat Converter".

Converts standard AD&D 2e THAC0 / descending AC into the campaign's house-rule
system (attack bonus + ascending AC), per the Combat house rules:

  * THAC0 is removed; attack bonus = 20 − THAC0        (house rule)
  * roll d20 + bonus, meet/beat the target's AC;
    ascending AC = 20 − descending AC                  (house rule)
  * crit on a natural 18+ that beats AC by 5+

It opens as a floating, always-on-top tool window that stays put while you
navigate pages, and can be resized or closed.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QSpinBox,
)
from PyQt5.QtCore import Qt


# ── Pure conversion helpers (unit-tested in tests/test_calculator.py) ─────────

def thac0_to_bonus(thac0: int) -> int:
    return 20 - thac0


def bonus_to_thac0(bonus: int) -> int:
    return 20 - bonus


def desc_to_asc(desc_ac: int) -> int:
    return 20 - desc_ac


def asc_to_desc(asc_ac: int) -> int:
    return 20 - asc_ac


def to_hit_need(attack_bonus: int, target_asc_ac: int) -> int:
    """The raw d20 result needed to hit (before nat-1/nat-20 clamping)."""
    return target_asc_ac - attack_bonus


def hit_chance(need: int) -> int:
    """Percent chance to hit on a d20 (a natural 1 always misses, 20 always hits)."""
    eff = max(2, min(20, need))
    return (21 - eff) * 5


_STYLE = """
QWidget { background: #1a1c26; color: #c8cad8; font-family: "Segoe UI", system-ui, sans-serif; font-size: 12px; }
QGroupBox { border: 1px solid #2a2e45; border-radius: 8px; margin-top: 11px;
            padding: 12px 10px 8px; font-weight: 700; color: #c9a84c; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLabel { color: #c8cad8; }
QLabel#hint { color: #5a6080; font-size: 10.5px; font-style: italic; }
QLabel#result { color: #e6e9f6; font-weight: 600; font-size: 13px; padding: 7px 9px;
                background: #23263a; border: 1px solid #383c52; border-radius: 6px; }
QLabel#ref { color: #6b7290; font-size: 10.5px; }
QSpinBox { background: #23263a; border: 1px solid #383c52; border-radius: 6px;
           padding: 3px 6px; color: #e6e9f6; }
QSpinBox:focus { border-color: #c9a84c; }
"""


class HouseRuleCalculator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("House-Rule Combat Converter")
        self.setMinimumWidth(288)
        self.resize(330, 470)
        self.setStyleSheet(_STYLE)
        self._guard = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(11)

        # THAC0 ⇄ attack bonus
        g1 = QGroupBox("THAC0  →  Attack Bonus")
        l1 = QGridLayout(g1)
        self.thac0 = self._spin(-10, 25, 20)
        self.bonus = self._spin(-5, 30, 0)
        l1.addWidget(QLabel("THAC0 (book)"), 0, 0);   l1.addWidget(self.thac0, 0, 1)
        l1.addWidget(QLabel("Attack bonus (house)"), 1, 0); l1.addWidget(self.bonus, 1, 1)
        l1.addWidget(self._hint("bonus = 20 − THAC0"), 2, 0, 1, 2)
        root.addWidget(g1)

        # descending ⇄ ascending AC
        g2 = QGroupBox("Armor Class:  Descending ⇄ Ascending")
        l2 = QGridLayout(g2)
        self.acd = self._spin(-15, 12, 10)
        self.aca = self._spin(8, 35, 10)
        l2.addWidget(QLabel("Descending (book)"), 0, 0);  l2.addWidget(self.acd, 0, 1)
        l2.addWidget(QLabel("Ascending (house)"), 1, 0);  l2.addWidget(self.aca, 1, 1)
        l2.addWidget(self._hint("ascending = 20 − descending"), 2, 0, 1, 2)
        root.addWidget(g2)

        # to-hit resolver
        g3 = QGroupBox("To-Hit Check")
        l3 = QGridLayout(g3)
        self.hb = self._spin(-5, 30, 0)
        self.ha = self._spin(8, 35, 10)
        l3.addWidget(QLabel("Your attack bonus"), 0, 0);    l3.addWidget(self.hb, 0, 1)
        l3.addWidget(QLabel("Target AC (ascending)"), 1, 0); l3.addWidget(self.ha, 1, 1)
        self.result = QLabel()
        self.result.setObjectName("result")
        self.result.setWordWrap(True)
        l3.addWidget(self.result, 2, 0, 1, 2)
        root.addWidget(g3)

        ref = QLabel("House rules: THAC0 removed (bonus = 20 − THAC0). Roll d20 + bonus, "
                     "meet or beat the target's ascending AC. Crit on a natural 18+ that "
                     "beats AC by 5 or more.")
        ref.setObjectName("ref")
        ref.setWordWrap(True)
        root.addWidget(ref)
        root.addStretch()

        self.thac0.valueChanged.connect(lambda v: self._sync(self.bonus, thac0_to_bonus(v)))
        self.bonus.valueChanged.connect(lambda v: self._sync(self.thac0, bonus_to_thac0(v)))
        self.acd.valueChanged.connect(lambda v: self._sync(self.aca, desc_to_asc(v)))
        self.aca.valueChanged.connect(lambda v: self._sync(self.acd, asc_to_desc(v)))
        self.hb.valueChanged.connect(self._update_hit)
        self.ha.valueChanged.connect(self._update_hit)
        self._update_hit()

    def _spin(self, lo, hi, val):
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setFixedWidth(78)
        return s

    def _hint(self, text):
        lbl = QLabel(text)
        lbl.setObjectName("hint")
        return lbl

    def _sync(self, other: QSpinBox, value: int):
        if self._guard:
            return
        self._guard = True
        other.setValue(int(value))
        self._guard = False

    def _update_hit(self):
        need = to_hit_need(self.hb.value(), self.ha.value())
        chance = hit_chance(need)
        if need <= 1:
            self.result.setText(f"Hits on 2+ on d20  ·  {chance}% (only a natural 1 misses)")
        elif need > 20:
            self.result.setText("Can't hit by the numbers  ·  5% (only a natural 20)")
        else:
            self.result.setText(f"Need {need}+ on d20  ·  {chance}% to hit")

"""Color panel: primary/secondary swatches, full color wheel, hex entry,
recent colors.

Left mouse button paints with the primary color, right button with the
secondary. Clicking a big swatch opens QColorDialog (full wheel + alpha).
The hex field accepts #RGB, #RRGGBB and #RRGGBBAA and stays in sync.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

MAX_RECENT = 24  # two full rows at PALETTE_COLUMNS

# Generated ramp palette: one column per hue, light-to-dark down each column,
# plus a top row of grays. 12 hues x 7 shades + 12 grays = 96 colors.
PALETTE_HUES = 12
PALETTE_SHADE_LIGHTNESS = (0.90, 0.78, 0.65, 0.52, 0.40, 0.28, 0.16)
PALETTE_SATURATION = 0.78
PALETTE_COLUMNS = PALETTE_HUES


def build_ramp_palette() -> list[list[QColor]]:
    """Return palette rows: [grays] + one row per shade across all hues."""
    grays = [
        QColor.fromHslF(0.0, 0.0, 1.0 - i / (PALETTE_HUES - 1))
        for i in range(PALETTE_HUES)
    ]
    rows = [grays]
    for lightness in PALETTE_SHADE_LIGHTNESS:
        rows.append([
            QColor.fromHslF(h / PALETTE_HUES, PALETTE_SATURATION, lightness)
            for h in range(PALETTE_HUES)
        ])
    return rows


class Swatch(QPushButton):
    """A small clickable color square."""

    def __init__(self, color: QColor, size: int = 22) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.set_color(color)

    def set_color(self, color: QColor) -> None:
        self.color = QColor(color)
        self.setStyleSheet(
            f"background-color: rgba({color.red()},{color.green()},"
            f"{color.blue()},{color.alpha()}); border: 1px solid #555;")
        self.setToolTip(color.name(QColor.NameFormat.HexArgb))


class ColorPanel(QWidget):
    primary_changed = Signal(QColor)
    secondary_changed = Signal(QColor)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.primary = QColor(0, 0, 0, 255)
        self.secondary = QColor(255, 255, 255, 255)
        self.recent: list[QColor] = []

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # primary / secondary big swatches
        row = QHBoxLayout()
        self.primary_btn = QPushButton()
        self.primary_btn.setFixedSize(48, 48)
        self.primary_btn.setToolTip("Primary color (left mouse) -- click to open color wheel")
        self.primary_btn.clicked.connect(lambda: self._pick(primary=True))
        self.secondary_btn = QPushButton()
        self.secondary_btn.setFixedSize(48, 48)
        self.secondary_btn.setToolTip("Secondary color (right mouse) -- click to open color wheel")
        self.secondary_btn.clicked.connect(lambda: self._pick(primary=False))
        swap = QPushButton("\u21c4")
        swap.setFixedSize(28, 28)
        swap.setToolTip("Swap primary/secondary (X)")
        swap.clicked.connect(self.swap_colors)
        row.addWidget(self.primary_btn)
        row.addWidget(self.secondary_btn)
        row.addWidget(swap)
        row.addStretch()
        layout.addLayout(row)

        # hex entry
        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel("Hex:"))
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB or #RRGGBBAA")
        self.hex_edit.returnPressed.connect(self._hex_entered)
        self.hex_edit.editingFinished.connect(self._hex_entered)
        hex_row.addWidget(self.hex_edit)
        layout.addLayout(hex_row)

        # generated ramp palette (grays row, then one ramp column per hue)
        self.palette_rows = build_ramp_palette()
        layout.addWidget(QLabel("Palette (left-click primary, right-click secondary)"))
        pal_grid = QGridLayout()
        pal_grid.setSpacing(1)
        for r, row in enumerate(self.palette_rows):
            for c, color in enumerate(row):
                sw = Swatch(color, size=20)
                sw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                sw.clicked.connect(
                    lambda checked=False, s=sw: self.set_primary(s.color))
                sw.customContextMenuRequested.connect(
                    lambda pos, s=sw: self.set_secondary(s.color))
                pal_grid.addWidget(sw, r, c)
        layout.addLayout(pal_grid)

        # recent colors
        layout.addWidget(QLabel("Recent"))
        self.recent_grid = QGridLayout()
        self.recent_grid.setSpacing(2)
        layout.addLayout(self.recent_grid)
        layout.addStretch()

        self._refresh()

    # ------------------------------------------------------------- API
    def set_primary(self, color: QColor) -> None:
        self.primary = QColor(color)
        self._push_recent(color)
        self._refresh()
        self.primary_changed.emit(self.primary)

    def set_secondary(self, color: QColor) -> None:
        self.secondary = QColor(color)
        self._push_recent(color)
        self._refresh()
        self.secondary_changed.emit(self.secondary)

    def swap_colors(self) -> None:
        self.primary, self.secondary = self.secondary, self.primary
        self._refresh()
        self.primary_changed.emit(self.primary)
        self.secondary_changed.emit(self.secondary)

    # ------------------------------------------------------------- internals
    def _pick(self, primary: bool) -> None:
        initial = self.primary if primary else self.secondary
        color = QColorDialog.getColor(
            initial, self, "Choose color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if color.isValid():
            if primary:
                self.set_primary(color)
            else:
                self.set_secondary(color)

    def _hex_entered(self) -> None:
        text = self.hex_edit.text().strip()
        m = HEX_RE.match(text)
        if not m:
            self._refresh()  # restore valid value
            return
        val = m.group(1)
        if len(val) == 3:
            val = "".join(c * 2 for c in val)
        if len(val) == 6:
            color = QColor(f"#{val}")
        else:  # RRGGBBAA -> QColor wants #AARRGGBB
            rgb, alpha = val[:6], val[6:]
            color = QColor(f"#{alpha}{rgb}")
        if color.isValid():
            self.set_primary(color)

    def _push_recent(self, color: QColor) -> None:
        c = QColor(color)
        self.recent = [r for r in self.recent if r.rgba() != c.rgba()]
        self.recent.insert(0, c)
        del self.recent[MAX_RECENT:]

    def _refresh(self) -> None:
        def style(c: QColor) -> str:
            return (f"background-color: rgba({c.red()},{c.green()},"
                    f"{c.blue()},{c.alpha()}); border: 2px solid #333;")
        self.primary_btn.setStyleSheet(style(self.primary))
        self.secondary_btn.setStyleSheet(style(self.secondary))
        if self.primary.alpha() == 255:
            self.hex_edit.setText(self.primary.name(QColor.NameFormat.HexRgb))
        else:
            # QColor gives #AARRGGBB; convert to the conventional #RRGGBBAA
            argb = self.primary.name(QColor.NameFormat.HexArgb)
            self.hex_edit.setText(f"#{argb[3:]}{argb[1:3]}")

        # rebuild recent grid
        while self.recent_grid.count():
            item = self.recent_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, c in enumerate(self.recent):
            sw = Swatch(c, size=20)
            sw.clicked.connect(lambda checked=False, s=sw: self.set_primary(s.color))
            self.recent_grid.addWidget(sw, i // PALETTE_COLUMNS,
                                       i % PALETTE_COLUMNS,
                                       Qt.AlignmentFlag.AlignLeft)
        # keep partially filled rows packed to the left
        self.recent_grid.setColumnStretch(PALETTE_COLUMNS, 1)

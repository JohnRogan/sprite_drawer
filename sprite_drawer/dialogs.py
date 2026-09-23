"""Dialogs: New Sprite (arbitrary width x height)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)

from .document import MAX_DIMENSION


class NewSpriteDialog(QDialog):
    def __init__(self, parent: QWidget | None = None,
                 default_w: int = 32, default_h: int = 32) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Sprite")
        layout = QFormLayout(self)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, MAX_DIMENSION)
        self.width_spin.setValue(default_w)
        self.width_spin.setSuffix(" px")
        layout.addRow("Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, MAX_DIMENSION)
        self.height_spin.setValue(default_h)
        self.height_spin.setSuffix(" px")
        layout.addRow("Height:", self.height_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def sprite_size(self) -> tuple[int, int]:
        return self.width_spin.value(), self.height_spin.value()

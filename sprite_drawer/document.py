"""SpriteDocument: the pixel data model with undo/redo.

The sprite is stored as a QImage in Format_ARGB32 (straight alpha) at its
true pixel resolution. Undo/redo is snapshot-based: before every committed
edit the full image is copied onto the undo stack (cheap at sprite sizes).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QImage

MAX_UNDO = 64
MAX_DIMENSION = 4096


class SpriteDocument(QObject):
    """Holds the sprite image, file path, dirty flag, and undo history."""

    changed = Signal()            # pixels changed -> repaint
    modified_changed = Signal(bool)
    document_reset = Signal()     # new/opened document (size may differ)

    def __init__(self, width: int = 32, height: int = 32) -> None:
        super().__init__()
        self.image = QImage(width, height, QImage.Format.Format_ARGB32)
        self.image.fill(QColor(0, 0, 0, 0))
        self.file_path: str | None = None
        self._modified = False
        self._undo_stack: list[QImage] = []
        self._redo_stack: list[QImage] = []

    # ------------------------------------------------------------- properties
    @property
    def width(self) -> int:
        return self.image.width()

    @property
    def height(self) -> int:
        return self.image.height()

    @property
    def modified(self) -> bool:
        return self._modified

    def set_modified(self, value: bool) -> None:
        if self._modified != value:
            self._modified = value
            self.modified_changed.emit(value)

    # ------------------------------------------------------------- lifecycle
    def new(self, width: int, height: int) -> None:
        width = max(1, min(MAX_DIMENSION, width))
        height = max(1, min(MAX_DIMENSION, height))
        self.image = QImage(width, height, QImage.Format.Format_ARGB32)
        self.image.fill(QColor(0, 0, 0, 0))
        self.file_path = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.set_modified(False)
        self.document_reset.emit()
        self.changed.emit()

    def load(self, path: str) -> bool:
        img = QImage(path)
        if img.isNull():
            return False
        self.image = img.convertToFormat(QImage.Format.Format_ARGB32)
        self.file_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.set_modified(False)
        self.document_reset.emit()
        self.changed.emit()
        return True

    def save(self, path: str) -> bool:
        if not self.image.save(path, "PNG"):
            return False
        self.file_path = path
        self.set_modified(False)
        return True

    # ------------------------------------------------------------- undo/redo
    def push_undo(self) -> None:
        """Call before mutating the image as part of a committed edit."""
        self._undo_stack.append(self.image.copy())
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self.image.copy())
        self.image = self._undo_stack.pop()
        self.set_modified(True)
        self.changed.emit()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self.image.copy())
        self.image = self._redo_stack.pop()
        self.set_modified(True)
        self.changed.emit()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    # ------------------------------------------------------------- editing
    def notify_changed(self) -> None:
        """Tools call this after mutating the image."""
        self.set_modified(True)
        self.changed.emit()

    def clear(self) -> None:
        self.push_undo()
        self.image.fill(QColor(0, 0, 0, 0))
        self.notify_changed()

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def color_at(self, x: int, y: int) -> QColor:
        if not self.in_bounds(x, y):
            return QColor(0, 0, 0, 0)
        return self.image.pixelColor(x, y)

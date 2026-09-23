"""PixelCanvas: the zoomable drawing surface.

Rendering order (paintEvent):
  1. checkerboard  (transparency background)
  2. underlay photo (at its own opacity -- the trace layer)
  3. sprite pixels  (optionally semi-translucent while tracing)
  4. live tool preview overlay
  5. grid lines     (when zoom is large enough)

The widget's size is sprite_size * zoom; it lives inside a QScrollArea.
Pan with middle-drag or space+drag; zoom with Ctrl+wheel or +/- shortcuts.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QScrollArea, QWidget

from .document import SpriteDocument
from .underlay import Underlay

MIN_ZOOM = 1
MAX_ZOOM = 64
GRID_MIN_ZOOM = 5  # only draw grid lines at this zoom or above

# Background modes cycled by Ctrl/Cmd+G
BG_GRID = 0      # grid lines + checkerboard
BG_CHECKER = 1   # checkerboard only
BG_PLAIN = 2     # flat neutral background
BG_MODE_NAMES = {BG_GRID: "grid + checker", BG_CHECKER: "checker only",
                 BG_PLAIN: "plain background"}
PLAIN_BG = QColor(96, 96, 96)  # neutral flat backdrop (plain mode + preview)


def _make_checker_pixmap(cell: int) -> QPixmap:
    """2x2 checker tile where each square is `cell` screen px = 1 sprite px."""
    pm = QPixmap(cell * 2, cell * 2)
    pm.fill(QColor(200, 200, 200))
    p = QPainter(pm)
    p.fillRect(0, 0, cell, cell, QColor(150, 150, 150))
    p.fillRect(cell, cell, cell, cell, QColor(150, 150, 150))
    p.end()
    return pm


class PixelCanvas(QWidget):
    color_picked = Signal(QColor)          # eyedropper result
    cursor_pixel_changed = Signal(int, int)  # hover position in sprite coords
    zoom_changed = Signal(int)

    def __init__(self, document: SpriteDocument, underlay: Underlay,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc = document
        self.underlay = underlay
        self.zoom = 8
        self.background_mode = BG_GRID
        self.preview_mode = False  # hides grid/checker/underlay, flat backdrop
        self.sprite_hidden = False  # display-only: hide the drawn pixels
        self.sprite_opacity = 1.0  # display-only, for tracing
        self.current_tool = None   # set by MainWindow (tools.Tool)
        self.primary_color = QColor(0, 0, 0, 255)
        self.secondary_color = QColor(255, 255, 255, 255)

        # transparent overlay the shape tools draw their live preview into
        self.preview = QImage(self.doc.width, self.doc.height,
                              QImage.Format.Format_ARGB32)
        self.preview.fill(QColor(0, 0, 0, 0))

        self._checker = _make_checker_pixmap(self.zoom)
        self._space_down = False
        self._panning = False
        self._pan_start = QPoint()

        self.doc.changed.connect(self.update)
        self.doc.document_reset.connect(self._on_document_reset)
        self.underlay.changed.connect(self.update)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._apply_size()

    # ------------------------------------------------------------- geometry
    def _apply_size(self) -> None:
        self.setFixedSize(self.doc.width * self.zoom,
                          self.doc.height * self.zoom)
        self.update()

    def _on_document_reset(self) -> None:
        self.preview = QImage(self.doc.width, self.doc.height,
                              QImage.Format.Format_ARGB32)
        self.preview.fill(QColor(0, 0, 0, 0))
        self.fit_zoom()

    def fit_zoom(self) -> None:
        """Pick a zoom that shows the whole sprite at a comfortable size."""
        target = 640
        z = max(MIN_ZOOM,
                min(MAX_ZOOM, target // max(self.doc.width, self.doc.height)))
        self.set_zoom(z if z >= 1 else 1)

    def set_zoom(self, zoom: int) -> None:
        zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if zoom != self.zoom:
            self.zoom = zoom
            # checker squares must stay locked to sprite pixels at every zoom
            self._checker = _make_checker_pixmap(zoom)
            self.zoom_changed.emit(zoom)
        self._apply_size()

    def zoom_in(self) -> None:
        self.set_zoom(self.zoom + max(1, self.zoom // 4))

    def zoom_out(self) -> None:
        self.set_zoom(self.zoom - max(1, self.zoom // 4))

    def widget_to_pixel(self, pos) -> tuple[int, int]:
        return int(pos.x()) // self.zoom, int(pos.y()) // self.zoom

    def clear_preview(self) -> None:
        self.preview.fill(QColor(0, 0, 0, 0))

    def set_sprite_opacity(self, o: float) -> None:
        self.sprite_opacity = max(0.0, min(1.0, o))
        self.update()

    # ------------------------------------------------------------- view modes
    def cycle_background(self) -> str:
        """Advance grid+checker -> checker only -> plain; return mode name."""
        self.background_mode = (self.background_mode + 1) % len(BG_MODE_NAMES)
        self.update()
        return BG_MODE_NAMES[self.background_mode]

    def set_preview_mode(self, on: bool) -> None:
        self.preview_mode = on
        self.update()

    def toggle_preview_mode(self) -> bool:
        self.set_preview_mode(not self.preview_mode)
        return self.preview_mode

    def set_sprite_hidden(self, hidden: bool) -> None:
        self.sprite_hidden = hidden
        self.update()

    # ------------------------------------------------------------- painting
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        # Preview: just the sprite as a game would render it -- flat backdrop,
        # no grid, no checker, no photo, full opacity. Tools still work.
        if self.preview_mode:
            painter.fillRect(self.rect(), PLAIN_BG)
            painter.scale(self.zoom, self.zoom)
            if not self.sprite_hidden:
                painter.drawImage(0, 0, self.doc.image)
            painter.drawImage(0, 0, self.preview)
            painter.end()
            return

        # 1. backdrop: checkerboard (one square per sprite pixel, tiled from
        #    the widget origin so squares coincide with pixel cells) or flat
        if self.background_mode == BG_PLAIN:
            painter.fillRect(self.rect(), PLAIN_BG)
        else:
            painter.drawTiledPixmap(self.rect(), self._checker)

        # 2. underlay photo (trace layer)
        if self.underlay.loaded and self.underlay.visible:
            painter.save()
            painter.setOpacity(self.underlay.opacity)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            img = self.underlay.image
            target = QRectF(
                self.underlay.offset_x * self.zoom,
                self.underlay.offset_y * self.zoom,
                img.width() * self.underlay.scale * self.zoom,
                img.height() * self.underlay.scale * self.zoom,
            )
            painter.drawImage(target, img)
            painter.restore()

        # 3. sprite pixels (nearest-neighbour scale)
        painter.save()
        painter.setOpacity(self.sprite_opacity)
        painter.scale(self.zoom, self.zoom)
        if not self.sprite_hidden:
            painter.drawImage(0, 0, self.doc.image)
        # 4. live preview overlay (kept visible so shape drags still show)
        painter.drawImage(0, 0, self.preview)
        painter.restore()

        # 5. grid lines
        if self.background_mode == BG_GRID and self.zoom >= GRID_MIN_ZOOM:
            painter.setPen(QColor(0, 0, 0, 110))
            w, h = self.width(), self.height()
            for x in range(0, self.doc.width + 1):
                painter.drawLine(x * self.zoom, 0, x * self.zoom, h)
            for y in range(0, self.doc.height + 1):
                painter.drawLine(0, y * self.zoom, w, y * self.zoom)

        painter.end()

    # ------------------------------------------------------------- input
    def _scroll_area(self) -> QScrollArea | None:
        w = self.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        return w

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (
                self._space_down and event.button() == Qt.MouseButton.LeftButton):
            self._panning = True
            self._pan_start = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self.current_tool is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            color = self.primary_color
        elif event.button() == Qt.MouseButton.RightButton:
            color = self.secondary_color
        else:
            return
        x, y = self.widget_to_pixel(event.position())
        self.current_tool.press(self, x, y, color)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            area = self._scroll_area()
            if area is not None:
                delta = event.globalPosition().toPoint() - self._pan_start
                self._pan_start = event.globalPosition().toPoint()
                h = area.horizontalScrollBar()
                v = area.verticalScrollBar()
                h.setValue(h.value() - delta.x())
                v.setValue(v.value() - delta.y())
            return
        x, y = self.widget_to_pixel(event.position())
        self.cursor_pixel_changed.emit(x, y)
        if self.current_tool is not None and self.current_tool.active:
            self.current_tool.move(self, x, y)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning and event.button() in (
                Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self.current_tool is not None and self.current_tool.active:
            x, y = self.widget_to_pixel(event.position())
            self.current_tool.release(self, x, y)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            old_zoom = self.zoom
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            # keep the pixel under the cursor roughly anchored
            if self.zoom != old_zoom:
                area = self._scroll_area()
                if area is not None:
                    pos = event.position()
                    px, py = pos.x() / old_zoom, pos.y() / old_zoom
                    h = area.horizontalScrollBar()
                    v = area.verticalScrollBar()
                    h.setValue(int(px * self.zoom - (pos.x() - h.value())))
                    v.setValue(int(py * self.zoom - (pos.y() - v.value())))
            event.accept()
        else:
            event.ignore()  # let the scroll area scroll

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            if not self._panning:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().keyReleaseEvent(event)

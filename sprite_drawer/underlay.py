"""Reference photo underlay (trace tool).

The underlay is a real photo of arbitrary pixel dimensions rendered *beneath*
the sprite pixels at an adjustable opacity, scale and offset. It is display
only and never baked into the saved PNG. Its settings are persisted in the
.sprite.json sidecar so a work-in-progress trace survives reopening.

Coordinate system: scale/offset are expressed in *sprite pixel space*.
A scale of 1.0 means one photo pixel covers one sprite pixel; offset is in
sprite pixels from the canvas top-left. The canvas multiplies by zoom when
rendering.
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .paths import src_img_dir


# Formats offered in the file dialog. Anything QImage reads works natively;
# HEIC/HEIF goes through Pillow + pillow-heif; PDF renders via QtPdf.
IMAGE_FILE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.heic *.heif *.pdf "
    "*.bmp *.gif *.webp *.tiff *.tif);;All files (*)")

PDF_MAX_RENDER_PX = 2048  # longest side of the rendered first page
SAMPLE_GRID = 32          # max taps per axis when averaging a photo region


def load_reference_image(path: str) -> QImage:
    """Load a reference image of any supported type as ARGB32.

    Order: PDF -> QtPdf render of page 1; everything else -> QImage; if Qt
    cannot decode it (e.g. HEIC), fall back to Pillow (with pillow-heif
    registered) and apply EXIF orientation. Returns a null QImage on failure.
    """
    if os.path.splitext(path)[1].lower() == ".pdf":
        return _load_pdf(path)
    img = QImage(path)
    if not img.isNull():
        return img.convertToFormat(QImage.Format.Format_ARGB32)
    return _load_with_pillow(path)


def _load_pdf(path: str) -> QImage:
    from PySide6.QtPdf import QPdfDocument

    doc = QPdfDocument()
    doc.load(path)
    if doc.pageCount() < 1:
        return QImage()
    size = doc.pagePointSize(0)  # page size in points (1/72 inch)
    if size.width() <= 0 or size.height() <= 0:
        return QImage()
    scale = PDF_MAX_RENDER_PX / max(size.width(), size.height())
    target = QSize(max(1, round(size.width() * scale)),
                   max(1, round(size.height() * scale)))
    return doc.render(0, target).convertToFormat(QImage.Format.Format_ARGB32)


def _load_with_pillow(path: str) -> QImage:
    try:
        from PIL import Image, ImageOps
        import pillow_heif
    except ImportError:
        return QImage()
    pillow_heif.register_heif_opener()
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)  # respect camera orientation
            im = im.convert("RGBA")
            qimg = QImage(im.tobytes(), im.width, im.height, im.width * 4,
                          QImage.Format.Format_RGBA8888)
            # copy() detaches from the Python buffer before it is freed
            return qimg.copy().convertToFormat(QImage.Format.Format_ARGB32)
    except Exception:
        return QImage()


class Underlay(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.image: QImage | None = None
        self.path: str | None = None
        self.visible: bool = True
        self.opacity: float = 0.5
        self.scale: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0

    @property
    def loaded(self) -> bool:
        return self.image is not None and not self.image.isNull()

    def load(self, path: str) -> bool:
        img = load_reference_image(path)
        if img.isNull():
            return False
        self.image = img
        self.path = path
        self.changed.emit()
        return True

    def clear(self) -> None:
        self.image = None
        self.path = None
        self.changed.emit()

    def sample_pixel(self, px: int, py: int) -> QColor | None:
        """Average photo color under sprite pixel (px, py), or None if the
        pixel does not overlap the photo.

        A sprite pixel usually covers many photo pixels (scale < 1), so the
        region is averaged rather than point-sampled; very large regions are
        subsampled on a grid of at most SAMPLE_GRID x SAMPLE_GRID taps.
        """
        if not self.loaded or self.scale <= 0:
            return None
        img = self.image
        x0 = (px - self.offset_x) / self.scale
        x1 = (px + 1 - self.offset_x) / self.scale
        y0 = (py - self.offset_y) / self.scale
        y1 = (py + 1 - self.offset_y) / self.scale
        ix0, ix1 = max(0, math.floor(x0)), min(img.width(), math.ceil(x1))
        iy0, iy1 = max(0, math.floor(y0)), min(img.height(), math.ceil(y1))
        if ix0 >= ix1 or iy0 >= iy1:
            return None
        step_x = max(1, (ix1 - ix0) // SAMPLE_GRID)
        step_y = max(1, (iy1 - iy0) // SAMPLE_GRID)
        r = g = b = a = n = 0
        for yy in range(iy0, iy1, step_y):
            for xx in range(ix0, ix1, step_x):
                c = img.pixelColor(xx, yy)
                r += c.red()
                g += c.green()
                b += c.blue()
                a += c.alpha()
                n += 1
        return QColor(round(r / n), round(g / n), round(b / n), round(a / n))

    def fit_to_canvas(self, canvas_w: int, canvas_h: int) -> None:
        """Scale the photo so it fits entirely inside the sprite canvas."""
        if not self.loaded:
            return
        iw, ih = self.image.width(), self.image.height()
        if iw == 0 or ih == 0:
            return
        self.scale = min(canvas_w / iw, canvas_h / ih)
        # center it
        self.offset_x = (canvas_w - iw * self.scale) / 2.0
        self.offset_y = (canvas_h - ih * self.scale) / 2.0
        self.changed.emit()

    # ------------------------------------------------------------- setters
    def set_visible(self, v: bool) -> None:
        self.visible = v
        self.changed.emit()

    def set_opacity(self, o: float) -> None:
        self.opacity = max(0.0, min(1.0, o))
        self.changed.emit()

    def set_scale(self, s: float) -> None:
        self.scale = max(0.001, s)
        self.changed.emit()

    def set_offset(self, x: float, y: float) -> None:
        self.offset_x = x
        self.offset_y = y
        self.changed.emit()

    # ------------------------------------------------------------- sidecar
    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "visible": self.visible,
            "opacity": self.opacity,
            "scale": self.scale,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
        }

    def from_dict(self, data: dict) -> None:
        path = data.get("path")
        if path and os.path.exists(path):
            self.load(path)
        self.visible = bool(data.get("visible", True))
        self.opacity = float(data.get("opacity", 0.5))
        self.scale = float(data.get("scale", 1.0))
        self.offset_x = float(data.get("offset_x", 0.0))
        self.offset_y = float(data.get("offset_y", 0.0))
        self.changed.emit()


class UnderlayPanel(QWidget):
    """Dock panel with the trace-photo controls.

    Also hosts the display-only "sprite layer opacity" slider so you can make
    your own pixels semi-translucent while tracing over the photo.
    """

    def __init__(self, underlay: Underlay, canvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.underlay = underlay
        self.canvas = canvas

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        btn_row = QHBoxLayout()
        load_btn = QPushButton("Load Photo\u2026")
        load_btn.clicked.connect(self._load)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.underlay.clear)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        self.path_label = QLabel("(no photo loaded)")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.visible_check = QCheckBox("Show underlay")
        self.visible_check.setChecked(True)
        self.visible_check.toggled.connect(self.underlay.set_visible)
        layout.addWidget(self.visible_check)

        form = QFormLayout()

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self.underlay.opacity * 100))
        self.opacity_slider.valueChanged.connect(
            lambda v: self.underlay.set_opacity(v / 100.0))
        form.addRow("Photo opacity:", self.opacity_slider)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.001, 1000.0)
        self.scale_spin.setDecimals(3)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(self.underlay.scale)
        self.scale_spin.valueChanged.connect(self.underlay.set_scale)
        form.addRow("Scale:", self.scale_spin)

        self.off_x_spin = QDoubleSpinBox()
        self.off_x_spin.setRange(-10000.0, 10000.0)
        self.off_x_spin.setDecimals(1)
        self.off_x_spin.valueChanged.connect(self._offset_changed)
        form.addRow("Offset X:", self.off_x_spin)

        self.off_y_spin = QDoubleSpinBox()
        self.off_y_spin.setRange(-10000.0, 10000.0)
        self.off_y_spin.setDecimals(1)
        self.off_y_spin.valueChanged.connect(self._offset_changed)
        form.addRow("Offset Y:", self.off_y_spin)

        self.sprite_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sprite_opacity_slider.setRange(10, 100)
        self.sprite_opacity_slider.setValue(100)
        self.sprite_opacity_slider.setToolTip(
            "Display-only: dim your pixels to see the photo through them")
        self.sprite_opacity_slider.valueChanged.connect(
            lambda v: self.canvas.set_sprite_opacity(v / 100.0))
        form.addRow("Sprite opacity:", self.sprite_opacity_slider)

        layout.addLayout(form)

        fit_btn = QPushButton("Fit to Canvas")
        fit_btn.clicked.connect(self._fit)
        layout.addWidget(fit_btn)
        layout.addStretch()

        self.underlay.changed.connect(self._sync_from_model)
        self._sync_from_model()

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load reference photo", src_img_dir(), IMAGE_FILE_FILTER)
        if not path:
            return
        if not self.underlay.load(path):
            QMessageBox.warning(self, "Load failed",
                                f"Could not load image:\n{path}")
            return
        self.underlay.fit_to_canvas(self.canvas.doc.width,
                                    self.canvas.doc.height)

    def _fit(self) -> None:
        self.underlay.fit_to_canvas(self.canvas.doc.width,
                                    self.canvas.doc.height)

    def _offset_changed(self) -> None:
        self.underlay.set_offset(self.off_x_spin.value(),
                                 self.off_y_spin.value())

    def _sync_from_model(self) -> None:
        u = self.underlay
        self.path_label.setText(
            os.path.basename(u.path) if u.path else "(no photo loaded)")
        for w, value in ((self.opacity_slider, int(u.opacity * 100)),
                         (self.scale_spin, u.scale),
                         (self.off_x_spin, u.offset_x),
                         (self.off_y_spin, u.offset_y)):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self.visible_check.blockSignals(True)
        self.visible_check.setChecked(u.visible)
        self.visible_check.blockSignals(False)

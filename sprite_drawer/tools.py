"""Drawing tools (MS Paint standard set).

All tools write pixel-exact results using replace semantics: the chosen RGBA
value is written into the pixel verbatim (no alpha blending), which is the
behaviour sprite artists expect. Shape tools draw a live preview into
canvas.preview while dragging and re-render the final shape directly onto the
document on release.

Tool protocol (driven by PixelCanvas mouse events):
    press(canvas, x, y, color)  -- button down at sprite pixel (x, y)
    move(canvas, x, y)          -- drag to (x, y) (only while active)
    release(canvas, x, y)       -- button up; commit
"""
from __future__ import annotations

import math

from PySide6.QtGui import QColor, QImage

TRANSPARENT = QColor(0, 0, 0, 0)


# ---------------------------------------------------------------- primitives
def stamp(img: QImage, x: int, y: int, color: QColor, size: int) -> None:
    """Write a size x size square brush centred on (x, y), clipped."""
    half = size // 2
    x0, y0 = x - half, y - half
    for yy in range(max(0, y0), min(img.height(), y0 + size)):
        for xx in range(max(0, x0), min(img.width(), x0 + size)):
            img.setPixelColor(xx, yy, color)


def draw_line(img: QImage, x0: int, y0: int, x1: int, y1: int,
              color: QColor, size: int) -> None:
    """Bresenham line, stamped with the square brush."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        stamp(img, x0, y0, color, size)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_rect(img: QImage, x0: int, y0: int, x1: int, y1: int,
              color: QColor, size: int, filled: bool) -> None:
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    if filled:
        for yy in range(max(0, ya), min(img.height(), yb + 1)):
            for xx in range(max(0, xa), min(img.width(), xb + 1)):
                img.setPixelColor(xx, yy, color)
    else:
        draw_line(img, xa, ya, xb, ya, color, size)
        draw_line(img, xa, yb, xb, yb, color, size)
        draw_line(img, xa, ya, xa, yb, color, size)
        draw_line(img, xb, ya, xb, yb, color, size)


def draw_ellipse(img: QImage, x0: int, y0: int, x1: int, y1: int,
                 color: QColor, size: int, filled: bool) -> None:
    """Pixel ellipse inscribed in the drag rectangle.

    Outline: sample the boundary in both x-major and y-major passes so steep
    and shallow sections both stay gap-free. Filled: horizontal spans.
    """
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    a = (xb - xa) / 2.0  # semi-axis x
    b = (yb - ya) / 2.0  # semi-axis y
    cx = (xa + xb) / 2.0
    cy = (ya + yb) / 2.0

    if a < 0.5 or b < 0.5:  # degenerate: line
        draw_line(img, xa, ya, xb, yb, color, size)
        return

    if filled:
        for yy in range(ya, yb + 1):
            t = (yy - cy) / b
            if abs(t) > 1.0:
                continue
            half_w = a * math.sqrt(1.0 - t * t)
            for xx in range(int(math.ceil(cx - half_w)),
                            int(math.floor(cx + half_w)) + 1):
                if 0 <= xx < img.width() and 0 <= yy < img.height():
                    img.setPixelColor(xx, yy, color)
        return

    # outline -- x-major pass
    for xx in range(xa, xb + 1):
        t = (xx - cx) / a
        if abs(t) > 1.0:
            continue
        dy = b * math.sqrt(1.0 - t * t)
        stamp(img, xx, int(round(cy - dy)), color, size)
        stamp(img, xx, int(round(cy + dy)), color, size)
    # outline -- y-major pass
    for yy in range(ya, yb + 1):
        t = (yy - cy) / b
        if abs(t) > 1.0:
            continue
        dx = a * math.sqrt(1.0 - t * t)
        stamp(img, int(round(cx - dx)), yy, color, size)
        stamp(img, int(round(cx + dx)), yy, color, size)


def flood_fill(img: QImage, x: int, y: int, color: QColor) -> None:
    """Scanline flood fill replacing the contiguous region's exact RGBA."""
    w, h = img.width(), img.height()
    if not (0 <= x < w and 0 <= y < h):
        return
    target = img.pixel(x, y)
    replacement = color.rgba()
    if target == replacement:
        return
    stack = [(x, y)]
    while stack:
        px, py = stack.pop()
        if img.pixel(px, py) != target:
            continue
        # expand to full horizontal run
        x_left = px
        while x_left > 0 and img.pixel(x_left - 1, py) == target:
            x_left -= 1
        x_right = px
        while x_right < w - 1 and img.pixel(x_right + 1, py) == target:
            x_right += 1
        for xx in range(x_left, x_right + 1):
            img.setPixel(xx, py, replacement)
        for ny in (py - 1, py + 1):
            if 0 <= ny < h:
                xx = x_left
                while xx <= x_right:
                    if img.pixel(xx, ny) == target:
                        stack.append((xx, ny))
                        # skip the rest of this run; the pop re-expands it
                        while xx <= x_right and img.pixel(xx, ny) == target:
                            xx += 1
                    else:
                        xx += 1


# ---------------------------------------------------------------- tool classes
class Tool:
    name = "tool"

    def __init__(self) -> None:
        self.active = False

    def press(self, canvas, x: int, y: int, color: QColor) -> None: ...
    def move(self, canvas, x: int, y: int) -> None: ...
    def release(self, canvas, x: int, y: int) -> None: ...


class PencilTool(Tool):
    name = "Pencil"
    erase = False

    def press(self, canvas, x, y, color):
        canvas.doc.push_undo()
        self.color = TRANSPARENT if self.erase else color
        self.last = (x, y)
        stamp(canvas.doc.image, x, y, self.color, canvas.brush_size)
        self.active = True

    def move(self, canvas, x, y):
        draw_line(canvas.doc.image, self.last[0], self.last[1], x, y,
                  self.color, canvas.brush_size)
        self.last = (x, y)

    def release(self, canvas, x, y):
        self.active = False
        canvas.doc.notify_changed()


class EraserTool(PencilTool):
    name = "Eraser"
    erase = True


class FillTool(Tool):
    name = "Fill"

    def press(self, canvas, x, y, color):
        if not canvas.doc.in_bounds(x, y):
            return
        canvas.doc.push_undo()
        flood_fill(canvas.doc.image, x, y, color)
        canvas.doc.notify_changed()


class EyedropperTool(Tool):
    name = "Eyedropper"

    def press(self, canvas, x, y, color):
        if canvas.doc.in_bounds(x, y):
            canvas.color_picked.emit(canvas.doc.color_at(x, y))


class UnderlayEyedropperTool(Tool):
    """Pick the trace photo's color beneath a sprite pixel as the primary color.

    Averages the photo region the sprite pixel covers (see
    Underlay.sample_pixel). Does nothing if no photo is loaded or the pixel
    lies outside the photo.
    """
    name = "Underlay Pick"

    def press(self, canvas, x, y, color):
        if not canvas.doc.in_bounds(x, y):
            return
        picked = canvas.underlay.sample_pixel(x, y)
        if picked is not None:
            canvas.color_picked.emit(picked)


class ShapeTool(Tool):
    """Base for drag-to-draw shapes with a live preview."""
    filled = False

    def draw_shape(self, img, x0, y0, x1, y1, color, size):  # override
        raise NotImplementedError

    def press(self, canvas, x, y, color):
        self.start = (x, y)
        self.color = color
        self.active = True
        canvas.clear_preview()
        self.draw_shape(canvas.preview, x, y, x, y, color, canvas.brush_size)

    def move(self, canvas, x, y):
        canvas.clear_preview()
        self.draw_shape(canvas.preview, self.start[0], self.start[1], x, y,
                        self.color, canvas.brush_size)

    def release(self, canvas, x, y):
        self.active = False
        canvas.clear_preview()
        canvas.doc.push_undo()
        self.draw_shape(canvas.doc.image, self.start[0], self.start[1], x, y,
                        self.color, canvas.brush_size)
        canvas.doc.notify_changed()


class LineTool(ShapeTool):
    name = "Line"

    def draw_shape(self, img, x0, y0, x1, y1, color, size):
        draw_line(img, x0, y0, x1, y1, color, size)


class RectTool(ShapeTool):
    name = "Rectangle"

    def draw_shape(self, img, x0, y0, x1, y1, color, size):
        draw_rect(img, x0, y0, x1, y1, color, size, self.filled)


class FilledRectTool(RectTool):
    name = "Filled Rectangle"
    filled = True


class EllipseTool(ShapeTool):
    name = "Ellipse"

    def draw_shape(self, img, x0, y0, x1, y1, color, size):
        draw_ellipse(img, x0, y0, x1, y1, color, size, self.filled)


class FilledEllipseTool(EllipseTool):
    name = "Filled Ellipse"
    filled = True

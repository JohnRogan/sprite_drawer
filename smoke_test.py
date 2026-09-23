"""Headless smoke test for Sprite Drawer (run with QT_QPA_PLATFORM=offscreen)."""
import json
import os
import sys
import tempfile

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from sprite_drawer.app import MainWindow, sidecar_path
from sprite_drawer.paths import sprites_dir, src_img_dir
from sprite_drawer.document import SpriteDocument
from sprite_drawer import tools
from sprite_drawer.underlay import Underlay

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# --- default dialog folders are <repo>/sprites and <repo>/src_img, any cwd ---
_repo = os.path.dirname(os.path.abspath(__file__))
_cwd = os.getcwd()
os.chdir(tempfile.gettempdir())
check("default sprite dialog folder is repo sprites/",
      sprites_dir() == os.path.join(_repo, "sprites")
      and os.path.isdir(sprites_dir()))
check("default photo dialog folder is repo src_img/",
      src_img_dir() == os.path.join(_repo, "src_img")
      and os.path.isdir(src_img_dir()))
os.chdir(_cwd)

# --- document: arbitrary dims, undo/redo ---
doc = SpriteDocument()
doc.new(37, 53)
check("arbitrary dims 37x53", doc.width == 37 and doc.height == 53)
doc.push_undo()
doc.image.setPixelColor(5, 5, QColor("#ff0000"))
doc.notify_changed()
check("pixel set", doc.color_at(5, 5) == QColor("#ff0000"))
doc.undo()
check("undo restores transparent", doc.color_at(5, 5).alpha() == 0)
doc.redo()
check("redo restores red", doc.color_at(5, 5) == QColor("#ff0000"))

# --- tools primitives ---
img = QImage(20, 20, QImage.Format.Format_ARGB32)
img.fill(QColor(0, 0, 0, 0))
blue = QColor("#0000ff")
tools.draw_line(img, 0, 0, 19, 19, blue, 1)
check("bresenham diagonal endpoints",
      img.pixelColor(0, 0) == blue and img.pixelColor(19, 19) == blue)
check("bresenham midpoint", img.pixelColor(10, 10) == blue)

img.fill(QColor(0, 0, 0, 0))
tools.draw_rect(img, 2, 2, 10, 8, blue, 1, filled=False)
check("rect outline corners",
      all(img.pixelColor(x, y) == blue for x, y in
          [(2, 2), (10, 2), (2, 8), (10, 8)]))
check("rect outline hollow", img.pixelColor(5, 5).alpha() == 0)

img.fill(QColor(0, 0, 0, 0))
tools.draw_rect(img, 2, 2, 10, 8, blue, 1, filled=True)
check("filled rect interior", img.pixelColor(5, 5) == blue)

img.fill(QColor(0, 0, 0, 0))
tools.draw_ellipse(img, 0, 0, 19, 19, blue, 1, filled=False)
check("ellipse outline extremes",
      img.pixelColor(0, 9).alpha() > 0 or img.pixelColor(0, 10).alpha() > 0)
check("ellipse hollow center", img.pixelColor(9, 9).alpha() == 0)

img.fill(QColor(0, 0, 0, 0))
tools.draw_ellipse(img, 0, 0, 19, 19, blue, 1, filled=True)
check("filled ellipse center", img.pixelColor(9, 9) == blue)
check("filled ellipse corner empty", img.pixelColor(0, 0).alpha() == 0)

img.fill(QColor(0, 0, 0, 0))
tools.draw_rect(img, 2, 2, 17, 17, blue, 1, filled=False)
tools.flood_fill(img, 9, 9, QColor("#00ff00"))
check("flood fill inside rect", img.pixelColor(9, 9) == QColor("#00ff00"))
check("flood fill stays inside", img.pixelColor(0, 0).alpha() == 0)
check("flood fill respects border", img.pixelColor(2, 2) == blue)

# out-of-canvas shape must clip, not crash
tools.draw_line(img, -5, -5, 25, 25, blue, 3)
tools.flood_fill(img, 50, 50, blue)
check("clipping does not crash", True)

# --- brush stamp size ---
img.fill(QColor(0, 0, 0, 0))
tools.stamp(img, 10, 10, blue, 3)
check("brush size 3 stamps 3x3",
      all(img.pixelColor(10 + dx, 10 + dy) == blue
          for dx in (-1, 0, 1) for dy in (-1, 0, 1)))

# --- save / load roundtrip with sidecar ---
tmp = tempfile.mkdtemp()
png_path = os.path.join(tmp, "hero.png")
doc.save(png_path)
doc2 = SpriteDocument()
doc2.load(png_path)
check("png roundtrip dims", doc2.width == 37 and doc2.height == 53)
check("png roundtrip pixel", doc2.color_at(5, 5) == QColor("#ff0000"))
check("modified cleared after save", not doc.modified)

# underlay + sidecar
ref = QImage(100, 60, QImage.Format.Format_ARGB32)
ref.fill(QColor("#123456"))
ref_path = os.path.join(tmp, "photo.png")
ref.save(ref_path)
u = Underlay()
check("underlay load", u.load(ref_path))

# underlay format support: HEIC (via pillow-heif) and PDF (via QtPdf)
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()
heic_path = os.path.join(tmp, "photo.heic")
Image.new("RGB", (120, 80), (18, 52, 86)).save(heic_path, format="HEIF")
u_heic = Underlay()
check("underlay loads HEIC",
      u_heic.load(heic_path) and u_heic.image.width() == 120
      and u_heic.image.height() == 80)

from PySide6.QtGui import QPageSize, QPainter as _QP, QPdfWriter
pdf_path = os.path.join(tmp, "photo.pdf")
writer = QPdfWriter(pdf_path)
writer.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
p = _QP(writer)
p.fillRect(0, 0, 500, 500, QColor("#654321"))
p.end()
u_pdf = Underlay()
check("underlay loads PDF page 1",
      u_pdf.load(pdf_path) and u_pdf.image.width() > 0)
check("pdf render capped at 2048",
      max(u_pdf.image.width(), u_pdf.image.height()) == 2048)

u_bad = Underlay()
check("unreadable file rejected gracefully",
      not u_bad.load(os.path.join(tmp, "nope.heic")) and not u_bad.loaded)

# underlay color sampling: left half red, right half blue photo, 200x100
two_tone = QImage(200, 100, QImage.Format.Format_ARGB32)
two_tone.fill(QColor("#ff0000"))
for yy in range(100):
    for xx in range(100, 200):
        two_tone.setPixelColor(xx, yy, QColor("#0000ff"))
tt_path = os.path.join(tmp, "two_tone.png")
two_tone.save(tt_path)
u_s = Underlay()
u_s.load(tt_path)
u_s.fit_to_canvas(20, 10)          # scale 0.1: each sprite px = 10x10 photo px
check("sample left side is red", u_s.sample_pixel(2, 5) == QColor("#ff0000"))
check("sample right side is blue", u_s.sample_pixel(17, 5) == QColor("#0000ff"))
u_s.set_offset(0.5, 0.0)           # now sprite px 10 covers photo x 95..105
mid = u_s.sample_pixel(10, 5)      # straddles the red/blue seam at x=100
check("sample region is averaged (not point)",
      mid is not None and mid.red() > 0 and mid.blue() > 0)
u_s.set_offset(5.0, 0.0)
check("sample outside photo is None", u_s.sample_pixel(0, 0) is None)
check("sample with no photo is None", Underlay().sample_pixel(0, 0) is None)

# palette size
from sprite_drawer.color_panel import build_ramp_palette
pal = build_ramp_palette()
flat = [c for row in pal for c in row]
check("ramp palette has 96 colors", len(flat) == 96)
check("ramp palette colors are distinct",
      len({c.rgba() for c in flat}) == len(flat))
u.fit_to_canvas(37, 53)
check("fit scale letterboxes", abs(u.scale - 37 / 100) < 1e-9)
u.set_opacity(0.42)
data = {"underlay": u.to_dict()}
sc = sidecar_path(png_path)
with open(sc, "w") as f:
    json.dump(data, f)
u2 = Underlay()
with open(sc) as f:
    u2.from_dict(json.load(f)["underlay"])
check("sidecar restores underlay",
      u2.loaded and abs(u2.opacity - 0.42) < 1e-9
      and abs(u2.scale - u.scale) < 1e-9)
check("sidecar path naming", sc.endswith("hero.sprite.json"))

# --- hex parsing via ColorPanel ---
from sprite_drawer.color_panel import ColorPanel
panel = ColorPanel()
panel.hex_edit.setText("#ff8800")
panel._hex_entered()
check("hex RRGGBB", panel.primary == QColor("#ff8800"))
panel.hex_edit.setText("#ff880080")
panel._hex_entered()
check("hex RRGGBBAA alpha", panel.primary.alpha() == 0x80
      and panel.primary.red() == 0xFF and panel.primary.green() == 0x88)
panel.hex_edit.setText("#f80")
panel._hex_entered()
check("hex shorthand RGB", panel.primary == QColor("#ff8800"))
# three hex entries but only two distinct RGBA values (dedupe is intended)
check("recent colors tracked + deduped", len(panel.recent) == 2)

# --- MainWindow constructs and wires up ---
win = MainWindow()
check("main window builds", win.canvas.current_tool is win._tools["pencil"])
win._select_tool("fill")
check("tool switch", win.canvas.current_tool is win._tools["fill"])

# simulate a pencil stroke through the tool protocol
win._select_tool("pencil")
win.canvas.brush_size = 1
tool = win.canvas.current_tool
tool.press(win.canvas, 1, 1, QColor("#00ffff"))
tool.move(win.canvas, 4, 1)
tool.release(win.canvas, 4, 1)
check("pencil stroke via protocol",
      win.doc.color_at(1, 1) == QColor("#00ffff")
      and win.doc.color_at(4, 1) == QColor("#00ffff"))
check("stroke marks modified", win.doc.modified)
win.doc.undo()
check("stroke undo", win.doc.color_at(1, 1).alpha() == 0)

# underlay pick tool sets the primary color from the photo
win.underlay.load(tt_path)
win.underlay.fit_to_canvas(win.doc.width, win.doc.height)
win._select_tool("underlay_pick")
win.doc.set_modified(False)  # the earlier undo flagged it; start clean
before = QColor(win.color_panel.primary)
win.canvas.current_tool.press(win.canvas, 1, win.doc.height // 2, before)
check("underlay pick sets primary from photo",
      win.color_panel.primary == QColor("#ff0000")
      and win.canvas.primary_color == QColor("#ff0000"))
check("underlay pick does not modify pixels", not win.doc.modified)
check("underlay pick has toolbar action", "underlay_pick" in win._tool_actions)

# background cycling + preview mode (state and actual key shortcuts)
from PySide6.QtCore import Qt as _Qt
from PySide6.QtTest import QTest
from sprite_drawer.canvas import BG_CHECKER, BG_GRID, BG_PLAIN, PLAIN_BG
c = win.canvas
check("starts in grid+checker mode", c.background_mode == BG_GRID)
c.cycle_background()
check("cycle -> checker only", c.background_mode == BG_CHECKER)
c.cycle_background()
check("cycle -> plain", c.background_mode == BG_PLAIN)
c.cycle_background()
check("cycle wraps to grid", c.background_mode == BG_GRID)

# window-context shortcuts only fire for a shown, active window
win.show()
QTest.qWaitForWindowExposed(win)
win.activateWindow()
win.canvas.setFocus()
QTest.qWait(50)
QTest.keyClick(win.canvas, _Qt.Key.Key_G)
check("G shortcut cycles background", c.background_mode == BG_CHECKER)
QTest.keyClick(win.canvas, _Qt.Key.Key_G, _Qt.KeyboardModifier.ControlModifier)
check("Ctrl+G no longer cycles", c.background_mode == BG_CHECKER)
win.color_panel.hex_edit.setFocus()
QTest.keyClicks(win.color_panel.hex_edit, "gh")
check("typing g/h in hex field does not trigger view toggles",
      c.background_mode == BG_CHECKER and not c.sprite_hidden)
win.color_panel.hex_edit.clear()
win.canvas.setFocus()
check("status label tracks mode", "checker only" in win.view_label.text())

check("preview off by default", not c.preview_mode)
QTest.keyClick(win.canvas, _Qt.Key.Key_Tab)
check("Tab shortcut enters preview", c.preview_mode
      and win.preview_action.isChecked())
check("status label shows PREVIEW", "PREVIEW" in win.view_label.text())
QTest.keyClick(win.canvas, _Qt.Key.Key_Tab)
check("Tab again exits preview", not c.preview_mode)

# rendering: preview hides checker/underlay behind a flat backdrop
c.set_zoom(8)
c.set_preview_mode(True)
shot = c.grab().toImage()
tx, ty = 0, 0  # a transparent sprite pixel (stroke was undone above)
check("preview backdrop is flat neutral",
      shot.pixelColor(tx * 8 + 3, ty * 8 + 3) == PLAIN_BG)
c.set_preview_mode(False)
c.background_mode = BG_PLAIN
shot = c.grab().toImage()
check("plain mode backdrop is flat neutral",
      shot.pixelColor(3, 3) == PLAIN_BG)
c.background_mode = BG_GRID

# Ctrl/Cmd+H hides drawn pixels (display only) without touching other modes
win.doc.image.setPixelColor(0, 0, QColor("#ff00ff"))
win.doc.set_modified(False)
c.background_mode = BG_PLAIN
check("drawn pixel visible before hide",
      c.grab().toImage().pixelColor(3, 3) == QColor("#ff00ff"))
win.canvas.setFocus()
QTest.keyClick(win.canvas, _Qt.Key.Key_H)
check("H shortcut hides drawn pixels",
      c.sprite_hidden and win.hide_pixels_action.isChecked())
check("hidden pixel shows backdrop",
      c.grab().toImage().pixelColor(3, 3) == PLAIN_BG)
check("hide does not modify document",
      win.doc.color_at(0, 0) == QColor("#ff00ff") and not win.doc.modified)
check("hide leaves background mode alone", c.background_mode == BG_PLAIN)
check("hide leaves preview alone", not c.preview_mode)
check("status label shows PIXELS HIDDEN",
      "PIXELS HIDDEN" in win.view_label.text())
QTest.keyClick(win.canvas, _Qt.Key.Key_Tab)
check("pixels stay hidden in preview",
      c.preview_mode and c.grab().toImage().pixelColor(3, 3) == PLAIN_BG)
QTest.keyClick(win.canvas, _Qt.Key.Key_Tab)
QTest.keyClick(win.canvas, _Qt.Key.Key_H)
check("H again shows pixels",
      not c.sprite_hidden
      and c.grab().toImage().pixelColor(3, 3) == QColor("#ff00ff"))
win.doc.image.setPixelColor(0, 0, QColor(0, 0, 0, 0))
c.background_mode = BG_GRID

# checkerboard squares must track zoom so one square == one sprite pixel
for z in (1, 7, 20, 64):
    win.canvas.set_zoom(z)
    if win.canvas._checker.width() != 2 * z:
        check(f"checker tile locked to zoom {z}", False)
        break
else:
    check("checker tile locked to zoom at 1/7/20/64", True)
win.doc.set_modified(False)  # allow clean close

print()
if failures:
    print(f"{len(failures)} FAILURES:", failures)
    sys.exit(1)
print("ALL CHECKS PASSED")
